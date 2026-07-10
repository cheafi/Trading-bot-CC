"""
Threshold Proposal Service — derive proposals from Alpha Review signals.

Sources: Alpha Review, QA, overfit, missed opp, governor QA.
Never auto-loosen; infrastructure misses do not propose loosen.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.services.threshold_governance_store import (
    PROPOSAL_TYPES,
    ThresholdGovernanceStore,
    ThresholdProposal,
    get_threshold_governance_store,
    make_proposal_id,
)
from src.services.threshold_registry import (
    get_threshold,
    is_risk_reducing,
    list_thresholds,
    registry_summary,
)

INFRASTRUCTURE_MISS_CATEGORIES = frozenset(
    {"infrastructure", "data_gap", "broker_offline", "session_unavailable"}
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _tighten_delta(defn_key: str, *, pct: float = 0.05) -> Optional[float]:
    defn = get_threshold(defn_key)
    if not defn:
        return None
    cur = defn.current_value
    if defn.risk_direction == "higher_is_stricter":
        return round(cur * (1.0 + pct), 4)
    return round(cur * (1.0 - pct), 4)


def _map_review_action_to_proposal(action: str) -> str:
    mapping = {
        "tighten": "tighten",
        "collect_more_samples": "collect_more_samples",
        "retire": "retire_threshold",
        "mute": "retire_threshold",
        "keep": "no_change",
        "monitor": "no_change",
        "human_review": "loosen_review",
    }
    return mapping.get(action, "no_change")


def _should_skip_loosen(
    *,
    category: str,
    evidence: Dict[str, Any],
    proposal_type: str,
) -> bool:
    if proposal_type != "loosen_review":
        return False
    if category in INFRASTRUCTURE_MISS_CATEGORIES:
        return True
    if evidence.get("infrastructure_miss") or evidence.get("data_gap"):
        return True
    return False


def propose_from_review_item(
    item: Dict[str, Any],
    *,
    source_report_id: str = "",
    source: str = "alpha_review",
) -> Optional[ThresholdProposal]:
    """Build a single proposal from an Alpha Review item."""
    action = str(item.get("recommended_action") or item.get("allowed_action") or "monitor")
    proposal_type = _map_review_action_to_proposal(action)
    category = str(item.get("category") or "")
    evidence = dict(item.get("evidence") or {})

    if _should_skip_loosen(category=category, evidence=evidence, proposal_type=proposal_type):
        return None

    threshold_key = str(evidence.get("threshold_key") or "")
    if not threshold_key:
        threshold_key = _infer_threshold_key(category, item)

    defn = get_threshold(threshold_key)
    if not defn and proposal_type not in ("collect_more_samples", "no_change"):
        return None

    current_value = defn.current_value if defn else 0.0
    proposed_value: Optional[float] = None

    if proposal_type == "tighten":
        proposed_value = _tighten_delta(threshold_key)
        if proposed_value is None or not is_risk_reducing(
            threshold_key, proposed_value, current_value=current_value
        ):
            return None
    elif proposal_type == "retire_threshold":
        proposed_value = current_value
    elif proposal_type == "loosen_review":
        proposed_value = evidence.get("proposed_loosen_value")
        if proposed_value is not None:
            proposed_value = _float(proposed_value)
    elif proposal_type == "collect_more_samples":
        proposed_value = None
    else:
        return None

    if proposal_type == "no_change":
        return None

    return ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key=threshold_key,
        proposal_type=proposal_type,
        status="open",
        current_value=current_value,
        proposed_value=proposed_value,
        rationale=str(item.get("summary") or item.get("title") or ""),
        source=source,
        source_report_id=source_report_id,
        evidence={
            **evidence,
            "category": category,
            "review_item_id": item.get("item_id"),
            "severity": item.get("severity"),
        },
        rollback_value=defn.rollback_value if defn else current_value,
        can_auto_loosen=False,
    )


def _infer_threshold_key(category: str, item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "").lower()
    if category == "overfit" or "overfit" in title:
        return "playbook.deploy_score_min"
    if category == "missed_opportunity":
        return "discovery.strict_filter_min"
    if category == "governor":
        return "governor.false_deploy_rate_max"
    if category == "sample":
        return "alpha.min_sample_lift"
    if category == "conversion":
        return "playbook.deploy_rr_min"
    if "position" in title or "capital" in title:
        return "capital.max_position_risk_pct"
    if "thesis" in title:
        return "playbook.thesis_min"
    return "opportunity.min_sample"


def propose_from_alpha_review(
    report: Dict[str, Any],
    *,
    governor_qa: Optional[Dict[str, Any]] = None,
    alpha_quality: Optional[Dict[str, Any]] = None,
) -> List[ThresholdProposal]:
    """Generate proposals from a full Alpha Review report."""
    proposals: List[ThresholdProposal] = []
    report_id = str(report.get("report_id") or "")

    for item in report.get("review_items") or []:
        p = propose_from_review_item(item, source_report_id=report_id)
        if p:
            proposals.append(p)

    for item in report.get("human_review_items") or []:
        p = propose_from_review_item(item, source_report_id=report_id)
        if p and p.proposal_type != "no_change":
            proposals.append(p)

    gq = governor_qa or report.get("governor_review") or {}
    if gq.get("human_review_suggested") or gq.get("qa_adjustment"):
        defn = get_threshold("governor.false_deploy_rate_max")
        if defn:
            proposed = _tighten_delta("governor.false_deploy_rate_max", pct=0.1)
            if proposed and is_risk_reducing(
                "governor.false_deploy_rate_max", proposed
            ):
                proposals.append(
                    ThresholdProposal(
                        proposal_id=make_proposal_id(),
                        threshold_key="governor.false_deploy_rate_max",
                        proposal_type="tighten",
                        current_value=defn.current_value,
                        proposed_value=proposed,
                        rationale=f"Governor QA: {gq.get('qa_adjustment', 'review suggested')}",
                        source="governor_qa",
                        source_report_id=report_id,
                        evidence={"governor_qa": gq},
                        rollback_value=defn.rollback_value,
                    )
                )

    aq = alpha_quality or {}
    if str(aq.get("overfit_risk") or "") in ("medium", "high"):
        defn = get_threshold("playbook.deploy_score_min")
        if defn:
            proposed = _tighten_delta("playbook.deploy_score_min", pct=0.05)
            if proposed:
                proposals.append(
                    ThresholdProposal(
                        proposal_id=make_proposal_id(),
                        threshold_key="playbook.deploy_score_min",
                        proposal_type="tighten",
                        current_value=defn.current_value,
                        proposed_value=proposed,
                        rationale=f"Overfit guard: risk={aq.get('overfit_risk')}",
                        source="alpha_qa",
                        source_report_id=report_id,
                        evidence={"overfit_risk": aq.get("overfit_risk")},
                        rollback_value=defn.rollback_value,
                    )
                )

    n = int(report.get("sample_size") or aq.get("sample_size") or 0)
    min_lift = get_threshold("alpha.min_sample_lift")
    if min_lift and n < min_lift.current_value:
        proposals.append(
            ThresholdProposal(
                proposal_id=make_proposal_id(),
                threshold_key="alpha.min_sample_lift",
                proposal_type="collect_more_samples",
                current_value=min_lift.current_value,
                proposed_value=None,
                rationale=f"Insufficient samples ({n} < {int(min_lift.current_value)})",
                source="alpha_review",
                source_report_id=report_id,
                evidence={"sample_size": n},
                rollback_value=min_lift.rollback_value,
            )
        )

    missed = aq.get("missed_opportunity_review") or report.get("missed_opportunity")
    if isinstance(missed, dict) and missed.get("infrastructure_miss"):
        pass
    elif isinstance(missed, dict) and missed.get("count", 0) > 3:
        defn = get_threshold("discovery.strict_filter_min")
        if defn:
            proposed = round(defn.current_value * 0.97, 4)
            if proposed < defn.current_value:
                proposals.append(
                    ThresholdProposal(
                        proposal_id=make_proposal_id(),
                        threshold_key="discovery.strict_filter_min",
                        proposal_type="loosen_review",
                        current_value=defn.current_value,
                        proposed_value=proposed,
                        rationale="Missed opportunities — human review only, never auto-loosen",
                        source="missed_opportunity",
                        source_report_id=report_id,
                        evidence=missed,
                        rollback_value=defn.rollback_value,
                    )
                )

    return _dedupe_proposals(proposals)


def _dedupe_proposals(proposals: Sequence[ThresholdProposal]) -> List[ThresholdProposal]:
    seen: Dict[tuple, ThresholdProposal] = {}
    for p in proposals:
        key = (p.threshold_key, p.proposal_type)
        if key not in seen or p.proposal_type == "tighten":
            seen[key] = p
    return list(seen.values())


def build_threshold_proposals(
    *,
    alpha_review: Optional[Dict[str, Any]] = None,
    alpha_quality: Optional[Dict[str, Any]] = None,
    governor_qa: Optional[Dict[str, Any]] = None,
    persist: bool = False,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """Build proposal batch from review signals."""
    if not alpha_review:
        return {
            "proposals": [],
            "count": 0,
            "registry": registry_summary(),
            "authority_effect": "none",
            "may_authorize_deploy": False,
            "can_auto_loosen": False,
        }

    proposals = propose_from_alpha_review(
        alpha_review,
        governor_qa=governor_qa,
        alpha_quality=alpha_quality,
    )
    st = store or get_threshold_governance_store()
    if persist:
        for p in proposals:
            st.append_proposal(p)

    return {
        "proposals": [p.to_dict() for p in proposals],
        "count": len(proposals),
        "by_type": _count_by_type(proposals),
        "registry": registry_summary(),
        "source_report_id": alpha_review.get("report_id"),
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "can_auto_loosen": False,
        "no_live_changes": True,
    }


def _count_by_type(proposals: Sequence[ThresholdProposal]) -> Dict[str, int]:
    counts: Dict[str, int] = {t: 0 for t in PROPOSAL_TYPES}
    for p in proposals:
        counts[p.proposal_type] = counts.get(p.proposal_type, 0) + 1
    return counts


def threshold_governance_summary_for_dashboard(
    *,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """Compact summary for decision_quality / Ops payload."""
    st = store or get_threshold_governance_store()
    s = st.summary()
    open_n = int(s.get("open_count") or 0)
    shadow_n = int(s.get("shadow_count") or 0)
    live_n = int(s.get("live_change_count") or 0)
    return {
        "status_line": (
            f"Threshold Review: {open_n} open · {shadow_n} shadow · "
            f"{'no live changes' if live_n == 0 else f'{live_n} live (audit)'}"
        ),
        "open_count": open_n,
        "shadow_count": shadow_n,
        "live_change_count": live_n,
        "open_proposals": (s.get("open_proposals") or [])[:5],
        "shadow_proposals": (s.get("shadow_proposals") or [])[:5],
        "registry_count": len(list_thresholds()),
        "can_auto_loosen": False,
        "no_live_changes_from_analytics": True,
        "collapsed": True,
        "authority_effect": "none",
        "may_authorize_deploy": False,
    }
