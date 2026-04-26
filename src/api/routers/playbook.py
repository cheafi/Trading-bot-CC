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
    top5 = []
    for i, r in enumerate(results[:5]):
        entry = {
            "rank": i + 1,
            "ticker": r.signal.get("ticker"),
            "sector": r.sector.sector_bucket.value,
            "theme": r.sector.theme,
            "action": r.decision.action,
            "grade": r.fit.grade,
            "confidence": round(r.confidence.final, 2),
            "why_now": r.explanation.why_now,
        }
        # Why This Not That — attach runner-up for comparison
        if i < len(results) - 1:
            nxt = results[i + 1]
            entry["runner_up"] = {
                "ticker": nxt.signal.get("ticker"),
                "score": round(nxt.confidence.final, 2),
                "reason": f"Higher conviction ({round(r.confidence.final, 2)} vs {round(nxt.confidence.final, 2)})"
                + (
                    f", better sector fit ({r.sector.sector_bucket.value})"
                    if r.sector.sector_bucket != nxt.sector.sector_bucket
                    else ""
                ),
            }
        top5.append(entry)

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
    for i, r in enumerate(results[:limit]):
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
            "entry_price": r.signal.get("entry_price"),
            "target_price": r.signal.get("target_price"),
            "stop_price": r.signal.get("stop_price"),
            "risk_reward": r.signal.get("risk_reward"),
            "why_now": r.explanation.why_now if r.explanation else None,
            "why_not": (r.explanation.why_not_stronger if r.explanation else None),
            "invalidation": (r.explanation.invalidation if r.explanation else None),
        }
        if r.ranking:
            row["discovery_rank"] = r.ranking.discovery_rank
            row["action_rank"] = r.ranking.action_rank
            row["conviction_rank"] = r.ranking.conviction_rank
        if r.conflict:
            row["conflict_level"] = r.conflict.conflict_level
        # Runner-up comparison
        if i < min(limit, len(results)) - 1:
            nxt = results[i + 1]
            row["runner_up"] = {
                "ticker": nxt.signal.get("ticker"),
                "score": round(nxt.confidence.final, 2),
                "reason": f"{r.signal.get('ticker')} has higher conviction"
                f" ({round(r.confidence.final, 2)} vs"
                f" {round(nxt.confidence.final, 2)})",
            }
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


# ── Backtest: Scanner Picks vs Benchmark ─────────────────────────────


