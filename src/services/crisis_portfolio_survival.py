"""
《乱世华尔街》portfolio survival — optionality, crowding, and preservation score.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.leverage_fragility import evaluate_leverage_fragility


def evaluate_crisis_portfolio_survival(
    *,
    positions: Optional[List[Dict[str, Any]]] = None,
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    deploy_blocked: bool = False,
    heat_pct: Optional[float] = None,
    cash_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Survival layer for portfolio decision console."""
    positions = positions or []
    n = len(positions)
    total_mv = sum(float(p.get("market_value") or 0) for p in positions)
    top_pct = 0.0
    if total_mv > 0 and positions:
        top_pct = max((float(p.get("market_value") or 0) / total_mv) * 100 for p in positions)

    frag = evaluate_leverage_fragility(
        vix=vix,
        breadth=breadth,
        top_concentration_pct=top_pct,
        heat_pct=heat_pct,
    )

    survival_score = 70.0
    if deploy_blocked:
        survival_score -= 25
    if frag["tier"] in ("high", "extreme"):
        survival_score -= 20
    if (heat_pct or 0) > 6:
        survival_score -= 15
    if n <= 1 and total_mv > 0:
        survival_score -= 10
    survival_score = max(0.0, min(100.0, survival_score))

    optionality = "high" if n >= 4 and top_pct < 12 else "medium" if n >= 2 else "low"
    crowding = "elevated" if frag["correlation_warning"] else "normal"

    posture = "preservation" if deploy_blocked or survival_score < 45 else "balanced"
    if survival_score >= 70 and not deploy_blocked:
        posture = "selective_attack"

    copy = (
        "Survival first — reduce heat and raise cash before new risk"
        if posture == "preservation"
        else (
            "Selective attack only — small size with confirmed liquidity"
            if posture == "selective_attack"
            else "Balanced — monitor liquidity and concentration"
        )
    )

    return {
        "survival_score": round(survival_score, 1),
        "optionality": optionality,
        "crisis_crowding": crowding,
        "posture": posture,
        "headline": copy,
        "fragility": frag,
        "position_count": n,
        "top_concentration_pct": round(top_pct, 1),
        "capital_preservation_priority": posture != "selective_attack",
    }
