"""Weekly Investment Committee digest (CCX-136)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.daily_ic_summary import build_daily_ic_summary


def build_weekly_ic_digest(*, board: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One-page weekly IC — extends daily summary with review prompts."""
    daily = build_daily_ic_summary(board=board)
    system = (board or {}).get("system_state") or {}
    best = (board or {}).get("best_action") or {}

    sections = [
        {
            "key": "regime",
            "title": "Regime review",
            "prompt": "Did regime change this week? Does posture still fit?",
        },
        {
            "key": "portfolio",
            "title": "Portfolio health",
            "prompt": "Concentration, sector overlap, cash %, trap flags?",
        },
        {
            "key": "beliefs",
            "title": "Active beliefs",
            "prompt": "Top holdings — thesis intact? Kill conditions near?",
        },
        {
            "key": "queue",
            "title": "Opportunity queue",
            "prompt": "Monitor vs deploy-qualified — quality not rank?",
        },
        {
            "key": "mistake",
            "title": "Mistake of the week",
            "prompt": "One error — process or outcome?",
        },
        {
            "key": "lesson",
            "title": "One lesson",
            "prompt": "What enters Knowledge Engine?",
        },
    ]

    return {
        "authority": "research_only",
        "cadence": "weekly",
        "daily_ic": daily,
        "sections": sections,
        "deploy_open": bool(system.get("deploy_open")),
        "best_trade": best.get("best_trade") or best.get("ticker"),
        "headline": daily.get("mission", {}).get("stance_one_liner")
        or "Weekly IC — review process, not prediction.",
        "one_action": "Assign max 2 deep-research slots for next week.",
    }
