"""
Decision Pipeline Router — Sprint 73
=======================================
/api/decide/{ticker}     — Full decision object for one ticker
/api/decide/batch        — Batch decision for multiple tickers
/api/decide/peers/{t}    — Peer comparison report
/api/portfolio           — All portfolio summaries
/api/portfolio/{type}    — Single portfolio detail
/api/portfolio/review    — Weekly postmortem for all portfolios
/api/experiments         — Keep/discard experiment log
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decision-pipeline"])


# ── Decision Object endpoints ────────────────────────────────────────────────


@router.get("/api/decide/{ticker}")
async def decide_ticker(ticker: str):
    """
    Full decision object for a single ticker.
    Runs the complete pipeline: Macro → Sector → RS → Setup → Confidence →
    Levels → Reasoning → Peers → Portfolio Gate → Final Action.
    """
    from src.engines.decision_object import DecisionPipeline

    pipeline = DecisionPipeline()
    decision = pipeline.build(ticker)
    return decision.to_dict()


@router.get("/api/decide/batch")
async def decide_batch(
    tickers: str = Query(
        default="NVDA,AAPL,MSFT,AMD,META",
        description="Comma-separated tickers",
    ),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Batch decision for multiple tickers. Returns sorted by final_confidence."""
    from src.engines.decision_object import DecisionPipeline

    pipeline = DecisionPipeline()
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()][:limit]
    decisions = pipeline.build_batch(ticker_list)

    # Sort by confidence descending
    decisions.sort(key=lambda d: d.final_confidence, reverse=True)

    return {
        "count": len(decisions),
        "decisions": [d.to_dict() for d in decisions],
    }


# ── Peer Comparison endpoints ────────────────────────────────────────────────


@router.get("/api/decide/peers/{ticker}")
async def peer_comparison(ticker: str):
    """
    Full peer comparison report:
    sector peers + RS ranking + stronger/weaker + explanations.
    """
    from src.engines.peer_comparison import PeerEngine

    engine = PeerEngine()
    return engine.compare_vs_peers(ticker.strip().upper())


# ── Portfolio Brain endpoints ────────────────────────────────────────────────


@router.get("/api/portfolio")
async def portfolio_all():
    """All 3 portfolio archetype summaries."""
    from src.engines.portfolio_brain import PortfolioBrain

    brain = PortfolioBrain()
    return {
        "portfolios": brain.all_summaries(),
        "count": len(brain.portfolios),
    }


@router.get("/api/portfolio/{archetype}")
async def portfolio_detail(archetype: str):
    """Single portfolio detail. Archetype: TREND_LEADERS, DEFENSIVE, TACTICAL."""
    from src.engines.portfolio_brain import PortfolioBrain

    brain = PortfolioBrain()
    run = brain.get_portfolio(archetype.upper())
    if not run:
        return {"error": f"Unknown archetype: {archetype}"}
    return run.summary()


@router.get("/api/portfolio/review")
async def portfolio_review():
    """Weekly postmortem for all portfolios."""
    from src.engines.portfolio_brain import PortfolioBrain

    brain = PortfolioBrain()
    return {
        "reviews": brain.review_all(),
        "count": len(brain.portfolios),
    }


# ── Keep/Discard Experiment endpoints ────────────────────────────────────────


@router.get("/api/experiments")
async def experiments_summary():
    """Keep/discard experiment log summary."""
    from src.engines.keep_discard import ExperimentLog

    log = ExperimentLog()
    return log.summary()


@router.get("/api/experiments/best")
async def experiments_best():
    """Best strategy variant ever tested."""
    from src.engines.keep_discard import ExperimentLog

    log = ExperimentLog()
    best = log.best_variant()
    if not best:
        return {"best": None, "message": "No experiments run yet"}
    return best


# ── PortfolioBrain sync endpoint ──────────────────────────────────────────────


