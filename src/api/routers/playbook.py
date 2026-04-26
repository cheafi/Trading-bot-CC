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
import statistics
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/playbook", tags=["playbook"])


# ── Real data access ─────────────────────────────────────────────────


async def _real_regime() -> Dict[str, Any]:
    """Get real regime from the engine (cached 60s in main)."""
    try:
        from src.api.main import _get_regime

        state = await _get_regime()
        return {
            "should_trade": getattr(state, "should_trade", True),
            "trend": getattr(state, "trend_regime", "sideways"),
            "vix": getattr(state, "vix", 18.0),
            "macro_trend": getattr(state, "trend_regime", "neutral"),
            "macro_event_nearby": False,
            "confidence": getattr(state, "confidence", 0.5),
        }
    except Exception as e:
        logger.warning("Regime fallback: %s", e)
        return {
            "should_trade": True,
            "trend": "NEUTRAL",
            "vix": 18.5,
            "macro_trend": "neutral",
            "macro_event_nearby": False,
        }


async def _real_signals() -> List[Dict[str, Any]]:
    """Get real signals from live scanner (cached 5min in main)."""
    try:
        from src.api.main import _scan_live_signals

        recs, _ = await _scan_live_signals(limit=50)
        return recs
    except Exception as e:
        logger.warning("Signals fallback: %s", e)
        return []


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

    regime = await _real_regime()
    signals = await _real_signals()

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
                "reason": (
                    f"Higher conviction"
                    f" ({round(r.confidence.final, 2)}"
                    f" vs {round(nxt.confidence.final, 2)})"
                    + (
                        ", better sector fit (" + r.sector.sector_bucket.value + ")"
                        if r.sector.sector_bucket != nxt.sector.sector_bucket
                        else ""
                    )
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
    regime = await _real_regime()
    signals = await _real_signals()

    results = pipeline.process_batch(signals, regime)

    # Filter
    if action:
        results = [r for r in results if r.decision.action == action.upper()]
    if sector:
        sb = sector.upper()
        results = [r for r in results if r.sector.sector_bucket.value == sb]

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
            "why_now": (r.explanation.why_now if r.explanation else None),
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
    category: str = Query(
        None,
        description="PATTERN/FLOW/SECTOR/RISK/VALIDATION",
    ),
) -> Dict[str, Any]:
    """Scanner matrix results grouped by category."""
    scanner = _get_scanner()
    regime = await _real_regime()
    signals = await _real_signals()

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
    regime = await _real_regime()

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
    regime = await _real_regime()

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
    regime = await _real_regime()
    signals = await _real_signals()

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


# ── Data builders for RS / Flow ──────────────────────────────────────


