"""
《纳瓦尔宝典》leverage — process / automation / judgment labels.

Naval: earn with code, media, capital, or labor — prefer judgment + process leverage.
"""

from __future__ import annotations

from typing import Any, Dict

LEVERAGE_TYPES = ("process", "automation", "judgment", "labor")

LEVERAGE_LABELS: Dict[str, str] = {
    "process": "process leverage — repeatable rules beat daily heroics",
    "automation": "automation leverage — let the board gate and scanner run",
    "judgment": "judgment leverage — few high-conviction decisions",
    "labor": "labor leverage — manual churn; avoid unless edge is clear",
}


def label_leverage(row: Dict[str, Any], *, surface: str = "playbook") -> Dict[str, Any]:
    action = (row.get("action") or "").upper()
    exec_ready = bool(row.get("execution_ready"))
    thesis = float(row.get("thesis_conf") or 0)

    if surface == "today" or (action in ("WAIT", "NO_TRADE") and not exec_ready):
        primary = "process"
    elif exec_ready and thesis >= 0.65:
        primary = "judgment"
    elif action == "PILOT":
        primary = "judgment"
    elif surface in ("playbook", "dossier") and row.get("score"):
        primary = "automation"
    else:
        primary = "labor"

    secondary = "process" if primary != "process" else "automation"

    return {
        "primary": primary,
        "secondary": secondary,
        "label": LEVERAGE_LABELS[primary],
        "guidance": (
            "Use judgment sparingly — one clear decision beats ten tweaks"
            if primary == "judgment"
            else "Trust the process — do not force trades for activity"
        ),
    }
