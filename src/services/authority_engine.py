"""
Deploy authority + engine state — canonical rules for operator surfaces.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def resolve_engine_state(
    today: Optional[Dict[str, Any]] = None,
    ops: Optional[Dict[str, Any]] = None,
) -> str:
    """Single engine resolver — conflicting signals → unknown."""
    t = today or {}
    o = ops or {}
    er = t.get("execution_readiness") or {}
    sub = er.get("sub_status") or {}

    signals: List[str] = []
    if er.get("engine_running") is True or sub.get("engine") == "on":
        signals.append("on")
    elif er.get("engine_running") is False or sub.get("engine") == "off":
        signals.append("off")
    if o.get("engine_running") is True:
        signals.append("on")
    elif o.get("engine_running") is False:
        signals.append("off")

    if not signals:
        return "unknown"
    if "on" in signals and "off" in signals:
        return "unknown"
    return signals[0]


def deploy_blocked(truth: Optional[Dict[str, Any]] = None) -> bool:
    t = truth or {}
    return not bool(t.get("deploy_authority"))


def primary_operator_state(truth: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Primary operator posture — MONITOR ONLY when deploy blocked;
    tradeability (e.g. SELECTIVE) is secondary only.
    """
    t = truth or {}
    regime = str(t.get("regime_state") or "WAIT").upper()
    blocked = deploy_blocked(t)
    if blocked:
        return {
            "primary": "MONITOR ONLY",
            "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
            "now": "MONITOR ONLY · Deploy blocked",
        }
    if regime == "NO_TRADE":
        return {"primary": "MONITOR ONLY", "secondary": "NO_TRADE", "now": "MONITOR ONLY · Regime closed"}
    return {"primary": regime, "secondary": "", "now": regime}


def pilot_sizing_allowed(truth: Optional[Dict[str, Any]] = None) -> bool:
    """Half-size pilot only when deploy path + broker + fresh data are all open."""
    t = truth or {}
    if not t.get("deploy_authority"):
        return False
    broker = str(t.get("broker_freshness") or "").lower()
    if broker in ("offline", "blocked"):
        return False
    brief = str(t.get("brief_freshness") or "").lower()
    if brief in ("expired", "fallback", "stale"):
        return False
    market = str(t.get("market_data_freshness") or "").lower()
    if market in ("stale", "unavailable"):
        return False
    board = str(t.get("ranked_board_freshness") or "").lower()
    if board in ("stale", "fallback", "unavailable"):
        return False
    return True


def why_lines(truth: Dict[str, Any]) -> List[str]:
    from src.services.system_truth import reason_codes_to_copy

    copy = truth.get("reason_copy") or reason_codes_to_copy(truth.get("reason_codes") or [])
    return [str(c) for c in copy if c][:4]


def next_action(truth: Dict[str, Any]) -> str:
    repair = truth.get("repair_priority") or []
    if "BROKER_OFFLINE" in repair:
        return "repair IBKR / open Repair Console"
    if "BRIEF_EXPIRED" in repair or "FALLBACK_BRIEF" in repair:
        return "refresh board / regenerate brief"
    if "DATA_STALE" in repair or "BOARD_STALE" in repair:
        return "refresh board / wait for live ranked load"
    if "ENGINE_OFF" in repair:
        return "start engine on Ops"
    if truth.get("deploy_authority"):
        return "review deploy-qualified on Playbook"
    return "monitor only — patience is the active decision"


def valid_candidates_line(truth: Dict[str, Any]) -> str:
    watch_n = int(truth.get("watch_qualified_count") or truth.get("setup_qualified_count") or 0)
    deploy_n = int(truth.get("deploy_qualified_count") or 0)
    if not truth.get("deploy_authority"):
        deploy_n = 0
    return f"Watch {watch_n} · Deploy {deploy_n}"


def blocked_line(truth: Dict[str, Any]) -> str:
    if truth.get("deploy_authority"):
        return ""
    return "no sizing, no handoff, no pilot entry"


def allowed_line(truth: Dict[str, Any]) -> str:
    if truth.get("deploy_authority"):
        return "deploy selectively on qualified names"
    return "monitor candidates, create watch rules"