_RS_UNIVERSE = [
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

_SECTOR_MAP = {
    "NVDA": "Tech",
    "AAPL": "Tech",
    "MSFT": "Tech",
    "AMZN": "Consumer",
    "META": "Tech",
    "GOOGL": "Tech",
    "TSLA": "Consumer",
    "AMD": "Tech",
    "AVGO": "Tech",
    "CRM": "Tech",
    "NFLX": "Consumer",
    "ADBE": "Tech",
    "NOW": "Tech",
    "UBER": "Consumer",
    "PLTR": "Tech",
    "PANW": "Tech",
    "CRWD": "Tech",
    "ANET": "Tech",
    "XOM": "Energy",
    "CVX": "Energy",
    "LLY": "Health",
    "UNH": "Health",
    "JPM": "Finance",
    "V": "Finance",
}


async def _build_rs_universe() -> List[Dict[str, Any]]:
    """Build RS universe from real yfinance data."""
    try:
        import yfinance as yf

        data = yf.download(
            _RS_UNIVERSE + ["SPY"],
            period="6mo",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return []
        close = data["Close"]
        universe = []
        for t in _RS_UNIVERSE:
            if t not in close.columns:
                continue
            s = close[t].dropna()
            if len(s) < 4:
                continue
            price = float(s.iloc[-1])
            r1w = float((s.iloc[-1] / s.iloc[-2] - 1) * 100)
            ret4 = float((s.iloc[-1] / s.iloc[-4] - 1) * 100)
            r1m = ret4 if len(s) >= 5 else 0.0
            ret12 = float((s.iloc[-1] / s.iloc[-12] - 1) * 100)
            r3m = ret12 if len(s) >= 13 else r1m
            ret0 = float((s.iloc[-1] / s.iloc[0] - 1) * 100)
            r6m = ret0 if len(s) >= 20 else r3m
            universe.append(
                {
                    "ticker": t,
                    "sector": _SECTOR_MAP.get(t, "Other"),
                    "market_cap": "LARGE",
                    "price": price,
                    "return_1w": r1w,
                    "return_1m": r1m,
                    "return_3m": r3m,
                    "return_6m": r6m,
                }
            )
        return universe
    except Exception as e:
        logger.warning("RS universe build failed: %s", e)
        return []


async def _build_benchmark() -> Dict[str, Any]:
    """Build benchmark returns from SPY."""
    try:
        import yfinance as yf

        data = yf.download(
            "SPY",
            period="6mo",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return {}
        c = data["Close"].dropna()
        if len(c) < 4:
            return {}
        r1w = float((c.iloc[-1] / c.iloc[-2] - 1) * 100)
        r1m = float((c.iloc[-1] / c.iloc[-4] - 1) * 100) if len(c) >= 5 else 0.0
        r3m = float((c.iloc[-1] / c.iloc[-12] - 1) * 100) if len(c) >= 13 else 0.0
        r6m = float((c.iloc[-1] / c.iloc[0] - 1) * 100) if len(c) >= 20 else 0.0
        return {
            "return_1w": r1w,
            "return_1m": r1m,
            "return_3m": r3m,
            "return_6m": r6m,
        }
    except Exception as e:
        logger.warning("Benchmark build failed: %s", e)
        return {}


async def _build_flow_universe() -> List[Dict[str, Any]]:
    """Build flow universe from real yfinance data."""
    try:
        import yfinance as yf

        data = yf.download(
            _RS_UNIVERSE,
            period="3mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return []
        universe = []
        for t in _RS_UNIVERSE:
            try:
                c = data["Close"][t].dropna()
                v = data["Volume"][t].dropna()
                if len(c) < 20 or len(v) < 20:
                    continue
                avg_vol = float(v.iloc[-20:].mean())
                cur_vol = float(v.iloc[-1])
                universe.append(
                    {
                        "ticker": t,
                        "price": float(c.iloc[-1]),
                        "volume": cur_vol,
                        "avg_volume_20d": avg_vol,
                        "vol_ratio": (
                            round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                        ),
                        "close_5d": [float(x) for x in c.iloc[-5:]],
                        "volume_5d": [float(x) for x in v.iloc[-5:]],
                    }
                )
            except Exception:
                continue
        return universe
    except Exception as e:
        logger.warning("Flow universe build failed: %s", e)
        return []


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
    universe = await _build_rs_universe()
    benchmark = await _build_benchmark()

    entries = engine.rank(universe, benchmark)

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
    universe = await _build_flow_universe()

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
    for sr, br in zip(
        strategy_returns,
        benchmark_returns,
        strict=True,
    ):
        strat_cum *= 1 + sr
        bench_cum *= 1 + br
        strat_curve.append(round(strat_cum, 4))
        bench_curve.append(round(bench_cum, 4))

    # Stats
    n = len(strategy_returns)
    strat_ann = (strat_cum ** (12.0 / n) - 1) if n > 0 else 0
    bench_ann = (bench_cum ** (12.0 / n) - 1) if n > 0 else 0
    strat_vol = statistics.stdev(strategy_returns) * (12**0.5) if n > 1 else 0
    bench_vol = statistics.stdev(benchmark_returns) * (12**0.5) if n > 1 else 0
    alpha = strat_ann - bench_ann
    win_months = sum(
        1
        for s, b in zip(
            strategy_returns,
            benchmark_returns,
            strict=True,
        )
        if s > b
    )

    win_rate = round(win_months / n * 100, 1) if n > 0 else 0

    return {
        "period": period,
        "benchmark": benchmark,
        "months": n,
        "strategy": {
            "name": "RS Top-5 Leaders (Monthly Rebal)",
            "total_return": round((strat_cum - 1) * 100, 2),
            "annualized": round(strat_ann * 100, 2),
            "volatility": round(strat_vol * 100, 2),
            "sharpe": (round(strat_ann / strat_vol, 2) if strat_vol > 0 else 0),
        },
        "benchmark_stats": {
            "total_return": round((bench_cum - 1) * 100, 2),
            "annualized": round(bench_ann * 100, 2),
            "volatility": round(bench_vol * 100, 2),
            "sharpe": (round(bench_ann / bench_vol, 2) if bench_vol > 0 else 0),
        },
        "alpha_annualized": round(alpha * 100, 2),
        "win_rate_vs_benchmark": win_rate,
        "equity_curve": {
            "dates": ["start"] + months,
            "strategy": strat_curve,
            "benchmark": bench_curve,
        },
        "recent_picks": picks_history[-6:],
    }


def _get_signal_for_ticker(
    ticker: str,
) -> Dict[str, Any] | None:
    """Look up a ticker from cached scanner signals."""
    try:
        from src.api.main import _scan_cache

        for rec in _scan_cache.get("recs", []):
            if rec.get("ticker", "").upper() == ticker.upper():
                return rec
    except Exception:
        pass
    return {"ticker": ticker, "score": 5, "strategy": "scan"}
