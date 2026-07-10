"""
Threshold Approval Workflow — human-gated threshold change lifecycle.

submit → approve_for_shadow → promote_to_live (shadow required unless tighten-only)
Also: reject, defer, request_more_samples, rollback.
Reviewer + rationale required for all transitions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.threshold_governance_store import (
    PROPOSAL_STATUSES,
    ThresholdDecision,
    ThresholdGovernanceStore,
    ThresholdLiveChange,
    ThresholdProposal,
    get_threshold_governance_store,
    make_change_id,
    make_decision_id,
)
from src.services.threshold_registry import (
    get_threshold,
    is_risk_reducing,
    validate_proposed_value,
)


def _require_reviewer(reviewer: str, rationale: str) -> Optional[str]:
    if not reviewer or not reviewer.strip():
        return "reviewer required"
    if not rationale or not rationale.strip():
        return "rationale required"
    return None


def _record_decision(
    store: ThresholdGovernanceStore,
    *,
    proposal_id: str,
    action: str,
    reviewer: str,
    rationale: str,
    prior_status: str,
    new_status: str,
) -> str:
    decision = ThresholdDecision(
        decision_id=make_decision_id(),
        proposal_id=proposal_id,
        action=action,
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior_status,
        new_status=new_status,
    )
    return store.append_decision(decision)


def _proposal_from_row(row: Dict[str, Any]) -> ThresholdProposal:
    return ThresholdProposal(**{k: v for k, v in row.items() if k in ThresholdProposal.__dataclass_fields__})


def submit_proposal(
    proposal: ThresholdProposal,
    *,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """Submit a new threshold proposal (open status)."""
    st = store or get_threshold_governance_store()
    proposal.status = "open"
    proposal.can_auto_loosen = False
    st.append_proposal(proposal)
    return {"ok": True, "proposal": proposal.to_dict(), "authority_effect": "none"}


def approve_for_shadow(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    proposal = _proposal_from_row(row)
    if proposal.proposal_type == "loosen_review":
        return {
            "ok": False,
            "error": "loosen_review cannot auto-approve; requires explicit human promote",
        }
    prior = proposal.status
    proposal.status = "approved_shadow"
    proposal.reviewer = reviewer
    proposal.reviewer_rationale = rationale
    st.update_proposal(proposal)
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="approve_for_shadow",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior,
        new_status="approved_shadow",
    )
    return {"ok": True, "proposal": proposal.to_dict(), "authority_effect": "none"}


def reject_proposal(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    proposal = _proposal_from_row(row)
    prior = proposal.status
    proposal.status = "rejected"
    proposal.reviewer = reviewer
    proposal.reviewer_rationale = rationale
    st.update_proposal(proposal)
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="reject",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior,
        new_status="rejected",
    )
    return {"ok": True, "proposal": proposal.to_dict(), "authority_effect": "none"}


def defer_proposal(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    proposal = _proposal_from_row(row)
    prior = proposal.status
    proposal.status = "deferred"
    proposal.reviewer = reviewer
    proposal.reviewer_rationale = rationale
    st.update_proposal(proposal)
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="defer",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior,
        new_status="deferred",
    )
    return {"ok": True, "proposal": proposal.to_dict(), "authority_effect": "none"}


def request_more_samples(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    proposal = _proposal_from_row(row)
    prior = proposal.status
    proposal.status = "more_samples"
    proposal.reviewer = reviewer
    proposal.reviewer_rationale = rationale
    st.update_proposal(proposal)
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="request_more_samples",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior,
        new_status="more_samples",
    )
    return {"ok": True, "proposal": proposal.to_dict(), "authority_effect": "none"}


def acknowledge_proposal(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str = "acknowledged",
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """Acknowledge without changing threshold — audit trail only."""
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="acknowledge",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=row.get("status", "open"),
        new_status=row.get("status", "open"),
    )
    return {"ok": True, "proposal": row, "authority_effect": "none"}


def promote_to_live(
    proposal_id: str,
    *,
    reviewer: str,
    rationale: str,
    shadow_run_id: str = "",
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """
    Promote approved proposal to live registry value.
    Requires shadow unless proposal_type is tighten (risk-reducing only).
    """
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    row = st.get_proposal(proposal_id)
    if not row:
        return {"ok": False, "error": "proposal not found"}
    proposal = _proposal_from_row(row)

    if proposal.proposal_type == "loosen_review":
        return {"ok": False, "error": "loosen_review cannot be promoted to live automatically"}

    if proposal.status not in ("approved_shadow", "shadow") and proposal.proposal_type != "tighten":
        return {
            "ok": False,
            "error": "promote_to_live requires shadow approval unless tighten-only",
        }

    if proposal.proposal_type != "tighten" and not shadow_run_id:
        return {"ok": False, "error": "shadow_run_id required for non-tighten promotions"}

    proposed_value = proposal.proposed_value
    if proposed_value is None:
        return {"ok": False, "error": "no proposed_value"}

    valid, msg = validate_proposed_value(
        proposal.threshold_key,
        proposed_value,
        proposal_type=proposal.proposal_type,
    )
    if not valid:
        return {"ok": False, "error": msg}

    defn = get_threshold(proposal.threshold_key)
    if not defn:
        return {"ok": False, "error": "unknown threshold key"}

    if not is_risk_reducing(proposal.threshold_key, proposed_value):
        if proposal.proposal_type == "tighten":
            return {"ok": False, "error": "tighten must be risk-reducing"}

    prior = proposal.status
    proposal.status = "promoted"
    proposal.reviewer = reviewer
    proposal.reviewer_rationale = rationale
    proposal.shadow_run_id = shadow_run_id
    st.update_proposal(proposal)

    change = ThresholdLiveChange(
        change_id=make_change_id(),
        proposal_id=proposal_id,
        threshold_key=proposal.threshold_key,
        prior_value=proposal.current_value,
        new_value=proposed_value,
        rollback_value=proposal.rollback_value or proposal.current_value,
        reviewer=reviewer,
        rationale=rationale,
    )
    st.append_live_change(change)
    _record_decision(
        st,
        proposal_id=proposal_id,
        action="promote_to_live",
        reviewer=reviewer,
        rationale=rationale,
        prior_status=prior,
        new_status="promoted",
    )
    return {
        "ok": True,
        "proposal": proposal.to_dict(),
        "live_change": change.to_dict(),
        "authority_effect": "none",
        "may_authorize_deploy": False,
    }


def rollback_live_change(
    change_id: str,
    *,
    reviewer: str,
    rationale: str,
    store: Optional[ThresholdGovernanceStore] = None,
) -> Dict[str, Any]:
    """Record rollback of a live threshold change."""
    err = _require_reviewer(reviewer, rationale)
    if err:
        return {"ok": False, "error": err}
    st = store or get_threshold_governance_store()
    changes = st.load_live_changes(limit=200)
    target = next((c for c in changes if c.get("change_id") == change_id), None)
    if not target:
        return {"ok": False, "error": "live change not found"}
    if target.get("rolled_back"):
        return {"ok": False, "error": "already rolled back"}

    rollback = ThresholdLiveChange(
        change_id=make_change_id(),
        proposal_id=str(target.get("proposal_id") or ""),
        threshold_key=str(target.get("threshold_key") or ""),
        prior_value=float(target.get("new_value") or 0),
        new_value=float(target.get("rollback_value") or target.get("prior_value") or 0),
        rollback_value=float(target.get("prior_value") or 0),
        action="rollback",
        reviewer=reviewer,
        rationale=rationale,
    )
    st.append_live_change(rollback)

    proposal_id = str(target.get("proposal_id") or "")
    if proposal_id:
        row = st.get_proposal(proposal_id)
        if row:
            proposal = _proposal_from_row(row)
            proposal.status = "rolled_back"
            st.update_proposal(proposal)
        _record_decision(
            st,
            proposal_id=proposal_id,
            action="rollback",
            reviewer=reviewer,
            rationale=rationale,
            prior_status="promoted",
            new_status="rolled_back",
        )

    return {
        "ok": True,
        "rollback_change": rollback.to_dict(),
        "authority_effect": "none",
    }
