"""CC live-only policy — refuse brief/stale/mock when CC_LIVE_DATA_ONLY=1."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def cc_live_data_only_enabled() -> bool:
    """True when CC must not serve brief-fallback, disk snapshot, or mock boards."""
    return os.environ.get("CC_LIVE_DATA_ONLY", "").strip().lower() in _TRUTHY


def _suspended_authority(*, reason: str) -> Dict[str, Any]:
    return {
        "source": "live_unavailable",
        "authority_level": "suspended",
        "deploy_authority": False,
        "gates_active": True,
        "gates": {
            "regime_wait": True,
            "fallback_brief": False,
            "scanner_loading": True,
            "data_stale": True,
            "live_only_blocked": True,
        },
        "effective_action_max": "NONE",
        "allows_trade_labels": False,
        "live_only": True,
        "detail": reason,
    }


INTELLIGENCE_EMPTY_LEARNING = "Learning — not enough forward outcomes yet"
INTELLIGENCE_EMPTY_NO_RESEARCH = "No research candidates yet"
INTELLIGENCE_EMPTY_NO_REVIEW = "No review items yet"
INTELLIGENCE_EMPTY_NO_THRESHOLD = "No threshold proposals yet"
INTELLIGENCE_EMPTY_REVIEW_ONLY = "Review only · no live changes"


def build_intelligence_fallback_blocks(
    *,
    reason: str = "degraded",
) -> Dict[str, Any]:
    """Research-only intelligence shells — never blank panels on degraded Today."""
    from src.services.threshold_proposal_service import (
        threshold_governance_summary_for_dashboard,
    )

    tg = threshold_governance_summary_for_dashboard()
    if not tg.get("open_count"):
        tg = {
            **tg,
            "status_line": f"Threshold Review: 0 open · 0 shadow · {INTELLIGENCE_EMPTY_REVIEW_ONLY}",
            "empty_message": INTELLIGENCE_EMPTY_NO_THRESHOLD,
        }
    decision_quality = {
        "title": "Decision Quality",
        "state": "learning",
        "state_label": "Learning mode",
        "banner": INTELLIGENCE_EMPTY_LEARNING,
        "metrics": {
            "deploy_candidates_tracked": 0,
            "journal_events_n": 0,
            "forward_outcomes_n": 0,
            "no_edge_samples_n": 0,
            "forward_r_5d": None,
            "watch_to_deploy_conversion": None,
            "false_deploy_rate": None,
            "avoided_loss_count": None,
            "no_edge_days_protected": 0,
            "best_validated_family": None,
            "noisy_family": None,
            "useful_families": [],
            "noisy_families": [],
            "sample_size": 0,
            "learning_mode": True,
            "outcome_source": "forward_outcome_backfill",
            "authority_effect": "none",
        },
        "capital_mode": "monitor_only",
        "capital_deploy_allowed": False,
        "governor_adjustment": None,
        "risk_mode_adjustment": None,
        "requires_human_review": False,
        "no_edge_quality": "learning",
        "rule_learning": {},
        "top_ranked_by_quality": [],
        "collapsed": True,
        "details_available": True,
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "labels": {
            "forward_study": "forward outcome study",
            "cash_protected": "cash protected",
            "no_fake_precision": True,
        },
        "alpha_quality": {
            "sample_size": 0,
            "status": "learning",
            "status_label": "learning",
            "oi_lift_display": "learning",
            "cost_adj_expectancy_display": "learning",
            "conversion_quality": "learning",
            "overfit_risk": "medium",
            "allow_green_ui": False,
            "learning_mode": True,
            "empty_message": INTELLIGENCE_EMPTY_LEARNING,
            "governor_qa": {
                "qa_adjustment": None,
                "human_review_suggested": False,
                "can_loosen_automatically": False,
                "authority_effect": "none",
            },
        },
        "alpha_review": {
            "status": "learning",
            "status_label": "learning",
            "evidence_level": "learning",
            "human_review_count": 0,
            "what_improved": [],
            "what_deteriorated": [],
            "top_items": [],
            "governor_review": {},
            "next_actions": [],
            "threshold_review_line": INTELLIGENCE_EMPTY_REVIEW_ONLY,
            "empty_message": INTELLIGENCE_EMPTY_NO_REVIEW,
            "collapsed": True,
            "authority_effect": "none",
            "may_authorize_deploy": False,
        },
        "threshold_governance": tg,
        "degraded_reason": reason,
    }
    opportunity_intelligence = {
        "title": "Opportunity Intelligence",
        "funnel_stages": [
            "research_hit",
            "evidence_candidate",
            "watch_candidate",
            "near_miss",
            "playbook_review",
            "deploy_review",
            "capital_candidate",
        ],
        "by_stage": {},
        "counts": {
            "total": 0,
            "research_hit": 0,
            "evidence_candidate": 0,
            "watch_candidate": 0,
            "near_miss": 0,
            "playbook_review": 0,
            "deploy_review": 0,
            "capital_candidate": 0,
        },
        "best_theme": None,
        "best_action": INTELLIGENCE_EMPTY_NO_RESEARCH,
        "candidate_chips": [],
        "portfolio": {},
        "scored_sample": [],
        "store_summary": {},
        "learning_mode": True,
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "research_note": INTELLIGENCE_EMPTY_NO_RESEARCH,
        "empty_message": INTELLIGENCE_EMPTY_NO_RESEARCH,
        "degraded_reason": reason,
    }
    return {
        "decision_quality": decision_quality,
        "opportunity_intelligence": opportunity_intelligence,
    }


def ensure_intelligence_payload_blocks(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Merge learning empty-state shells — intelligence panels must never render blank."""
    if not isinstance(payload, dict):
        return payload
    reason = str(
        payload.get("trust", {}).get("reason")
        or payload.get("degraded_reason")
        or "learning"
    )
    fallback = build_intelligence_fallback_blocks(reason=reason)
    fb_dq = fallback["decision_quality"]
    fb_oi = fallback["opportunity_intelligence"]

    dq = payload.get("decision_quality")
    if not isinstance(dq, dict):
        payload["decision_quality"] = dict(fb_dq)
    else:
        if not dq.get("banner"):
            dq["banner"] = fb_dq["banner"]
        metrics = dq.get("metrics")
        if not isinstance(metrics, dict):
            dq["metrics"] = dict(fb_dq["metrics"])
        elif metrics.get("learning_mode") is None:
            metrics["learning_mode"] = True
        for key in ("alpha_quality", "alpha_review", "threshold_governance"):
            if not isinstance(dq.get(key), dict):
                dq[key] = dict(fb_dq[key])
        aq = dq.get("alpha_quality") or {}
        if not aq.get("empty_message") and int(aq.get("sample_size") or 0) < 1:
            aq["empty_message"] = INTELLIGENCE_EMPTY_LEARNING
            aq.setdefault("learning_mode", True)
            dq["alpha_quality"] = aq
        ar = dq.get("alpha_review") or {}
        if not ar.get("empty_message") and not (
            ar.get("what_improved")
            or ar.get("what_deteriorated")
            or ar.get("top_items")
            or ar.get("next_actions")
        ):
            ar["empty_message"] = INTELLIGENCE_EMPTY_NO_REVIEW
            dq["alpha_review"] = ar
        tg = dq.get("threshold_governance") or {}
        if not tg.get("empty_message") and not int(tg.get("open_count") or 0):
            tg["empty_message"] = INTELLIGENCE_EMPTY_NO_THRESHOLD
            tg.setdefault(
                "status_line",
                f"Threshold Review: 0 open · 0 shadow · {INTELLIGENCE_EMPTY_REVIEW_ONLY}",
            )
            dq["threshold_governance"] = tg

    oi = payload.get("opportunity_intelligence")
    if not isinstance(oi, dict):
        payload["opportunity_intelligence"] = dict(fb_oi)
    else:
        total = int((oi.get("counts") or {}).get("total") or 0)
        if total < 1:
            oi["empty_message"] = oi.get("empty_message") or INTELLIGENCE_EMPTY_NO_RESEARCH
            oi["best_action"] = oi.get("best_action") or INTELLIGENCE_EMPTY_NO_RESEARCH
            oi["research_note"] = oi.get("research_note") or INTELLIGENCE_EMPTY_NO_RESEARCH
            oi.setdefault("learning_mode", True)

    return payload


