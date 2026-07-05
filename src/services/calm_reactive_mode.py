"""
《纳瓦尔宝典》calm vs reactive — peace cost and false urgency detection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.leverage_engine import label_leverage


def evaluate_calm_reactive(
    *,
    tradeability: str = "",
    deployable_count: int = 0,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    vix: Optional[float] = None,
) -> Dict[str, Any]:
    """Detect when the UI or market is pushing false urgency."""
    tb = (tradeability or "").upper()
    high_score_count = sum(
        1 for r in (opportunities or []) if float(r.get("score") or 0) >= 7.5
    )
    vix_f = float(vix) if vix is not None else 0.0

    false_urgency = False
    if tb in ("WAIT", "NO_TRADE") and high_score_count >= 2:
        false_urgency = True
    if deployable_count == 0 and high_score_count >= 3:
        false_urgency = True
    if vix_f > 28 and deployable_count == 0 and high_score_count >= 1:
        false_urgency = True

    peace_cost = "high" if false_urgency else "medium" if tb == "WAIT" else "low"
    preserve_focus = tb in ("WAIT", "NO_TRADE") or deployable_count == 0

    lev = label_leverage({"action": tb, "execution_ready": deployable_count > 0}, surface="today")

    if false_urgency:
        headline = "False urgency detected — high scores without deploy path"
        banner = "Peace is the position. No action required until board opens."
        signal_light = "ignore"
    elif preserve_focus:
        headline = "Calm mode — preserve bandwidth for what compounds"
        banner = "Monitor lightly. Reacting to noise has a peace cost."
        signal_light = "monitor_lightly"
    else:
        headline = "Selective calm — act only where judgment leverage applies"
        banner = f"{deployable_count} deploy-grade name(s) — ignore the rest"
        signal_light = "think_deeply"

    return {
        "mode": "calm",
        "false_urgency": false_urgency,
        "peace_cost": peace_cost,
        "preserve_focus": preserve_focus,
        "headline": headline,
        "banner": banner,
        "signal_light": signal_light,
        "leverage_hint": lev["label"],
    }
