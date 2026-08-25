"""Shared research-surface safety — no deploy authority across Agent / Lab / Shadow / Reports."""

from __future__ import annotations

from typing import Any, Dict, List

RESEARCH_AUTHORITY_LABEL = "研究 / 監察 only · Research / Monitoring only"
RESEARCH_AUTHORITY_SUB = "不提供部署權限 · No deploy authority"

_FORBIDDEN_COPY = frozenset(
    {
        "buy now",
        "deploy now",
        "size now",
        "send to ibkr",
        "place order",
        "full size",
        "one-click live",
        "auto trade",
        "execute now",
    }
)

DEFAULT_AUTHORITY_NOTICE: List[str] = [
    "Research / monitoring only · 研究 / 監察 only",
    "Requires Dashboard + Playbook confirmation",
    "No sizing / no handoff from research surfaces",
    "Backtest pass ≠ live trade permission",
]

PINE_DISCLAIMER = (
    "// RESEARCH DRAFT ONLY — NOT LIVE EXECUTION\n"
    "// Clarity Console · 非部署權限 · No deploy authority\n"
    "// Validate in Strategy Lab before any Playbook review\n"
)


def research_safety_contract(*, surface: str = "research") -> Dict[str, Any]:
    return {
        "surface_type": "research_monitoring",
        "surface": surface,
        "authority_label": RESEARCH_AUTHORITY_LABEL,
        "authority_sub": RESEARCH_AUTHORITY_SUB,
        "can_research": True,
        "can_monitor": True,
        "can_validate": True,
        "can_export": True,
        "can_deploy": False,
        "can_size": False,
        "can_handoff": False,
        "can_override_dashboard": False,
        "can_override_playbook": False,
        "authority_notice": list(DEFAULT_AUTHORITY_NOTICE),
        "pipeline_stops_at": "watch_rule_or_playbook_review",
    }


def authority_notice_for_state(system_state: Dict[str, Any] | None) -> List[str]:
    from src.services.vibe_agent_safety import (
        authority_notice_for_state as _agent_notices,
    )

    return _agent_notices(system_state)


def sanitize_research_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip deploy/sizing/handoff; force research-only actions."""
    out = dict(payload)
    out["authority_effect"] = "none"
    action = str(out.get("action") or "research_only")
    if action not in (
        "research_only",
        "alert_only",
        "journal_only",
        "brief_only",
        "validate_only",
        "export_only",
    ):
        action = "research_only"
    out["action"] = action
    out["can_deploy"] = False
    out["can_size"] = False
    out["can_handoff"] = False
    for key in ("sizing", "order", "ibkr", "broker_order", "live_execution"):
        out.pop(key, None)
    if "generatedCode" in out and isinstance(out["generatedCode"], str):
        if PINE_DISCLAIMER.split("\n")[0] not in out["generatedCode"]:
            out["generatedCode"] = PINE_DISCLAIMER + out["generatedCode"]
    text_fields = ("next_action", "headline", "message", "summary", "verdict")
    for field in text_fields:
        val = str(out.get(field) or "").lower()
        if any(bad in val for bad in _FORBIDDEN_COPY):
            out[field] = str(out.get(field) or "") + " · Requires Playbook confirmation"
    out.setdefault("authority_notice", list(DEFAULT_AUTHORITY_NOTICE))
    return out


def pipeline_step_labels() -> List[Dict[str, str]]:
    """Safer one-click research pipeline — no live execution labels."""
    return [
        {"id": "draft", "label": "Generate strategy draft · 生成策略草稿"},
        {"id": "validate", "label": "Run validation · 執行驗證"},
        {"id": "watch_rule", "label": "Create watch rule · 建立監察規則"},
        {"id": "playbook", "label": "Send to Playbook review · 送 Playbook 審閱"},
        {"id": "dossier", "label": "Open Dossier · 開啟 Dossier"},
        {"id": "journal", "label": "Add to journal · 加入日誌"},
    ]
