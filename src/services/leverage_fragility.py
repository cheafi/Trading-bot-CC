"""
《乱世华尔街》leverage fragility — crowded books break together in stress.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

FRAGILITY_LABELS: Dict[str, str] = {
    "low": "Leverage fragility low — dispersion still possible",
    "elevated": "Elevated fragility — correlation rising",
    "high": "High fragility — one macro shock moves the book",
    "extreme": "Extreme fragility — de-gross before adding risk",
}


def evaluate_leverage_fragility(
    *,
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    top_concentration_pct: Optional[float] = None,
    heat_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Book-level leverage/crowding fragility heuristics."""
    vix_f = float(vix) if vix is not None else 0.0
    breadth_f = float(breadth) if breadth is not None else 50.0
    top_pct = float(top_concentration_pct) if top_concentration_pct is not None else 0.0
    heat = float(heat_pct) if heat_pct is not None else 0.0

    labels: List[str] = []
    tier = "low"
    score = 80.0

    if vix_f >= 30 or (breadth_f < 28 and top_pct > 15):
        tier = "extreme"
        score = 10.0
        labels.append(FRAGILITY_LABELS["extreme"])
    elif vix_f >= 24 or breadth_f < 38 or top_pct > 12 or heat > 6:
        tier = "high"
        score = 30.0
        labels.append(FRAGILITY_LABELS["high"])
    elif vix_f >= 18 or top_pct > 10:
        tier = "elevated"
        score = 55.0
        labels.append(FRAGILITY_LABELS["elevated"])
    else:
        labels.append(FRAGILITY_LABELS["low"])

    return {
        "tier": tier,
        "fragility_score": round(score, 1),
        "labels": labels,
        "headline": labels[0],
        "correlation_warning": tier in ("high", "extreme"),
    }
