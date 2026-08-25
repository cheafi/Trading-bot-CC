"""
《纳瓦尔宝典》signal-to-noise — act only when clarity earns bandwidth.

Five bands: act_now · think_deeply · monitor_lightly · ignore · noise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SIGNAL_LEVELS = ("act_now", "think_deeply", "monitor_lightly", "ignore", "noise")

SIGNAL_LABELS: Dict[str, str] = {
    "act_now": "act now — edge clear, gates open",
    "think_deeply": "think deeply — thesis worth study, not urgency",
    "monitor_lightly": "monitor lightly — bookmark, no daily churn",
    "ignore": "ignore for today — board or setup does not earn focus",
    "noise": "noise — score theater without deploy path",
}


def classify_signal_to_noise(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Map row + board context to a single signal band."""
    tb = (
        tradeability or row.get("tradeability") or row.get("honest_tradeability") or ""
    ).upper()
    action = (row.get("action") or "").upper()
    score = float(row.get("score") or row.get("validated_score") or 0)
    thesis = float(row.get("thesis_conf") or row.get("thesis_quality") or 0)
    exec_ready = bool(row.get("execution_ready"))
    net = row.get("net_deploy_score") or row.get("net_edge_score")

    if tb in ("NO_TRADE", "WAIT") and action not in ("TRADE", "PILOT"):
        level = "ignore" if score < 7 else "monitor_lightly"
        if tb == "NO_TRADE":
            level = "ignore"
    elif action == "TRADE" and exec_ready and thesis >= 0.65 and deployable_count > 0:
        level = "act_now"
    elif action == "PILOT" and thesis >= 0.55:
        level = "think_deeply"
    elif action in ("WATCH", "WAIT") and thesis >= 0.5 and score >= 6.5:
        level = "monitor_lightly"
    elif score >= 7 and thesis < 0.45:
        level = "noise"
    elif net is not None and float(net) < 5.5 and score >= 7:
        level = "noise"
    elif score < 5.5:
        level = "ignore"
    else:
        level = "monitor_lightly"

    return {
        "level": level,
        "label": SIGNAL_LABELS[level],
        "action_necessity": (
            "required"
            if level == "act_now"
            else "optional"
            if level == "think_deeply"
            else "none"
        ),
        "preserve_focus": level in ("ignore", "noise", "monitor_lightly"),
    }


def tags_for_playbook_row(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    deployable_count: int = 0,
) -> Dict[str, Any]:
    sn = classify_signal_to_noise(
        row, tradeability=tradeability, deployable_count=deployable_count
    )
    return {
        "signal_to_noise": sn["level"],
        "signal_to_noise_label": sn["label"],
    }


def what_matters_today(
    opportunities: Optional[List[Dict[str, Any]]] = None,
    *,
    tradeability: str = "",
    deployable_count: int = 0,
    limit: int = 3,
) -> List[Dict[str, str]]:
    """Top names that earn mental bandwidth today — not the full scanner."""
    out: List[Dict[str, str]] = []
    for row in opportunities or []:
        sn = classify_signal_to_noise(
            row, tradeability=tradeability, deployable_count=deployable_count
        )
        if sn["level"] in ("act_now", "think_deeply"):
            out.append(
                {
                    "ticker": str(row.get("ticker") or "—"),
                    "band": sn["level"],
                    "label": sn["label"],
                }
            )
        if len(out) >= limit:
            break
    return out
