"""
CC — Playbook & Scanner API Router
=====================================
Decision-oriented endpoints for the upgraded platform.

Endpoints:
  GET  /api/v7/playbook/today       — Today's regime + playbook
  GET  /api/v7/playbook/ranked      — 3-layer ranked opportunities
  GET  /api/v7/playbook/scanners    — Scanner matrix results
  GET  /api/v7/playbook/vcp/{ticker} — VCP intelligence for ticker
  GET  /api/v7/playbook/dossier/{ticker} — Full symbol dossier
  GET  /api/v7/playbook/no-trade    — Current no-trade / avoid list
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/playbook", tags=["playbook"])


def _get_pipeline():
    """Lazy import to avoid circular deps."""
    from src.engines.sector_pipeline import SectorPipeline

    return SectorPipeline()


def _get_vcp():
    from src.engines.vcp_intelligence import VCPIntelligence

    return VCPIntelligence()


def _get_scanner():
    from src.engines.scanner_matrix import ScannerMatrix

    return ScannerMatrix()


# ── Today / Playbook ─────────────────────────────────────────────────


@router.get("/today")
async def today_playbook() -> Dict[str, Any]:
    """Today's market regime, sector playbook, top 5, avoid list."""
    pipeline = _get_pipeline()

    # Get current regime (simplified — would come from regime engine)
    regime = _get_regime_stub()
    signals = _get_signals_stub()

    results = pipeline.process_batch(signals, regime)

    # Top 5 by conviction
    top5 = [
        {
            "rank": i + 1,
            "ticker": r.signal.get("ticker"),
            "sector": r.sector.sector_bucket.value,
            "theme": r.sector.theme,
            "action": r.decision.action,
            "grade": r.fit.grade,
            "confidence": round(r.confidence.final, 2),
            "why_now": r.explanation.why_now,
        }
        for i, r in enumerate(results[:5])
    ]

    # Avoid list
    avoid = [
        {
            "ticker": r.signal.get("ticker"),
            "reason": r.decision.rationale,
        }
        for r in results
        if r.decision.action == "NO_TRADE"
    ]

    # Sector playbook
    sector_summary = pipeline.get_sector_summary(results)
    action_summary = pipeline.get_action_summary(results)

    return {
        "regime": regime,
        "tradeability": "TRADE" if regime.get("should_trade") else "NO_TRADE",
        "sector_playbook": sector_summary,
        "action_summary": action_summary,
        "top_5": top5,
        "avoid_list": avoid[:10],
        "total_signals": len(results),
    }


# ── Ranked Opportunities ─────────────────────────────────────────────


@router.get("/ranked")
async def ranked_opportunities(
    limit: int = Query(20, ge=1, le=100),
    action: str = Query(None, description="Filter by action"),
    sector: str = Query(None, description="Filter by sector bucket"),
) -> Dict[str, Any]:
    """3-layer ranked opportunity board."""
    pipeline = _get_pipeline()
    regime = _get_regime_stub()
    signals = _get_signals_stub()

    results = pipeline.process_batch(signals, regime)

    # Filter
    if action:
        results = [r for r in results if r.decision.action == action.upper()]
    if sector:
        results = [r for r in results if r.sector.sector_bucket.value == sector.upper()]

    rows = []
    for r in results[:limit]:
        row = {
            "ticker": r.signal.get("ticker"),
            "sector_type": r.sector.sector_bucket.value,
            "theme": r.sector.theme,
            "setup": r.signal.get("strategy", ""),
            "stage": r.sector.sector_stage.value,
            "leader": r.sector.leader_status.value,
            "score": round(r.fit.final_score, 1),
            "grade": r.fit.grade,
            "thesis_conf": round(r.confidence.thesis, 2),
            "timing_conf": round(r.confidence.timing, 2),
            "exec_conf": round(r.confidence.execution, 2),
            "data_conf": round(r.confidence.data, 2),
            "final_conf": round(r.confidence.final, 2),
            "action": r.decision.action,
            "risk_level": r.decision.risk_level,
        }
        if r.ranking:
            row["discovery_rank"] = r.ranking.discovery_rank
            row["action_rank"] = r.ranking.action_rank
            row["conviction_rank"] = r.ranking.conviction_rank
        if r.conflict:
            row["conflict_level"] = r.conflict.conflict_level
        rows.append(row)

    return {
        "count": len(rows),
        "opportunities": rows,
    }


# ── Scanner Hub ──────────────────────────────────────────────────────


@router.get("/scanners")
async def scanner_hub(
    category: str = Query(None, description="PATTERN/FLOW/SECTOR/RISK/VALIDATION"),
) -> Dict[str, Any]:
    """Scanner matrix results grouped by category."""
    scanner = _get_scanner()
    regime = _get_regime_stub()
    signals = _get_signals_stub()

    if category:
        from src.engines.scanner_matrix import ScannerCategory

        try:
            cat = ScannerCategory(category.upper())
            hits = scanner.scan_category(cat, signals, regime)
            return {
                "category": category.upper(),
                "hits": [h.to_dict() for h in hits],
                "count": len(hits),
            }
        except ValueError:
            return {"error": f"Unknown category: {category}"}

    summary = scanner.get_summary(signals, regime)
    return {"scanners": summary}


# ── VCP Intelligence ─────────────────────────────────────────────────


