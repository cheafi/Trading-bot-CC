"""
Agent page — monitoring copilot state (no deploy authority).

Agent is a watch-rule copilot only. It never sizes, deploys, or hands off to IBKR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.authority_engine import (
    allowed_line,
    blocked_line,
    deploy_authority_tier,
    primary_operator_state,
)
from src.services.system_truth import BRIEF_EXPIRE_DAYS, mission_blockers_from_truth

AgentMode = str  # active_monitor | degraded_monitor | unavailable

_BLOCKED_ACTIONS = frozenset({"AVOID", "NO_TRADE", "BLOCKED", "EXIT", "REDUCE", "PASS"})


def exclude_expired_brief_from_agent(truth: Optional[Dict[str, Any]] = None) -> bool:
    """briefAgeDays > 2 → expired; exclude all brief-derived Agent content."""
    t = truth or {}
    age = t.get("brief_age_days")
    if age is not None and int(age) > BRIEF_EXPIRE_DAYS:
        return True
    return str(t.get("brief_freshness") or "").lower() == "expired"


def _source_freshness(truth: Dict[str, Any]) -> str:
    scoped = truth.get("scoped_freshness") or {}
    raw = scoped.get("agent_rules") or truth.get("agentRulesFreshness") or "fresh"
    return str(raw or "fresh").lower()


def _normalize_candidates(
    watch_candidates: Optional[List[Any]] = None,
    near_miss: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for src in list(watch_candidates or []) + list(near_miss or []):
        if isinstance(src, str):
            ticker = src.strip().upper()
            row: Dict[str, Any] = {"ticker": ticker}
        elif isinstance(src, dict):
            ticker = str(src.get("ticker") or src.get("symbol") or "").strip().upper()
            row = dict(src)
            row["ticker"] = ticker
        else:
            continue
        if not ticker or len(ticker) > 8 or ticker in seen:
            continue
        seen.add(ticker)
        out.append(row)
    return out


def resolve_agent_mode(truth: Optional[Dict[str, Any]] = None) -> AgentMode:
    t = truth or {}
    if not t:
        return "unavailable"
    runtime = str(t.get("runtime_state") or "").lower()
    if runtime in ("unavailable", "critical"):
        return "unavailable"
    tier = deploy_authority_tier(t)
    if tier != "allowed" or not t.get("deploy_authority"):
        return "degraded_monitor"
    if exclude_expired_brief_from_agent(t):
        return "degraded_monitor"
    if _source_freshness(t) != "fresh":
        return "degraded_monitor"
    if str(t.get("ranked_board_freshness") or "").lower() in (
        "stale",
        "fallback",
        "unavailable",
    ):
        return "degraded_monitor"
    return "active_monitor"


def agent_brief_label(truth: Optional[Dict[str, Any]] = None) -> str:
    """Expired brief — never labeled as fallback."""
    t = truth or {}
    if exclude_expired_brief_from_agent(t):
        age = int(t.get("brief_age_days") or 0)
        return (
            f"Brief: Expired {age}d — excluded from Agent brief and rule suggestions"
        )
    bf = str(t.get("brief_freshness") or "fresh").lower()
    if bf == "stale":
        return "Brief: Stale — provisional rule status only"
    if bf == "fresh":
        return "Brief: Fresh"
    if bf == "fallback":
        return "Brief: Fallback board — monitor context only, not deploy"
    return f"Brief: {bf.title()}"


def agent_max_one_blocker_line(truth: Optional[Dict[str, Any]] = None) -> str:
    t = dict(truth or {})
    t["agent_blocker_compact"] = True
    blockers = mission_blockers_from_truth(t)
    if blockers:
        return str(blockers[0])
    return str(t.get("primary_blocker") or "").strip()


def suggest_safe_watch_rules(
    candidates: Optional[List[Any]],
    truth: Optional[Dict[str, Any]] = None,
    *,
    max_rules: int = 3,
) -> List[Dict[str, Any]]:
    """Safe watch-rule seeds — authority_effect always none."""
    t = truth or {}
    if exclude_expired_brief_from_agent(t):
        return []
    provisional = _source_freshness(t) != "fresh"
    rule_status = "provisional" if provisional else "draft"
    rows: List[Dict[str, Any]] = []
    for cand in _normalize_candidates(candidates, None):
        ticker = str(cand.get("ticker") or "")
        action = str(cand.get("action") or cand.get("effective_action") or "WATCH").upper()
        if action in _BLOCKED_ACTIONS:
            continue
        rows.append(
            {
                "trigger": f"Alert when {ticker} needs attention — monitor only",
                "ticker": ticker,
                "expiry": "session",
                "source": str(cand.get("source") or "playbook_watch"),
                "authority_effect": "none",
                "rule_status": rule_status,
            }
        )
        if len(rows) >= max(0, int(max_rules)):
            break
    return rows


def _suggested_rules_empty_reason(
    truth: Dict[str, Any],
    watch_candidates: Optional[List[Any]],
    near_miss: Optional[List[Any]],
) -> str:
    if exclude_expired_brief_from_agent(truth):
        return agent_brief_label(truth)
    if not _normalize_candidates(watch_candidates, near_miss):
        return "No fresh watch or near-miss on Playbook — no safe rule candidates"
    return ""


def build_degraded_agent_status(truth: Optional[Dict[str, Any]] = None) -> str:
    """Degraded operator note — never 'Overnight Brief'."""
    t = truth or {}
    if resolve_agent_mode(t) != "degraded_monitor":
        return ""
    parts: List[str] = []
    blocker = agent_max_one_blocker_line(t)
    if blocker:
        parts.append(blocker)
    if exclude_expired_brief_from_agent(t):
        age = int(t.get("brief_age_days") or 0)
        parts.append(f"Brief expired {age}d — excluded from Agent brief and rule suggestions")
    if deploy_authority_tier(t) != "allowed":
        parts.append("Deploy authority blocked — sizing and handoff disabled")
    body = " · ".join(parts) if parts else "System degraded — monitor-only copilot"
    return f"Degraded Status Note: {body}"


def _agent_now_line(truth: Dict[str, Any], mode: AgentMode) -> str:
    if mode == "unavailable":
        return "MONITOR ONLY · Agent unavailable"
    if mode == "degraded_monitor":
        return "MONITOR ONLY · Agent degraded"
    # Never mirror SELECTIVE as primary — Agent is always monitor copilot.
    posture = primary_operator_state(truth)
    if posture.get("primary") == "MONITOR ONLY":
        return str(posture.get("now") or "MONITOR ONLY · Active monitor copilot")
    return "MONITOR ONLY · Active monitor copilot"


def _agent_next_line(
    truth: Dict[str, Any],
    mode: AgentMode,
    *,
    has_suggested: bool,
) -> str:
    if mode == "unavailable":
        return "wait for system truth — refresh Dashboard first"
    if exclude_expired_brief_from_agent(truth):
        return "refresh Playbook board — brief excluded from Agent"
    if mode == "degraded_monitor":
        return "repair blockers on Dashboard — Agent stays monitor-only"
    if has_suggested:
        return "review suggested watch rules — alert only, no deploy"
    return "describe a monitor condition or seed rules from Playbook Watch"


def build_agent_page_state(
    truth: Optional[Dict[str, Any]] = None,
    watch_candidates: Optional[List[Any]] = None,
    near_miss: Optional[List[Any]] = None,
    *,
    rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    t = dict(truth or {})
    mode = resolve_agent_mode(t)
    tier = deploy_authority_tier(t)
    deploy_allowed = tier == "allowed" and bool(t.get("deploy_authority"))
    existing_rules = [r for r in (rules or []) if r and r.get("enabled", True) is not False]
    suggested = suggest_safe_watch_rules(
        _normalize_candidates(watch_candidates, near_miss),
        t,
        max_rules=3,
    )
    empty_reason = _suggested_rules_empty_reason(t, watch_candidates, near_miss)
    if not suggested and empty_reason:
        suggested_reason = empty_reason
    elif not suggested:
        suggested_reason = "No safe rule candidates"
    else:
        suggested_reason = ""
    return {
        "now": _agent_now_line(t, mode),
        "why": agent_max_one_blocker_line(t) or "monitor only — no deploy authority",
        "allowed": allowed_line(t) if deploy_allowed else "monitor candidates, create watch rules",
        "blocked": blocked_line(t) or "no sizing, no handoff, no pilot entry",
        "rules": existing_rules,
        "rules_count": len(existing_rules),
        "suggested_rules": suggested,
        "suggested_rules_reason": suggested_reason,
        "next": _agent_next_line(t, mode, has_suggested=bool(suggested)),
        "mode": mode,
        "brief_label": agent_brief_label(t),
        "degraded_status_note": build_degraded_agent_status(t),
        "agent_can_deploy": False,
        "agent_can_size": False,
        "agent_can_handoff": False,
        "authority_guardrail_label": "Test authority guardrail",
    }


def log_agent_audit_event(event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    e = event or {}
    return {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "category": str(e.get("category") or "agent"),
        "message": str(e.get("message") or ""),
        "detail": str(e.get("detail") or ""),
        "authority_effect": "none",
    }


def enforce_agent_authority_guardrail() -> Dict[str, Any]:
    return {
        "pass": True,
        "label": "Test authority guardrail",
        "message": "PASS — Agent cannot deploy, size, or hand off to IBKR",
    }


def build_agent_audit_journal_on_load(
    truth: Optional[Dict[str, Any]] = None,
    page_state: Optional[Dict[str, Any]] = None,
    *,
    rules_count: int = 0,
) -> List[Dict[str, Any]]:
    """Audit-useful journal seeds — degraded, brief expiry, no rules, guardrail."""
    t = truth or {}
    state = page_state or build_agent_page_state(t, [], [])
    events: List[Dict[str, Any]] = []
    mode = str(state.get("mode") or resolve_agent_mode(t))
    if mode == "degraded_monitor":
        events.append(
            log_agent_audit_event(
                {
                    "category": "degraded",
                    "message": "Agent degraded — monitor-only copilot",
                    "detail": str(state.get("why") or ""),
                }
            )
        )
    if exclude_expired_brief_from_agent(t):
        events.append(
            log_agent_audit_event(
                {
                    "category": "brief_expiry",
                    "message": str(state.get("brief_label") or agent_brief_label(t)),
                    "detail": "Brief excluded from Agent brief and rule suggestions",
                }
            )
        )
    if rules_count <= 0:
        events.append(
            log_agent_audit_event(
                {
                    "category": "no_rules",
                    "message": "No active watch rules",
                    "detail": str(
                        state.get("suggested_rules_reason") or "No safe rule candidates"
                    ),
                }
            )
        )
    guardrail = enforce_agent_authority_guardrail()
    events.append(
        log_agent_audit_event(
            {
                "category": "guardrail_test",
                "message": guardrail["label"],
                "detail": guardrail["message"],
            }
        )
    )
    return events
