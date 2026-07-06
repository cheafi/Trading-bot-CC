"""Strategy Lab authority modes — offline draft vs validation vs promotion."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from src.services.authority_engine import deploy_authority_tier
from src.services.system_truth import BRIEF_EXPIRE_DAYS

StrategyLabMode = Literal[
    "offline_draft_only",
    "validation_ready",
    "validated_research",
    "unavailable",
]

_STALE_SCOPES = frozenset(
    {"stale", "fallback", "unavailable", "expired", "offline", "blocked", "mock"}
)
_FRESH_SCOPES = frozenset({"fresh", "ready", "partial"})


def exclude_expired_brief_from_strategy_context(truth: Optional[Dict[str, Any]] = None) -> bool:
    """Expired briefs are excluded — never treated as fallback in Strategy Lab."""
    t = truth or {}
    age = t.get("brief_age_days")
    if age is not None and int(age) > BRIEF_EXPIRE_DAYS:
        return True
    return str(t.get("brief_freshness") or "").lower() == "expired"


def _brief_age_days(truth: Dict[str, Any]) -> int:
    age = truth.get("brief_age_days")
    if age is not None:
        return int(age)
    return int((truth.get("brief_status") or {}).get("age_days") or 0)


def _scope_stale(val: str) -> bool:
    return str(val or "unavailable").lower() in _STALE_SCOPES


def _scope_fresh(val: str) -> bool:
    return str(val or "").lower() in _FRESH_SCOPES


def _validation_bundle(truth: Dict[str, Any]) -> Dict[str, Any]:
    bundle = truth.get("strategy_lab_validation") or truth.get("strategy_validation") or {}
    return bundle if isinstance(bundle, dict) else {}


def _validation_flag(bundle: Dict[str, Any], *keys: str) -> bool:
    for key in keys:
        val = bundle.get(key)
        if val is True:
            return True
        if isinstance(val, dict) and val.get("passed") is True:
            return True
        if str(val or "").lower() in ("pass", "passed", "fresh", "ok"):
            return True
    return False


def build_strategy_validation_status(
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Per-scope validation gates for Strategy Lab promotion path."""
    t = dict(truth or {})
    bundle = _validation_bundle(t)
    brief_excluded = exclude_expired_brief_from_strategy_context(t)
    brief_age = _brief_age_days(t)

    market = str(t.get("market_data_freshness") or "unavailable")
    board = str(t.get("ranked_board_freshness") or "unavailable")
    broker = str(t.get("broker_freshness") or "offline")
    tier = deploy_authority_tier(t)

    if brief_excluded:
        brief_status = "expired"
        brief_label = f"Expired {brief_age}d — excluded from strategy context"
    elif str(t.get("brief_freshness") or "").lower() == "fallback":
        brief_status = "excluded"
        brief_label = "Fallback — excluded from strategy validation"
    elif _scope_stale(str(t.get("brief_freshness") or "")):
        brief_status = "stale"
        brief_label = "Brief stale — confirm before validation"
    else:
        brief_status = "fresh"
        brief_label = "Fresh — included in strategy context"

    deploy_allowed = tier == "allowed" and bool(t.get("deploy_authority"))
    authority = {
        "deploy": deploy_allowed,
        "sizing": deploy_allowed,
        "handoff": deploy_allowed and broker not in ("offline", "blocked"),
        "label": (
            "deploy path open on qualified names"
            if deploy_allowed
            else "research only — no deploy, sizing, or handoff"
        ),
    }

    return {
        "live_data": {
            "passed": _scope_fresh(market),
            "label": "Fresh" if _scope_fresh(market) else "Stale — refresh before validation",
        },
        "brief": {"passed": not brief_excluded and brief_status == "fresh", "label": brief_label},
        "board": {
            "passed": _scope_fresh(board),
            "label": "Fresh" if _scope_fresh(board) else "Stale — promotion blocked",
        },
        "broker": {
            "passed": broker not in ("offline", "blocked"),
            "label": "Ready" if broker not in ("offline", "blocked") else "Offline — no handoff",
        },
        "backtest": {
            "passed": _validation_flag(bundle, "backtest", "backtest_passed"),
            "label": "Passed" if _validation_flag(bundle, "backtest", "backtest_passed") else "Pending",
        },
        "walk_forward": {
            "passed": _validation_flag(bundle, "walk_forward", "walk_forward_passed"),
            "label": (
                "Passed"
                if _validation_flag(bundle, "walk_forward", "walk_forward_passed")
                else "Pending"
            ),
        },
        "costs": {
            "passed": _validation_flag(bundle, "costs", "costs_passed"),
            "label": "Passed" if _validation_flag(bundle, "costs", "costs_passed") else "Pending",
        },
        "calibration": {
            "passed": _validation_flag(bundle, "calibration", "calibration_passed"),
            "label": (
                "Ready"
                if _validation_flag(bundle, "calibration", "calibration_passed")
                else "Provisional"
            ),
        },
        "authority": authority,
    }


