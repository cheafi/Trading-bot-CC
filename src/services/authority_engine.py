"""
Deploy authority + engine state — canonical rules for operator surfaces.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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


def deploy_authority_tier(truth: Optional[Dict[str, Any]] = None) -> str:
    t = truth or {}
    tier = str(t.get("deploy_authority_tier") or t.get("deployAuthority") or "").lower()
    if tier in ("allowed", "paper_only", "pilot_only", "blocked"):
        return tier
    return "allowed" if t.get("deploy_authority") else "blocked"


def deploy_blocked(truth: Optional[Dict[str, Any]] = None) -> bool:
    return deploy_authority_tier(truth) != "allowed"


def live_handoff_blocked(truth: Optional[Dict[str, Any]] = None) -> bool:
    """Live IBKR handoff — never when broker offline or deploy not allowed."""
    t = truth or {}
    if deploy_authority_tier(t) != "allowed":
        return True
    broker = str(t.get("broker_freshness") or "").lower()
    if broker in ("offline", "blocked"):
        return True
    return not bool(t.get("deploy_authority"))


def primary_operator_state(truth: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Primary operator posture — tier-aware daily paths (paper / pilot / monitor)."""
    t = truth or {}
    regime = str(t.get("regime_state") or "WAIT").upper()
    tier = deploy_authority_tier(t)

    if t.get("operator_tier_now"):
        now = str(t["operator_tier_now"])
        if tier == "allowed":
            return {"primary": regime, "secondary": "", "now": now}
        if tier == "paper_only":
            return {
                "primary": "PAPER DEPLOY",
                "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
                "now": now,
            }
        if tier == "pilot_only":
            return {
                "primary": "PILOT",
                "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
                "now": now,
            }

    try:
        from src.services.cc_daily_trading import tier_operator_copy

        copy = tier_operator_copy(
            tier,
            broker_offline=str(t.get("broker_freshness") or "").lower() in ("offline", "blocked"),
        )
        now = copy.get("now") or "MONITOR ONLY · Deploy blocked"
    except Exception:
        now = "MONITOR ONLY · Deploy blocked" if tier == "blocked" else regime

    if tier == "allowed":
        if regime == "NO_TRADE":
            return {"primary": "MONITOR ONLY", "secondary": "NO_TRADE", "now": "MONITOR ONLY · Regime closed"}
        return {"primary": regime, "secondary": "", "now": now}
    if tier == "paper_only":
        return {
            "primary": "PAPER DEPLOY",
            "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
            "now": now,
        }
    if tier == "pilot_only":
        return {
            "primary": "PILOT",
            "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
            "now": now,
        }
    if regime == "NO_TRADE":
        return {"primary": "MONITOR ONLY", "secondary": "NO_TRADE", "now": "MONITOR ONLY · Regime closed"}
    return {
        "primary": "MONITOR ONLY",
        "secondary": regime if regime not in ("NO_TRADE", "WAIT") else "",
        "now": now,
    }


def pilot_sizing_allowed(truth: Optional[Dict[str, Any]] = None) -> bool:
    """Half-size pilot when pilot tier + broker + fresh data — not on paper-only path."""
    t = truth or {}
    tier = deploy_authority_tier(t)
    if tier == "paper_only":
        return False
    if tier == "allowed" and t.get("deploy_authority"):
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
    if tier != "pilot_only":
        return False
    broker = str(t.get("broker_freshness") or "").lower()
    if broker in ("offline", "blocked"):
        return False
    brief = str(t.get("brief_freshness") or "").lower()
    if brief in ("expired", "fallback", "stale"):
        return False
    board = str(t.get("ranked_board_freshness") or "").lower()
    if board in ("stale", "fallback", "unavailable"):
        return False
    return int(t.get("pilot_eligible_count") or 0) >= 1


def paper_deploy_allowed(truth: Optional[Dict[str, Any]] = None) -> bool:
    return deploy_authority_tier(truth) == "paper_only"


def why_lines(truth: Dict[str, Any]) -> List[str]:
    from src.services.system_truth import reason_codes_to_copy

    copy = truth.get("reason_copy") or reason_codes_to_copy(truth.get("reason_codes") or [])
    return [str(c) for c in copy if c][:4]


def next_action(truth: Dict[str, Any]) -> str:
    tier = deploy_authority_tier(truth)
    repair = truth.get("repair_priority") or []
    if tier == "paper_only":
        return "review paper simulation drafts on Playbook — no live handoff"
    if tier == "pilot_only":
        if "BROKER_OFFLINE" in repair:
            return "repair IBKR for pilot sizing — half size when ready"
        return "review Pilot bucket on Playbook — half size when broker ready"
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
    if truth.get("qualification_counts_line"):
        return str(truth["qualification_counts_line"])
    watch_n = int(truth.get("watch_qualified_count") or truth.get("setup_qualified_count") or 0)
    trade_n = int(truth.get("trade_qualified_count") or 0)
    exec_n = int(truth.get("execution_qualified_count") or 0)
    deploy_n = int(truth.get("deploy_qualified_count") or 0)
    paper_n = int(truth.get("paper_qualified_count") or 0)
    tier = deploy_authority_tier(truth)
    if tier == "paper_only" and paper_n > 0:
        return (
            f"Setup-qualified: {watch_n} · Trade-qualified: {trade_n} · "
            f"Execution-qualified: {exec_n} · Paper-qualified: {paper_n}"
        )
    if not truth.get("deploy_authority"):
        deploy_n = 0
    pilot_n = int(truth.get("pilot_eligible_count") or 0)
    if tier == "pilot_only" and pilot_n > 0:
        return (
            f"Setup-qualified: {watch_n} · Trade-qualified: {trade_n} · "
            f"Pilot: {pilot_n} · Execution-qualified: {exec_n}"
        )
    return (
        f"Setup-qualified: {watch_n} · Trade-qualified: {trade_n} · "
        f"Execution-qualified: {exec_n} · Deploy-qualified: {deploy_n}"
    )


def blocked_line(truth: Dict[str, Any]) -> str:
    tier = deploy_authority_tier(truth)
    if tier == "allowed":
        return ""
    if tier == "paper_only":
        return "no live handoff while broker offline"
    if tier == "pilot_only":
        return "no full-size deploy until execution-ready"
    return "no sizing, no handoff, no pilot entry"


def allowed_line(truth: Dict[str, Any]) -> str:
    tier = deploy_authority_tier(truth)
    if tier == "allowed":
        return "deploy selectively on qualified names"
    if tier == "paper_only":
        return "paper simulation drafts — no live IBKR handoff"
    if tier == "pilot_only":
        return "pilot probe on B+ setups — half size when broker ready"
    return "monitor candidates, create watch rules"