@router.post("/api/portfolio/sync")
async def portfolio_sync(
    tickers: List[str] = None,
    archetype: str = "GROWTH",
):
    """
    Run DecisionPipeline on *tickers* (defaults to all brief tickers),
    gate each result through PortfolioBrain.can_add(), and persist
    approved holdings.

    Returns:
        added    — list of tickers added to the portfolio
        blocked  — list of tickers rejected with reason
        skipped  — tickers with insufficient decision confidence
    """
    import asyncio
    from src.services.brief_data_service import all_brief_tickers
    from src.engines.decision_object import DecisionPipeline
    from src.engines.portfolio_brain import PortfolioBrain, Holding
    from datetime import datetime, timezone

    if not tickers:
        tickers = all_brief_tickers()
    if not tickers:
        return {"error": "No tickers available — run generate_brief.py first"}

    archetype = archetype.upper()

    # Build decisions off the event loop (yfinance calls are blocking)
    def _run_decisions():
        pipeline = DecisionPipeline()
        return pipeline.build_batch(tickers)

    decisions = await asyncio.to_thread(_run_decisions)

    brain = PortfolioBrain()
    run = brain.get_portfolio(archetype)
    if run is None:
        return {"error": f"Unknown archetype: {archetype}"}

    added, blocked, skipped = [], [], []

    for d in decisions:
        # Minimum quality gate: TRADE conviction + confidence ≥ 60
        if d.conviction_tier not in ("TRADE", "LEADER"):
            skipped.append(
                {"ticker": d.ticker, "reason": f"conviction={d.conviction_tier}"}
            )
            continue
        if d.final_confidence < 60:
            skipped.append(
                {"ticker": d.ticker, "reason": f"confidence={d.final_confidence}"}
            )
            continue

        ok, reason = run.can_add(d.ticker, d.sector or "UNKNOWN")
        if not ok:
            blocked.append({"ticker": d.ticker, "reason": reason})
            continue

        holding = Holding(
            ticker=d.ticker,
            entry_date=datetime.now(timezone.utc).date().isoformat(),
            entry_price=d.current_price or 0.0,
            current_price=d.current_price or 0.0,
            sector=d.sector or "UNKNOWN",
            entry_rs=d.rs_composite or 100.0,
            entry_confidence=d.final_confidence,
            entry_thesis=d.thesis or "",
            status="OPEN",
        )
        run.add_holding(holding)
        added.append(d.ticker)

    if added:
        brain.save_all()

    return {
        "archetype": archetype,
        "tickers_evaluated": len(decisions),
        "added": added,
        "blocked": blocked,
        "skipped": skipped,
    }


# ── Discord alert trigger ─────────────────────────────────────────────────────


@router.get("/api/alerts/decision/{ticker}")
async def alert_decision(ticker: str, webhook_url: str = ""):
    """
    Build a full decision object for *ticker* and push it to Discord
    via a structured embed.

    Query param:
        webhook_url  — override the DISCORD_WEBHOOK_URL env var
    """
    import asyncio
    from src.engines.decision_object import DecisionPipeline
    from src.notifications.discord_bot import DiscordInteractiveBot

    ticker = ticker.upper()

    def _build():
        pipeline = DecisionPipeline()
        d = pipeline.build(ticker)
        return d.to_dict() if hasattr(d, "to_dict") else vars(d)

    try:
        decision_dict = await asyncio.to_thread(_build)
    except Exception as exc:
        return {"ticker": ticker, "error": f"Decision build failed: {exc}"}

    bot = DiscordInteractiveBot()
    sent = await bot.send_decision_alert(decision_dict, channel_webhook=webhook_url)

    return {
        "ticker": ticker,
        "sent": sent,
        "conviction": decision_dict.get("conviction_tier"),
        "confidence": decision_dict.get("final_confidence"),
        "message": (
            "Alert dispatched"
            if sent
            else "Alert skipped (no webhook configured or embed build failed)"
        ),
    }
