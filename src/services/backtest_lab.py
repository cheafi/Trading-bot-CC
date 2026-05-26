"""Backtest lab — attribution, walk-forward, trade-level review."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.services.p2_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

_CACHE_ATTR = "backtest_lab_cache"


async def build_backtest_lab(
    request,
    *,
    ticker: str,
    strategy: str = "all",
    period: str = "2y",
    walk_forward: bool = True,
) -> Dict[str, Any]:
    """Full lab report wrapping live backtest + walk-forward + trade review."""
    sym = ticker.upper()
    cache_key = f"{sym}_{strategy}_{period}_{walk_forward}"
    cached = get_cached(request.app.state, f"{_CACHE_ATTR}_{cache_key}")
    if cached is not None:
        return cached

    from src.api.routers.live_backtest import live_backtest

    core = await live_backtest(
        request,
        ticker=sym,
        strategy=strategy,
        period=period,
    )
    wf = (
        await _walk_forward_summary(request, sym, strategy, period)
        if walk_forward
        else {"windows": [], "stability_score": 0, "verdict": "skipped", "note": "walk_forward=false"}
    )
    trade_review = _trade_level_review(core)
    attribution = _strategy_attribution(core)

    result = {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "ticker": sym,
        "strategy": strategy,
        "period": period,
        "core_backtest": core,
        "walk_forward": wf,
        "trade_level_review": trade_review,
        "attribution": attribution,
        "evidence": {
            "basis": "backtest",
            "label": "Historical simulation — gross, no fees/slippage",
            "trust": core.get("trust"),
        },
    }
    set_cached(request.app.state, f"{_CACHE_ATTR}_{cache_key}", result, ttl_sec=300)
    return result


async def _walk_forward_summary(
    request,
    ticker: str,
    strategy: str,
    period: str,
) -> Dict[str, Any]:
    """Rolling windows — parallel backtests for speed."""
    windows = [("6mo", "recent"), ("1y", "1y")]
    if period not in ("6mo",):
        windows.append(("2y", "2y"))

    from src.api.routers.live_backtest import live_backtest

    async def _one(p: str, label: str):
        try:
            res = await live_backtest(
                request, ticker=ticker.upper(), strategy=strategy, period=p
            )
            best = res.get("best_strategy") or {}
            return {
                "window": label,
                "period": p,
                "best_strategy": best.get("name"),
                "return_pct": best.get("total_return_pct"),
                "win_rate": best.get("win_rate"),
                "sharpe": best.get("sharpe"),
                "max_dd": best.get("max_drawdown"),
                "trades": best.get("total_trades"),
                "vs_benchmark": best.get("vs_benchmark"),
            }
        except Exception as exc:
            return {"window": label, "error": str(exc)[:80]}

    rows = await asyncio.gather(*[_one(p, lbl) for p, lbl in windows])
    rows = list(rows)
    stable = len([r for r in rows if (r.get("return_pct") or 0) > 0])
    return {
        "windows": rows,
        "stability_score": round(stable / max(len(rows), 1) * 100),
        "verdict": (
            "stable_across_windows"
            if stable >= 2
            else "unstable" if rows
            else "insufficient_data"
        ),
        "note": "Windows run in parallel — compare consistency not single fit",
    }


def _trade_level_review(core: Dict[str, Any]) -> Dict[str, Any]:
    """Trade-level stats from best strategy."""
    strategies = core.get("strategies") or []
    best_name = (core.get("best_strategy") or {}).get("name")
    best = next((s for s in strategies if s.get("name") == best_name), None)
    if not best:
        return {"trades": [], "summary": "No strategy trades", "trade_count": 0}
    trades = best.get("trades") or best.get("all_trades") or []
    if not trades and best.get("sample_trades"):
        trades = best["sample_trades"]
    wins = [t for t in trades if float(t.get("pnl_pct", 0)) > 0]
    losses = [t for t in trades if float(t.get("pnl_pct", 0)) <= 0]
    sorted_trades = sorted(
        trades, key=lambda t: float(t.get("pnl_pct", 0)), reverse=True
    )
    return {
        "strategy": best_name,
        "trade_count": len(trades),
        "win_rate": round(len(wins) / max(len(trades), 1) * 100, 1),
        "avg_win_pct": round(
            sum(float(t.get("pnl_pct", 0)) for t in wins) / max(len(wins), 1), 2
        ),
        "avg_loss_pct": round(
            sum(float(t.get("pnl_pct", 0)) for t in losses) / max(len(losses), 1), 2
        ),
        "best_trades": sorted_trades[:5],
        "worst_trades": sorted_trades[-5:][::-1] if sorted_trades else [],
        "holding_days_avg": round(
            sum(int(t.get("hold_days", t.get("days", 0)) or 0) for t in trades)
            / max(len(trades), 1),
            1,
        ),
    }


def _strategy_attribution(core: Dict[str, Any]) -> Dict[str, Any]:
    """Which strategy contributed most to simulated edge."""
    strategies = core.get("strategies") or []
    ranked = sorted(
        strategies,
        key=lambda s: float(s.get("total_return_pct") or s.get("return_pct") or 0),
        reverse=True,
    )
    return {
        "benchmark_return_pct": core.get("benchmark_return"),
        "ranked": [
            {
                "name": s.get("name"),
                "return_pct": s.get("total_return_pct", s.get("return_pct")),
                "sharpe": s.get("sharpe"),
                "trades": s.get("total_trades", s.get("trades")),
                "contribution_note": "Standalone strategy run — not blended portfolio",
            }
            for s in ranked[:6]
        ],
        "selection_effect_note": "Pick best strategy vs buy-hold benchmark",
    }
