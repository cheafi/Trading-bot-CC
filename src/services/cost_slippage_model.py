"""
Cost Slippage Model — spread/volume/ATR/liquidity → cost_drag_r and cost-adjusted expected R.

Heuristic model for ranking humility; not live TCA. Never inflates deploy-qualified counts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.cost_adjusted_edge import infer_burdens_from_row


def _float(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def estimate_spread_bps(row: Dict[str, Any]) -> float:
    """Estimate half-spread burden in bps from liquidity proxies."""
    base = 8.0
    liq = _float(row.get("liquidity_score"), 0.5) or 0.5
    vol = _float(row.get("avg_volume") or row.get("volume"), 1_000_000) or 1_000_000
    if vol < 200_000:
        base += 18.0
    elif vol < 500_000:
        base += 10.0
    elif vol < 2_000_000:
        base += 4.0
    if liq < 0.35:
        base += 12.0
    elif liq < 0.55:
        base += 6.0
    burdens = infer_burdens_from_row(row)
    base += burdens.get("spread_burden", 0.15) * 20.0
    return round(min(80.0, base), 1)


def estimate_slippage_bps(row: Dict[str, Any], *, atr_pct: Optional[float] = None) -> float:
    """ATR/volatility-linked slippage estimate in bps."""
    atr = atr_pct if atr_pct is not None else _float(row.get("atr_pct") or row.get("atr_percent"))
    if atr is None:
        atr = 2.5
    slip = max(5.0, float(atr) * 4.0)
    if row.get("extended") or row.get("timing_extended"):
        slip += 8.0
    vol = _float(row.get("avg_volume") or row.get("volume"), 1_000_000) or 1_000_000
    if vol < 300_000:
        slip += 10.0
    return round(min(60.0, slip), 1)


def cost_drag_r(
    row: Dict[str, Any],
    *,
    expected_r: Optional[float] = None,
    notional_usd: float = 25_000.0,
) -> Dict[str, Any]:
    """
    Convert spread + slippage bps into R drag using stop distance proxy.

    Uses risk_reward and score as rough stop-distance heuristic when ATR missing.
    """
    spread_bps = estimate_spread_bps(row)
    slip_bps = estimate_slippage_bps(row)
    total_bps = spread_bps + slip_bps
    rr = _float(row.get("risk_reward") or row.get("rr_ratio"), 2.0) or 2.0
    stop_pct = max(0.8, min(8.0, 3.0 / max(rr, 0.5)))
    round_trip_cost_pct = (total_bps / 10_000.0) * 2.0
    drag_r = round((round_trip_cost_pct / (stop_pct / 100.0)), 2)
    exp_r = expected_r if expected_r is not None else _float(row.get("expected_r"), 0.0) or 0.0
    net_r = round(max(-3.0, exp_r - drag_r), 2)
    return {
        "spread_bps": spread_bps,
        "slippage_bps": slip_bps,
        "total_cost_bps": round(total_bps * 2, 1),
        "cost_drag_r": drag_r,
        "gross_expected_r": exp_r if exp_r else None,
        "cost_adjusted_expected_r": {
            "low": None if exp_r == 0 else round(net_r - 0.4, 1),
            "high": None if exp_r == 0 else round(net_r + 0.2, 1),
            "point": net_r if exp_r else None,
            "display": "learning" if exp_r == 0 else f"{net_r}R net",
        },
        "model_note": "Heuristic spread/ATR/liquidity model — not live TCA",
        "may_authorize_deploy": False,
    }


def estimate_cost_adjusted_r(
    row: Dict[str, Any],
    *,
    expected_r: Optional[float] = None,
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Primary API for opportunity calibration."""
    _ = truth  # reserved for brief-expired widening
    result = cost_drag_r(row, expected_r=expected_r)
    return {
        "cost_drag_r": result["cost_drag_r"],
        "cost_adjusted_expected_r": result["cost_adjusted_expected_r"],
        "spread_bps": result["spread_bps"],
        "slippage_bps": result["slippage_bps"],
        "model_note": result["model_note"],
    }
