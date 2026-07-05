"""Rebalance simulator — preview trades vs target weights."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def simulate_rebalance(
    positions: List[Dict[str, Any]],
    *,
    policy: str = "equal_weight",
    max_single_pct: float = 0.12,
    target_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    total = sum(float(p.get("market_value") or 0) for p in positions) or 0.0
    if not positions or total <= 0:
        return {
            "feasible": False,
            "trades": [],
            "note": "No positions or zero book value",
        }
    n = len(positions)
    if target_weights:
        tw = {
            k.upper(): float(v)
            for k, v in target_weights.items()
            if k and float(v) >= 0
        }
        s = sum(tw.values()) or 1.0
        target_map = {k: v / s for k, v in tw.items()}
    else:
        target_map = None
    target_each = 1.0 / n
    trades: List[Dict[str, Any]] = []
    for p in positions:
        mv = float(p.get("market_value") or 0)
        current = mv / total
        drift = current - target_each
        ticker = (p.get("ticker") or "—").upper()
        if target_map is not None:
            target_each = target_map.get(ticker, 0.0)
            drift = current - target_each
        if abs(drift) < 0.02:
            continue
        notional = round(abs(drift) * total, 2)
        trades.append(
            {
                "ticker": ticker,
                "side": "SELL" if drift > 0 else "BUY",
                "notional_usd": notional,
                "current_weight_pct": round(current * 100, 2),
                "target_weight_pct": round(target_each * 100, 2),
                "drift_pct": round(drift * 100, 2),
            }
        )
    trades.sort(key=lambda x: -x["notional_usd"])
    return {
        "feasible": True,
        "policy": policy,
        "max_single_pct": max_single_pct,
        "trade_count": len(trades),
        "trades": trades[:20],
        "estimated_turnover_pct": round(
            sum(t["notional_usd"] for t in trades) / total * 50, 2
        ),
        "evidence": {
            "basis": "equal_weight_heuristic",
            "label": "Not execution advice — preview only",
        },
    }