@router.get("/vcp/{ticker}")
async def vcp_analysis(ticker: str) -> Dict[str, Any]:
    """Full VCP intelligence analysis for a ticker."""
    pipeline = _get_pipeline()
    vcp = _get_vcp()
    regime = _get_regime_stub()

    signal = _get_signal_for_ticker(ticker)
    if not signal:
        return {"error": f"No signal data for {ticker}"}

    sector = pipeline.classifier.classify(ticker, signal)
    result = vcp.analyze(signal, sector, regime)

    return {
        "ticker": ticker,
        "vcp": result.to_dict(),
    }


# ── Symbol Dossier ───────────────────────────────────────────────────


@router.get("/dossier/{ticker}")
async def symbol_dossier(ticker: str) -> Dict[str, Any]:
    """Complete decision dossier for a single symbol."""
    pipeline = _get_pipeline()
    vcp = _get_vcp()
    regime = _get_regime_stub()

    signal = _get_signal_for_ticker(ticker)
    if not signal:
        return {"error": f"No signal data for {ticker}"}

    # Full pipeline
    result = pipeline.process(signal, regime)

    # VCP analysis (if applicable)
    vcp_result = vcp.analyze(signal, result.sector, regime)

    # Scanner warnings
    scanner = _get_scanner()
    warnings = scanner.get_warnings([signal], regime)
    ticker_warnings = [w.to_dict() for w in warnings if w.ticker == ticker]

    return {
        "ticker": ticker,
        "signal": result.to_dict(),
        "vcp": vcp_result.to_dict() if vcp_result.detection.is_vcp else None,
        "warnings": ticker_warnings,
    }


# ── No-Trade / Avoid List ───────────────────────────────────────────


@router.get("/no-trade")
async def no_trade_list() -> Dict[str, Any]:
    """Current no-trade and avoid signals with reasons."""
    pipeline = _get_pipeline()
    regime = _get_regime_stub()
    signals = _get_signals_stub()

    results = pipeline.process_batch(signals, regime)

    no_trades = [
        {
            "ticker": r.signal.get("ticker"),
            "action": r.decision.action,
            "reason": r.decision.rationale,
            "risk_level": r.decision.risk_level,
            "conflict": r.conflict.summary if r.conflict else "",
            "sector": r.sector.sector_bucket.value,
            "stage": r.sector.sector_stage.value,
        }
        for r in results
        if r.decision.action in ("NO_TRADE", "EXIT", "REDUCE")
    ]

    return {
        "count": len(no_trades),
        "no_trade_signals": no_trades,
    }


# ── Stubs (replace with real data sources) ───────────────────────────


def _get_rs_engine():
    from src.engines.rs_ranking import RSRankingEngine

    return RSRankingEngine()


def _get_flow_engine():
    from src.engines.flow_intelligence import FlowIntelligenceEngine

    return FlowIntelligenceEngine()


@router.get("/rs-ranking")
async def rs_ranking(
    sector: str = Query(None, description="Filter by sector"),
    cap: str = Query(None, description="MEGA/LARGE/MID/SMALL"),
    limit: int = Query(30, ge=1, le=100),
) -> Dict[str, Any]:
    """Relative Strength ranking with sector/size filters."""
    engine = _get_rs_engine()
    universe = _get_rs_universe_stub()

    entries = engine.rank(universe, _get_benchmark_stub())

    if sector:
        entries = [e for e in entries if e.sector.upper() == sector.upper()]
    if cap:
        entries = [e for e in entries if e.market_cap.upper() == cap.upper()]

    sector_rs = engine.get_sector_rankings(entries)
    breakouts = engine.get_breakouts(entries)
    breakdowns = engine.get_breakdowns(entries)

    return {
        "count": min(limit, len(entries)),
        "rankings": [e.to_dict() for e in entries[:limit]],
        "sector_rs": [s.to_dict() for s in sector_rs],
        "breakouts": [e.to_dict() for e in breakouts[:10]],
        "breakdowns": [e.to_dict() for e in breakdowns[:10]],
    }


@router.get("/flow")
async def flow_intelligence(
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    """Flow / smart money intelligence."""
    engine = _get_flow_engine()
    universe = _get_flow_universe_stub()

    profiles = engine.analyze_batch(universe)
    unusual = engine.get_unusual_activity(profiles)

    return {
        "count": min(limit, len(profiles)),
        "profiles": [p.to_dict() for p in profiles[:limit]],
        "unusual_activity": [p.to_dict() for p in unusual[:10]],
    }


def _get_regime_stub() -> Dict[str, Any]:
    """Stub regime — replace with RegimeDetector output."""
    return {
        "should_trade": True,
        "trend": "NEUTRAL",
        "vix": 18.5,
        "macro_trend": "neutral",
        "macro_event_nearby": False,
    }


def _get_signals_stub() -> List[Dict[str, Any]]:
    """Stub signals — replace with SignalEngine output."""
    return []


def _get_signal_for_ticker(ticker: str) -> Dict[str, Any] | None:
    """Stub single signal lookup."""
    return {"ticker": ticker, "score": 5, "strategy": "scan"}


def _get_rs_universe_stub() -> List[Dict[str, Any]]:
    """Stub RS universe — replace with real market data."""
    return []


def _get_benchmark_stub() -> Dict[str, Any]:
    """Stub benchmark returns — replace with SPY data."""
    return {
        "return_1w": 0.5,
        "return_1m": 2.1,
        "return_3m": 5.0,
        "return_6m": 8.0,
    }


def _get_flow_universe_stub() -> List[Dict[str, Any]]:
    """Stub flow data — replace with real OHLCV data."""
    return []
