"""Composite cross-market backtests and run cards (research only)."""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

import pandas as pd

from src.research.backtrader_bridge import run_sma_cross_backtest
from src.services.research_safety import sanitize_research_payload


def _truncate_history_as_of(df, as_of: Optional[str]):
    if not as_of or df is None or getattr(df, "empty", True):
        return df, False
    try:
        cut = pd.to_datetime(str(as_of)[:10])
        idx = pd.to_datetime(df.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert(None)
        mask = idx <= cut
        out = df.loc[mask]
        return (out if not out.empty else df), True
    except Exception:
        return df, False


async def run_composite_backtest(
    mds,
    symbols: List[str],
    *,
    period: str = "1y",
    fast: int = 10,
    slow: int = 30,
    strategy_label: str = "sma_cross_composite",
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the same research strategy on multiple symbols; aggregate run card."""
    legs: List[Dict[str, Any]] = []
    returns: List[float] = []
    for raw in symbols[:8]:
        sym = str(raw or "").strip().upper()
        if not sym:
            continue
        try:
            hist = await mds.get_history(sym, period=period, interval="1d")
        except Exception as exc:
            legs.append(
                {"ticker": sym, "ok": False, "error": type(exc).__name__}
            )
            continue
        if hist is None or getattr(hist, "empty", True):
            legs.append({"ticker": sym, "ok": False, "error": "no_history"})
            continue
        pit_applied = False
        hist_use = hist
        if as_of:
            hist_use, pit_applied = _truncate_history_as_of(hist, as_of)
        leg = run_sma_cross_backtest(hist_use, fast=fast, slow=slow)
        leg["ticker"] = sym
        leg["pit_truncated"] = pit_applied
        legs.append(leg)
        if leg.get("ok") and leg.get("total_return_pct") is not None:
            try:
                returns.append(float(leg["total_return_pct"]))
            except (TypeError, ValueError):
                pass

    ok_legs = [l for l in legs if l.get("ok")]
    agg_return = round(statistics.mean(returns), 2) if returns else None
    run_card = {
        "schema": "cc.run_card.v1",
        "strategy": strategy_label,
        "period": period,
        "symbols": [l.get("ticker") for l in ok_legs],
        "leg_count": len(legs),
        "ok_count": len(ok_legs),
        "aggregate_return_pct": agg_return,
        "pit_data": bool(as_of),
        "as_of": as_of,
        "pit_note": (
            f"Bars truncated through {as_of} (research PIT mode)."
            if as_of
            else "Bars are latest-available from live/cache feeds — not point-in-time audited."
        ),
        "validation": {
            "min_legs_ok": len(ok_legs) >= 1,
            "composite_ready": len(ok_legs) >= 2,
            "warnings": [] if ok_legs else ["no_successful_legs"],
        },
    }
    if len(ok_legs) == 1:
        run_card["validation"]["warnings"].append("single_leg_composite")

    from src.services.pit_fundamental_pack import build_pit_fundamental_context

    pit_fund = build_pit_fundamental_context(
        [l.get("ticker") for l in ok_legs if l.get("ticker")],
        as_of=as_of,
    )
    if pit_fund.get("applied"):
        run_card["pit_fundamental"] = pit_fund

    return sanitize_research_payload(
        {
            "ok": bool(ok_legs),
            "run_card": run_card,
            "legs": legs,
            "pit_fundamental": pit_fund if pit_fund.get("applied") else None,
            "authority": "research_only",
            "execution_permission": False,
        }
    )


def attach_run_card_to_draft(
    draft: Dict[str, Any], run_card: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge run card metrics into strategy draft for export."""
    out = dict(draft)
    out["lastRunCard"] = run_card
    if run_card.get("aggregate_return_pct") is not None:
        out.setdefault("backtestSummary", {})["composite_return_pct"] = run_card[
            "aggregate_return_pct"
        ]
    return out