def build_live_unavailable_today_payload(*, reason: str) -> Dict[str, Any]:
    """Explicit Today response when live scanner path is required but unavailable."""
    now = datetime.now(timezone.utc)
    authority = _suspended_authority(reason=reason)
    intel = build_intelligence_fallback_blocks(reason=reason)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": (
            "Live-only mode — scanner cache empty and brief fallback disabled. "
            "Run engine cycle or wait for live scan."
        ),
        "market_regime": {
            "label": "NEUTRAL",
            "risk_state": "NEUTRAL",
            "should_trade": False,
            "confidence": 0.0,
            "tradeability": "WAIT",
            "summary": reason,
            "trend": "SIDEWAYS",
            "volatility": "NORMAL",
            "score": 0,
            "vix": None,
            "breadth": None,
            "entropy": None,
        },
        "market_pulse": {},
        "top_5": [],
        "near_miss": [],
        "filter_funnel": {
            "universe": 0,
            "signals_triggered": 0,
            "score_above_6": 0,
            "actionable_above_7": 0,
            "high_conviction_above_8": 0,
            "note": reason,
        },
        "best_setup_family": None,
        "family_breakdown": {},
        "avoid": [reason],
        "what_changed": [reason],
        "event_risks": [],
        "sector_summary": {},
        "action_summary": {},
        "ai_narrative": None,
        "decision_authority": authority,
        "todays_decision": {
            "day_state": "LIVE_UNAVAILABLE",
            "hero_label": "Live scan required",
            "deploy_posture": "WAIT",
            "deploy_label": "Live-only — no fallback board",
            "can_deploy_today": False,
        },
        "trust": {
            "mode": "PAPER",
            "source": "live-unavailable",
            "freshness": "UNAVAILABLE",
            "stale": True,
            "reason": reason,
            "live_only": True,
            "ai_powered": False,
            "as_of": now.isoformat() + "Z",
        },
        "live_only_blocked": True,
        "decision_quality": intel["decision_quality"],
        "opportunity_intelligence": intel["opportunity_intelligence"],
        "generated_at": now.isoformat() + "Z",
    }


def build_live_unavailable_ranked(*, reason: str) -> Dict[str, Any]:
    """Playbook/ranked shape when live pipeline required but unavailable."""
    saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "count": 0,
        "opportunities": [],
        "near_miss": [],
        "avoid_grouped": {"total": 0, "groups": []},
        "rejection_clusters": [],
        "filter_funnel": {
            "universe_scanned": 0,
            "watch_qualified_setups": 0,
            "deploy_qualified_setups": 0,
            "high_score_setups": 0,
            "execution_ready_setups": 0,
        },
        "cached": False,
        "stale": False,
        "source": "live-unavailable",
        "warning": reason,
        "board_mode": "live_unavailable",
        "board_mode_label": "Live board unavailable",
        "board_message": reason,
        "board_explanation": (
            "CC_LIVE_DATA_ONLY is set — brief and disk snapshot fallbacks are disabled. "
            "Retry with refresh=true or run an engine cycle."
        ),
        "snapshot_timestamp": saved_at,
        "live_only_blocked": True,
        "trust": {
            "stale": True,
            "source": "live-unavailable",
            "live_only": True,
            "reason": reason,
        },
        "decision_authority": _suspended_authority(reason=reason),
    }
