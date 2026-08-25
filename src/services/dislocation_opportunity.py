"""
《乱世华尔街》dislocation taxonomy — panic, repair, dead-cat; not all selloffs are buys.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.utils.numeric_parse import coerce_float

DISLOCATION_LABELS: Dict[str, str] = {
    "panic": "Panic dislocation — preservation first, no hero entries",
    "repair": "Repair phase — confirmation only, small size",
    "dead_cat": "Dead-cat bounce risk — do not chase relief rallies",
    "none": "No dislocation signal — routine regime rules apply",
}


def classify_dislocation(
    *,
    vix: Optional[float] = None,
    change_pct: Optional[float] = None,
    breadth: Optional[float] = None,
    should_trade: bool = True,
) -> Dict[str, Any]:
    """Ticker- or market-level dislocation class."""
    vix_f = float(vix) if vix is not None else 0.0
    chg = coerce_float(change_pct, 0.0)
    breadth_f = float(breadth) if breadth is not None else 50.0

    if vix_f >= 28 and not should_trade:
        kind = "panic"
    elif vix_f >= 22 and chg > 2.5 and breadth_f < 40:
        kind = "dead_cat"
    elif vix_f >= 20 and breadth_f < 45 and chg < -1.5:
        kind = "repair"
    else:
        kind = "none"

    return {
        "kind": kind,
        "label": DISLOCATION_LABELS[kind],
        "headline": DISLOCATION_LABELS[kind],
        "attack_allowed": kind in ("none", "repair") and should_trade,
    }


def dislocation_for_row(
    row: Dict[str, Any], *, market_vix: Optional[float] = None
) -> Dict[str, Any]:
    """Playbook row helper."""
    return classify_dislocation(
        vix=row.get("vix") or market_vix,
        change_pct=row.get("change_pct") or row.get("pct_change"),
        breadth=row.get("breadth"),
        should_trade=bool(row.get("should_trade", True)),
    )
