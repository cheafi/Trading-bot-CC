"""Benchmark context for strategy backtests (research only)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from src.services.research_safety import sanitize_research_payload


async def spy_buy_hold_context(
    mds,
    *,
    period: str = "1y",
    strategy_return_pct: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        hist = await mds.get_history("SPY", period=period, interval="1d")
    except Exception as exc:
        return {"ok": False, "benchmark": "SPY", "error": type(exc).__name__}
    if hist is None or getattr(hist, "empty", True):
        return {"ok": False, "benchmark": "SPY", "error": "no_bars"}
    col = "Close" if "Close" in hist.columns else "close"
    close = hist[col].astype(float)
    ret = round((float(close.iloc[-1]) / float(close.iloc[0]) - 1.0) * 100.0, 2)
    out: Dict[str, Any] = {
        "ok": True,
        "benchmark": "SPY",
        "period": period,
        "buy_hold_return_pct": ret,
        "bars": len(close),
        "authority": "research_only",
    }
    if strategy_return_pct is not None:
        out["excess_vs_spy_pct"] = round(float(strategy_return_pct) - ret, 2)
    return sanitize_research_payload(out)


async def attach_benchmark_to_backtest(
    mds,
    *,
    period: str,
    run_card: Dict[str, Any],
) -> Dict[str, Any]:
    strat_ret = run_card.get("aggregate_return_pct")
    bench = await spy_buy_hold_context(
        mds, period=period, strategy_return_pct=strat_ret
    )
    regime = {}
    try:
        from src.services.regime_service import RegimeService

        regime = RegimeService.get()
    except Exception:
        pass
    return sanitize_research_payload(
        {
            "benchmark_context": bench,
            "regime_snapshot": {
                "label": regime.get("label") or regime.get("regime_label"),
                "should_trade": regime.get("should_trade"),
                "stale": regime.get("stale"),
            },
        }
    )