def resolve_strategy_lab_mode(truth: Optional[Dict[str, Any]] = None) -> StrategyLabMode:
    """Offline draft when any core scope is degraded; promotion only after validation passes."""
    t = dict(truth or {})
    validation = build_strategy_validation_status(t)

    data_stale = _scope_stale(str(t.get("market_data_freshness") or ""))
    board_stale = _scope_stale(str(t.get("ranked_board_freshness") or ""))
    broker_offline = str(t.get("broker_freshness") or "offline").lower() in ("offline", "blocked")
    brief_expired = exclude_expired_brief_from_strategy_context(t)

    if data_stale or board_stale or broker_offline or brief_expired:
        return "offline_draft_only"

    promotion_ready = (
        validation["backtest"]["passed"]
        and validation["walk_forward"]["passed"]
        and validation["costs"]["passed"]
        and validation["calibration"]["passed"]
        and validation["live_data"]["passed"]
        and validation["brief"]["passed"]
        and validation["board"]["passed"]
    )
    if promotion_ready:
        return "validated_research"

    if validation["live_data"]["passed"] and validation["board"]["passed"]:
        return "validation_ready"

    return "offline_draft_only"


def _single_blocker_line(truth: Dict[str, Any], validation: Dict[str, Any]) -> str:
    """At most one operator blocker line — highest priority wins."""
    if exclude_expired_brief_from_strategy_context(truth):
        age = _brief_age_days(truth)
        return f"Brief expired {age}d — excluded from strategy context"
    if _scope_stale(str(truth.get("ranked_board_freshness") or "")):
        return "Board stale — validation and Playbook promotion blocked"
    if _scope_stale(str(truth.get("market_data_freshness") or "")):
        return "Market data stale — refresh context before validation"
    if str(truth.get("broker_freshness") or "offline").lower() in ("offline", "blocked"):
        return "Broker offline — no deploy, sizing, or handoff"
    if not validation["backtest"]["passed"]:
        return "Backtest validation pending — export Pine blocked"
    if not validation["walk_forward"]["passed"]:
        return "Walk-forward validation pending — export Pine blocked"
    if not validation["costs"]["passed"]:
        return "Cost-adjusted edge pending — Playbook promotion blocked"
    return ""


