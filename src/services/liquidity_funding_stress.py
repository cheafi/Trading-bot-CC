"""
《乱世华尔街》liquidity & funding stress — when size and exit matter more than edge.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

LIQUIDITY_LABELS: Dict[str, str] = {
    "calm": "Liquidity adequate — normal depth assumptions",
    "thin": "Bid-ask stress — size down, avoid market orders",
    "funding_tight": "Funding stress — carry and margin dominate",
    "liquidity_trap": "Liquidity trap — exits may gap; preservation first",
}


def evaluate_liquidity_funding_stress(
    *,
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    tradeability: str = "",
    entropy: Optional[float] = None,
) -> Dict[str, Any]:
    """Heuristic liquidity/funding posture from regime fields on /today."""
    vix_f = float(vix) if vix is not None else 0.0
    breadth_f = float(breadth) if breadth is not None else 50.0
    ent = float(entropy) if entropy is not None else 0.5
    tb = (tradeability or "").upper()

    state = "calm"
    labels = [LIQUIDITY_LABELS["calm"]]
    score = 85.0

    if vix_f >= 32 or tb == "NO_TRADE":
        state = "liquidity_trap"
        score = 15.0
        labels = [LIQUIDITY_LABELS["liquidity_trap"]]
    elif vix_f >= 26 or breadth_f < 30:
        state = "funding_tight"
        score = 35.0
        labels = [LIQUIDITY_LABELS["funding_tight"]]
    elif vix_f >= 20 or breadth_f < 40 or ent > 0.72:
        state = "thin"
        score = 55.0
        labels = [LIQUIDITY_LABELS["thin"]]

    return {
        "state": state,
        "liquidity_state": state,
        "score": round(score, 1),
        "labels": labels,
        "headline": labels[0],
        "size_multiplier": {
            "calm": 1.0,
            "thin": 0.6,
            "funding_tight": 0.35,
            "liquidity_trap": 0.0,
        }[state],
    }