@router.get("/backtest-vs-benchmark")
async def backtest_vs_benchmark(
    period: str = Query("5y", description="1y/2y/5y"),
    benchmark: str = Query("SPY", description="SPY or QQQ"),
) -> Dict[str, Any]:
    """Compare hypothetical scanner top-pick returns vs SPY/QQQ.

    Uses RS leadership methodology: buy top-5 RS leaders monthly,
    equal-weight, rebalance monthly, compare to buy-and-hold benchmark.
    """
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance/pandas not available"}

    # RS leadership universe (top liquid names)
    universe = [
        "NVDA",
        "AAPL",
        "MSFT",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "AMD",
        "AVGO",
        "CRM",
        "NFLX",
        "ADBE",
        "NOW",
        "UBER",
        "PLTR",
        "PANW",
        "CRWD",
        "ANET",
        "XOM",
        "CVX",
        "LLY",
        "UNH",
        "JPM",
        "V",
    ]
    tickers = universe + [benchmark]

    try:
        data = yf.download(
            tickers,
            period=period,
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )
        if data.empty:
            return {"error": "No data returned from yfinance"}
        close = data["Close"].dropna(how="all")
    except Exception as e:
        return {"error": f"Data fetch failed: {e}"}

    if close.empty or len(close) < 3:
        return {"error": "Insufficient data"}

    # Monthly returns
    returns = close.pct_change().dropna()

    # RS ranking: 3-month rolling return
    rs_window = 3
    rolling_ret = close.pct_change(rs_window).dropna()

    # Strategy: each month, buy top-5 RS leaders, equal weight
    strategy_returns = []
    benchmark_returns = []
    months = []
    picks_history = []

    for i in range(rs_window, len(close) - 1):
        date_idx = close.index[i]
        next_idx = close.index[i + 1]

        # RS rank at this month
        rs_scores = {}
        for t in universe:
            if t in rolling_ret.columns:
                val = rolling_ret.loc[rolling_ret.index <= date_idx, t]
                if len(val) > 0 and pd.notna(val.iloc[-1]):
                    rs_scores[t] = val.iloc[-1]

        if len(rs_scores) < 5:
            continue

        # Top 5 leaders
        ranked = sorted(rs_scores.items(), key=lambda x: x[1], reverse=True)
        top5 = [t for t, _ in ranked[:5]]

        # Next month return for top5 (equal weight)
        port_ret = 0.0
        valid = 0
        for t in top5:
            if t in returns.columns:
                r_vals = returns.loc[returns.index <= next_idx, t]
                if len(r_vals) > 0 and pd.notna(r_vals.iloc[-1]):
                    port_ret += r_vals.iloc[-1]
                    valid += 1
        if valid > 0:
            port_ret /= valid

        # Benchmark return
        bm_ret = 0.0
        if benchmark in returns.columns:
            bm_vals = returns.loc[returns.index <= next_idx, benchmark]
            if len(bm_vals) > 0 and pd.notna(bm_vals.iloc[-1]):
                bm_ret = bm_vals.iloc[-1]

        strategy_returns.append(port_ret)
        benchmark_returns.append(bm_ret)
        months.append(str(next_idx.date()))
        picks_history.append(
            {
                "date": str(date_idx.date()),
                "picks": top5,
            }
        )

    if not strategy_returns:
        return {"error": "Not enough data for backtest"}

    # Cumulative returns
    strat_cum = 1.0
    bench_cum = 1.0
    strat_curve = [1.0]
    bench_curve = [1.0]
    for sr, br in zip(strategy_returns, benchmark_returns):
        strat_cum *= 1 + sr
        bench_cum *= 1 + br
        strat_curve.append(round(strat_cum, 4))
        bench_curve.append(round(bench_cum, 4))

    # Stats
    import statistics

    n = len(strategy_returns)
    strat_ann = (strat_cum ** (12.0 / n) - 1) if n > 0 else 0
    bench_ann = (bench_cum ** (12.0 / n) - 1) if n > 0 else 0
    strat_vol = statistics.stdev(strategy_returns) * (12**0.5) if n > 1 else 0
    bench_vol = statistics.stdev(benchmark_returns) * (12**0.5) if n > 1 else 0
    alpha = strat_ann - bench_ann
    win_months = sum(1 for s, b in zip(strategy_returns, benchmark_returns) if s > b)

    return {
        "period": period,
        "benchmark": benchmark,
        "months": n,
        "strategy": {
            "name": "RS Top-5 Leaders (Monthly Rebal)",
            "total_return": round((strat_cum - 1) * 100, 2),
            "annualized": round(strat_ann * 100, 2),
            "volatility": round(strat_vol * 100, 2),
            "sharpe": round(strat_ann / strat_vol, 2) if strat_vol > 0 else 0,
        },
        "benchmark_stats": {
            "total_return": round((bench_cum - 1) * 100, 2),
            "annualized": round(bench_ann * 100, 2),
            "volatility": round(bench_vol * 100, 2),
            "sharpe": round(bench_ann / bench_vol, 2) if bench_vol > 0 else 0,
        },
        "alpha_annualized": round(alpha * 100, 2),
        "win_rate_vs_benchmark": round(win_months / n * 100, 1) if n > 0 else 0,
        "equity_curve": {
            "dates": ["start"] + months,
            "strategy": strat_curve,
            "benchmark": bench_curve,
        },
        "recent_picks": picks_history[-6:],
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
