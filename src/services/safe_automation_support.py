"""
Safe automation support — workflow helpers without auto-deploy or gate bypass.

All outputs are monitor-only suggestions; operator retains Dashboard / Playbook authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_SAFE_AUTOMATION,
    build_provenance_envelope,
)
from src.services.today_insights import (
    build_opportunity_recheck_heuristic,
    detect_monitor_upgrade_gap_alerts,
)


def build_monitor_upgrade_alert_engine(
    near_miss: List[Dict[str, Any]],
    *,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    alerts = detect_monitor_upgrade_gap_alerts(near_miss, prior_near_miss=prior_near_miss)
    return {
        "engine": "monitor_upgrade_alert",
        "alert_count": len(alerts),
        "alerts": alerts,
        "monitoring_only": True,
        "may_authorize_deploy": False,
        "operator_action": "Review upgrade watch on Dashboard — board gate still required",
    }


def build_near_miss_auto_recheck(
    near_miss: List[Dict[str, Any]],
    *,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    hints = build_opportunity_recheck_heuristic(
        near_miss=near_miss,
        prior_near_miss=prior_near_miss,
    )
    return {
        "engine": "near_miss_auto_recheck",
        "hint_count": len(hints),
        "hints": hints,
        "monitoring_only": True,
        "may_authorize_deploy": False,
        "no_auto_deploy": True,
    }


def build_daily_operator_briefing(
    *,
    tradeability: str = "WAIT",
    narrative: str = "",
    near_miss_count: int = 0,
    deployable_count: int = 0,
    monitor_trigger_count: int = 0,
    ibkr_connected: bool = False,
    degraded: bool = False,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Structured AM briefing — triage order, not a deploy decision."""
    tb = str(tradeability or "").upper()
    safe_actions: List[str] = []
    blocked_actions: List[str] = []

    if degraded:
        safe_actions.append("Dossier core-only · Guide checklist · retry when data fresh")
        blocked_actions.append("Sizing or IBKR handoff from degraded fallback")
    elif tb == "WAIT":
        safe_actions.append("Upgrade-watch queue · Discovery ranking · Playbook sort review")
        blocked_actions.append("New deploy without tradeability lift + board gate")
    elif tb in ("TRADE", "SELECTIVE") and deployable_count > 0:
        safe_actions.append(
            f"{deployable_count} execution-ready — confirm on Dashboard before handoff"
        )
        blocked_actions.append("Deploy from research tabs or tracker alerts alone")
    else:
        safe_actions.append("Monitor queue · near-miss recheck · Funds allocator research")
        blocked_actions.append("Pilot sizing without board confirmation")

    if not ibkr_connected:
        blocked_actions.append("IBKR execution — connect before live handoff")

    cluster_lines = [
        str(h.get("label") or "") + ": " + str(h.get("detail") or "")
        for h in (quant_cluster_hints or [])
        if h.get("label")
    ]

    sections = [
        {
            "heading": "Board posture",
            "lines": [narrative or f"Tradeability {tb} — board gate applies"],
        },
        {
            "heading": "Safe now",
            "lines": safe_actions,
        },
        {
            "heading": "Blocked without gate",
            "lines": blocked_actions,
        },
    ]
    if near_miss_count:
        sections.append(
            {
                "heading": "Upgrade watch",
                "lines": [
                    f"{near_miss_count} near-miss candidates — monitor-to-upgrade only"
                ],
            }
        )
    if monitor_trigger_count:
        sections.append(
            {
                "heading": "Monitor triggers",
                "lines": [f"{monitor_trigger_count} active triggers — not deploy"],
            }
        )
    if cluster_lines:
        sections.append({"heading": "Quant clusters", "lines": cluster_lines[:4]})

    return {
        "briefing_type": "daily_operator",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "tradeability": tb,
        "degraded": degraded,
        "sections": sections,
        "one_liner": safe_actions[0] if safe_actions else "Monitor-only day",
        "may_authorize_deploy": False,
        "is_board_decision": False,
    }


def build_monitor_queue_aging(
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    *,
    near_miss: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Escalation hints when monitor queue is deep — workflow only."""
    triggers = list(monitor_triggers or [])
    nm = list(near_miss or [])
    depth = len(triggers) + len(nm)
    if depth >= 5:
        level = "high"
        label = f"Monitor queue depth {depth} — triage order on Dashboard"
    elif depth >= 2:
        level = "moderate"
        label = f"Monitor queue depth {depth} — review upgrade watch"
    else:
        level = "low"
        label = "Monitor queue light — standard workflow"
    return {
        "depth": depth,
        "level": level,
        "label": label,
        "may_authorize_deploy": False,
        "escalation_only": True,
    }


def build_research_staleness_alerts(
    *,
    degraded: bool = False,
    scanner_degraded: bool = False,
) -> Dict[str, Any]:
    """Alert when research surfaces should not inform sizing."""
    stale = degraded or scanner_degraded
    return {
        "stale": stale,
        "alerts": (
            ["Research staleness — dossier/funds/backtest confirm-only until fresh"]
            if stale
            else []
        ),
        "may_authorize_deploy": False,
        "recovery_hint": "Retry when data badges clear and /health mode=full",
    }


def build_safe_automation_context(
    *,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    tradeability: str = "WAIT",
    narrative: str = "",
    deployable_count: int = 0,
    ibkr_connected: bool = False,
    degraded: bool = False,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    nm = list(near_miss or [])
    body = {
        "near_miss_recheck": build_near_miss_auto_recheck(nm, prior_near_miss=prior_near_miss),
        "monitor_upgrade_alerts": build_monitor_upgrade_alert_engine(
            nm, prior_near_miss=prior_near_miss
        ),
        "monitor_queue_aging": build_monitor_queue_aging(
            monitor_triggers, near_miss=nm
        ),
        "research_staleness": build_research_staleness_alerts(degraded=degraded),
        "daily_briefing": build_daily_operator_briefing(
            tradeability=tradeability,
            narrative=narrative,
            near_miss_count=len(nm),
            deployable_count=deployable_count,
            monitor_trigger_count=len(monitor_triggers or []),
            ibkr_connected=ibkr_connected,
            degraded=degraded,
            quant_cluster_hints=quant_cluster_hints,
        ),
        "automation_ceiling": "workflow_support",
        "may_authorize_deploy": False,
        "may_override_board_gate": False,
        "no_auto_deploy": True,
        "no_hidden_authority_escalation": True,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_SAFE_AUTOMATION,
        source="safe-automation-support",
        as_of=datetime.now(timezone.utc).isoformat(),
        degraded=degraded,
        data_mode="research_only" if degraded else "ops_probe",
        extra=body,
    )
