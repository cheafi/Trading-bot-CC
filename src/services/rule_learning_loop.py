"""
Rule Learning Loop — monitor/agent rule tracking and retirement suggestions.

Agent can suggest keep/tighten/mute/retire but cannot deploy, size, or handoff.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

RULE_STATUSES: tuple[str, ...] = (
    "draft",
    "active",
    "noisy",
    "useful",
    "retired",
)

AGENT_SUGGESTIONS: tuple[str, ...] = (
    "keep",
    "tighten",
    "mute",
    "retire",
    "convert_to_playbook_review",
)

_FALSE_ALARM_THRESHOLD = 0.45
_USEFUL_HIT_THRESHOLD = 0.55
_MIN_TRIGGERS = 3


@dataclass
class RuleRecord:
    rule_id: str
    name: str = ""
    surface: str = "agent"
    status: str = "draft"
    triggers: int = 0
    false_alarms: int = 0
    missed_upgrades: int = 0
    operator_dismissals: int = 0
    operator_acted: int = 0
    forward_r_mean: Optional[float] = None
    sample_size: int = 0
    agent_suggestion: str = "keep"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["may_size"] = False
        d["may_handoff"] = False
        return d


def _false_alarm_rate(rule: RuleRecord) -> float:
    if rule.triggers < 1:
        return 0.0
    return rule.false_alarms / rule.triggers


def evaluate_rule(rule: RuleRecord) -> RuleRecord:
    """Update rule status and agent suggestion from outcomes."""
    rate = _false_alarm_rate(rule)
    rule.sample_size = rule.triggers
    if rule.triggers < _MIN_TRIGGERS:
        rule.status = "draft" if rule.status == "draft" else "active"
        rule.agent_suggestion = "keep"
        rule.notes = "Insufficient triggers for learning"
        return rule
    if rate >= _FALSE_ALARM_THRESHOLD:
        rule.status = "noisy"
        rule.agent_suggestion = "retire"
        rule.notes = f"High false alarm rate {rate:.0%} — suggest retire"
    elif rule.forward_r_mean is not None and rule.forward_r_mean >= _USEFUL_HIT_THRESHOLD:
        rule.status = "useful"
        rule.agent_suggestion = "convert_to_playbook_review"
        rule.notes = "Forward outcomes positive — suggest Playbook review rule"
    elif rate >= 0.3:
        rule.status = "noisy"
        rule.agent_suggestion = "tighten"
        rule.notes = "Elevated false alarms — suggest tighten"
    elif rule.operator_dismissals > rule.operator_acted:
        rule.status = "noisy"
        rule.agent_suggestion = "mute"
        rule.notes = "Operator dismissals dominate — suggest mute"
    else:
        rule.status = "active"
        rule.agent_suggestion = "keep"
        rule.notes = "Within tolerance"
    return rule


def rule_from_dict(data: Dict[str, Any]) -> RuleRecord:
    return RuleRecord(
        rule_id=str(data.get("rule_id") or data.get("id") or ""),
        name=str(data.get("name") or data.get("label") or ""),
        surface=str(data.get("surface") or "agent"),
        status=str(data.get("status") or "draft"),
        triggers=int(data.get("triggers") or data.get("trigger_count") or 0),
        false_alarms=int(data.get("false_alarms") or 0),
        missed_upgrades=int(data.get("missed_upgrades") or 0),
        operator_dismissals=int(data.get("operator_dismissals") or 0),
        operator_acted=int(data.get("operator_acted") or 0),
        forward_r_mean=float(data["forward_r_mean"]) if data.get("forward_r_mean") is not None else None,
    )


def summarize_rules(
    rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate rule learning window for Dashboard / Agent."""
    records = [evaluate_rule(rule_from_dict(r)) for r in (rules or [])]
    noisy = [r for r in records if r.status == "noisy"]
    useful = [r for r in records if r.status == "useful"]
    return {
        "total": len(records),
        "draft": sum(1 for r in records if r.status == "draft"),
        "active": sum(1 for r in records if r.status == "active"),
        "noisy": len(noisy),
        "useful": len(useful),
        "retired": sum(1 for r in records if r.status == "retired"),
        "suggest_retire": [r.to_dict() for r in noisy if r.agent_suggestion == "retire"][:3],
        "suggest_promote": [r.to_dict() for r in useful][:3],
        "rules": [r.to_dict() for r in records[:12]],
        "agent_may_deploy": False,
        "agent_may_size": False,
        "agent_may_handoff": False,
        "authority_effect": "none",
    }


def build_rules_from_agent_state(
    agent_page_state: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Scaffold rules from agent page state when no persistence."""
    aps = dict(agent_page_state or {})
    count = int(aps.get("rules_count") or 0)
    if count < 1:
        return []
    return [
        {
            "rule_id": f"agent-rule-{i}",
            "name": f"Watch rule {i}",
            "surface": "agent",
            "status": "active",
            "triggers": max(0, count - i),
            "false_alarms": 0 if i > 1 else 1,
            "operator_dismissals": 0,
            "operator_acted": 0,
            "forward_r_mean": None,
        }
        for i in range(min(count, 5))
    ]