def resolve_strategy_action_availability(
    mode: str,
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Action gates — offline draft sandbox vs validation/promotion path."""
    t = dict(truth or {})
    m = str(mode or "offline_draft_only")
    validation = build_strategy_validation_status(t)
    tier = deploy_authority_tier(t)
    deploy_allowed = tier == "allowed" and bool(t.get("deploy_authority"))
    board_stale = _scope_stale(str(t.get("ranked_board_freshness") or ""))
    promotion_passed = (
        validation["backtest"]["passed"]
        and validation["walk_forward"]["passed"]
        and validation["costs"]["passed"]
    )

    def _action(enabled: bool, reason: str = "") -> Dict[str, Any]:
        return {"enabled": bool(enabled), "reason": str(reason or "").strip()}

    offline = m == "offline_draft_only"
    validated = m == "validated_research"
    can_validate = m in ("validation_ready", "validated_research") and not offline

    actions = {
        "generate_draft": _action(True, ""),
        "save_draft": _action(True, ""),
        "refresh_context": _action(True, ""),
        "run_validation": _action(
            can_validate,
            "Offline draft only — repair live data before validation"
            if offline
            else "",
        ),
        "committee_review": _action(
            can_validate,
            "Offline draft only — committee needs fresh validation context"
            if offline
            else "Run validation before committee review",
        ),
        "export_pine": _action(
            validated and promotion_passed,
            "Offline draft only — Pine export blocked"
            if offline
            else "Complete backtest + walk-forward + costs validation first",
        ),
        "send_playbook": _action(
            validated and promotion_passed and not board_stale,
            "Board stale — Playbook promotion blocked"
            if board_stale
            else (
                "Offline draft only — Playbook promotion blocked"
                if offline
                else "Complete validation before Playbook review"
            ),
        ),
        "backtest_lab": _action(
            True,
            "Offline sandbox — historical simulation only, not deploy authority"
            if offline
            else "Research-only backtest — not deploy authority",
        ),
    }

    if not deploy_allowed:
        for key in ("export_pine", "send_playbook"):
            if actions[key]["enabled"]:
                actions[key] = _action(False, "Deploy authority blocked — research export only")

    return actions


def build_strategy_lab_page_state(
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Strategy Lab tab payload — NOW / WHY / ALLOWED / BLOCKED / VALIDATION / NEXT."""
    t = dict(truth or {})
    mode = resolve_strategy_lab_mode(t)
    validation = build_strategy_validation_status(t)
    actions = resolve_strategy_action_availability(mode, t)
    blocker = _single_blocker_line(t, validation)
    regime = str(t.get("regime_state") or "WAIT").upper()

    if mode == "offline_draft_only":
        now = "RESEARCH ONLY · Offline draft sandbox"
        allowed = "generate offline draft · save draft · refresh context"
        nxt = "repair live data / refresh board — then run validation"
    elif mode == "validation_ready":
        now = "RESEARCH ONLY · Validation ready"
        allowed = "run validation · committee review · offline drafts"
        nxt = "run validation — export Pine after backtest + walk-forward + costs pass"
    elif mode == "validated_research":
        now = "RESEARCH ONLY · Validated research"
        allowed = "export Pine · send to Playbook review · committee review"
        nxt = "promote to Playbook watch rules — board gate still required"
    else:
        now = "RESEARCH ONLY · Unavailable"
        allowed = "monitor only"
        nxt = "refresh context when API recovers"

    why_parts: List[str] = []
    if exclude_expired_brief_from_strategy_context(t):
        why_parts.append(f"Brief expired {_brief_age_days(t)}d — excluded")
    elif _scope_stale(str(t.get("market_data_freshness") or "")):
        why_parts.append("market data stale")
    elif _scope_stale(str(t.get("ranked_board_freshness") or "")):
        why_parts.append("board stale")
    elif str(t.get("broker_freshness") or "").lower() in ("offline", "blocked"):
        why_parts.append("broker offline")
    elif regime not in ("WAIT", "NO_TRADE"):
        why_parts.append(f"regime {regime} — research context only")
    else:
        why_parts.append("no closed-trade validation path open")
    why = " · ".join(why_parts[:2])

    if regime == "SELECTIVE" or str(t.get("tradeability_authority_line") or ""):
        # Strategy Lab never surfaces SELECTIVE as primary deploy posture.
        now = now if "RESEARCH ONLY" in now else "RESEARCH ONLY · Offline draft sandbox"

    return {
        "now": now,
        "why": why,
        "allowed": allowed,
        "blocked": blocker,
        "validation_status": validation,
        "next": nxt,
        "mode": mode,
        "actions": actions,
        "primary": "RESEARCH ONLY",
        "secondary": now.split("·", 1)[-1].strip() if "·" in now else "research only",
        "brief_line": validation["brief"]["label"],
        "exclude_brief_from_context": exclude_expired_brief_from_strategy_context(t),
        "authority": validation["authority"],
    }
