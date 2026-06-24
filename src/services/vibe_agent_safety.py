"""Agent safety contract — monitoring only, never deploy authority."""

from __future__ import annotations

from typing import Any, Dict, List

AGENT_SURFACE_TYPE = "research_monitoring"
AGENT_AUTHORITY_LABEL = "Research / Monitoring only · 非部署權限"
AGENT_PAGE_TITLE = "Vibe Agent · 熬夜盯盤副駕"

_FORBIDDEN_ACTIONS = frozenset(
    {"deploy", "size", "handoff", "ibkr_order", "autonomous_execute", "override_gate"}
)
_FORBIDDEN_COPY = frozenset(
    {"buy now", "deploy now", "size now", "send to ibkr", "place order", "full size"}
)

DEFAULT_AUTHORITY_NOTICE: List[str] = [
    "Research / monitoring only",
    "Requires Dashboard + Playbook confirmation",
    "No sizing / no handoff from Agent",
]


def agent_safety_contract() -> Dict[str, Any]:
    """Explicit AgentSafetyContract for API + UI."""
    return {
        "surface_type": AGENT_SURFACE_TYPE,
        "authority_label": AGENT_AUTHORITY_LABEL,
        "can_monitor": True,
        "can_alert": True,
        "can_create_watch_rules": True,
        "can_journal": True,
        "can_suggest_confirmation_path": True,
        "can_deploy": False,
        "can_size": False,
        "can_handoff": False,
        "can_override_dashboard": False,
        "can_override_playbook": False,
        "can_hide_degraded_state": False,
        "authority_notice": list(DEFAULT_AUTHORITY_NOTICE),
    }


def authority_notice_for_state(system_state: Dict[str, Any] | None) -> List[str]:
    """Context-aware notices — never grant permission."""
    notices = list(DEFAULT_AUTHORITY_NOTICE)
    ss = system_state or {}
    tb = str(ss.get("tradeability") or "WAIT").upper()
    if tb in ("WAIT", "NO_TRADE"):
        notices.append(f"Board gate {tb} · 只可監察")
    if str(ss.get("data_freshness") or "") in ("STALE", "CRITICAL"):
        notices.append("Data stale — alerts provisional")
    broker = str(ss.get("broker_state") or "").upper()
    if broker in (
        "GATEWAY_DOWN",
        "DISCONNECTED",
        "SESSION_INACTIVE",
        "EXEC_BLOCKED",
        "HANDOFF_BLOCKED",
    ):
        notices.append("Broker offline — no handoff")
    if ss.get("fallback_mode"):
        notices.append("Brief fallback — monitor alerts only")
    return notices


def sanitize_agent_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip forbidden deploy/sizing/handoff fields from agent outputs."""
    out = dict(payload)
    out["authority_effect"] = "none"
    out["action"] = str(out.get("action") or "alert_only")
    if out["action"] not in ("alert_only", "journal_only", "brief_only"):
        out["action"] = "alert_only"
    for key in ("can_deploy", "can_size", "can_handoff", "sizing", "order", "ibkr"):
        out.pop(key, None)
    text_fields = ("next_action", "headline", "message", "hypothesis", "trigger_reason")
    for field in text_fields:
        val = str(out.get(field) or "").lower()
        if any(bad in val for bad in _FORBIDDEN_COPY):
            out[field] = out.get(field, "") + " · Requires Playbook confirmation"
    return out


def guardrail_for_action(
    *,
    action_type: str,
    system_state: Dict[str, Any] | None,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """createCalmDownGuardrail — detect emotional / rule-breaking attempts."""
    ss = system_state or {}
    ctx = context or {}
    tb = str(ss.get("tradeability") or "WAIT").upper()
    data_tier = str(ss.get("data_freshness") or "FRESH")
    broker_bad = str(ss.get("broker_state") or "") not in (
        "",
        "CONNECTED",
        "HANDOFF_READY",
        "BRACKET_READY",
    )
    violated: List[str] = []
    act = str(action_type or "").lower()

    if act in ("deploy", "size", "handoff", "ibkr_order"):
        violated.append("agent cannot authorize deploy/sizing/handoff")
    if tb in ("WAIT", "NO_TRADE") and act in (
        "deploy",
        "size",
        "increase_risk",
        "chase",
        "average_down",
    ):
        violated.append(f"page gate {tb}")
    if data_tier in ("STALE", "CRITICAL") and act in ("deploy", "size"):
        violated.append("data stale")
    if broker_bad and act in ("handoff", "ibkr_order"):
        violated.append("broker offline")
    if ctx.get("confirm_only_dossier") and act in ("size", "handoff"):
        violated.append("dossier confirm-only")
    if ctx.get("mock_flow") and act in ("deploy", "trade", "chase"):
        violated.append("mock flow non-actionable")
    if ctx.get("drawdown_breach") and act in ("increase_risk", "deploy", "size"):
        violated.append("drawdown guard")

    if not violated:
        return {"triggered": False, "authority_notice": list(DEFAULT_AUTHORITY_NOTICE)}

    safer = "加入 watch rule，等 Playbook + Dashboard 同時放行"
    if act in ("chase", "average_down"):
        safer = "設定 monitor rule + invalidation，唔好喺 gate 阻塞時追價"
    return sanitize_agent_payload(
        {
            "triggered": True,
            "warning_title": "先停一停 · Pause first",
            "warning_sentence": (
                "你而家想做嘅動作同系統規則有衝突。"
                "請先確認：Dashboard gate、Playbook action、Dossier structure、Portfolio risk。"
            ),
            "violated_rules": violated,
            "safer_alternative": safer,
            "confirmation_path": "Dashboard → Playbook → Dossier",
            "action": "alert_only",
            "authority_notice": authority_notice_for_state(ss),
        }
    )
