"""Threshold approval workflow — human-gated transitions."""

from __future__ import annotations

from src.services.threshold_approval_workflow import (
    acknowledge_proposal,
    approve_for_shadow,
    defer_proposal,
    promote_to_live,
    reject_proposal,
    rollback_live_change,
    submit_proposal,
)
from src.services.threshold_governance_store import (
    ThresholdGovernanceStore,
    ThresholdProposal,
    make_proposal_id,
)


def _store(tmp_path) -> ThresholdGovernanceStore:
    return ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )


def test_approve_for_shadow_requires_reviewer(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.deploy_score_min",
        proposal_type="tighten",
        current_value=72.0,
        proposed_value=75.0,
        rollback_value=72.0,
    )
    submit_proposal(p, store=store)
    bad = approve_for_shadow(p.proposal_id, reviewer="", rationale="", store=store)
    assert bad["ok"] is False
    good = approve_for_shadow(
        p.proposal_id, reviewer="alice", rationale="shadow first", store=store
    )
    assert good["ok"] is True
    assert good["proposal"]["status"] == "approved_shadow"


def test_loosen_review_cannot_approve_shadow(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="discovery.strict_filter_min",
        proposal_type="loosen_review",
        current_value=65.0,
        proposed_value=63.0,
        rollback_value=65.0,
    )
    submit_proposal(p, store=store)
    result = approve_for_shadow(
        p.proposal_id, reviewer="alice", rationale="try", store=store
    )
    assert result["ok"] is False


def test_promote_tighten_only_without_shadow_id(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.deploy_score_min",
        proposal_type="tighten",
        status="open",
        current_value=72.0,
        proposed_value=75.0,
        rollback_value=72.0,
    )
    submit_proposal(p, store=store)
    result = promote_to_live(
        p.proposal_id,
        reviewer="alice",
        rationale="risk reducing tighten",
        store=store,
    )
    assert result["ok"] is True
    assert result["live_change"]["rollback_value"] == 72.0


def test_reject_and_defer(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="alpha.min_sample_lift",
        proposal_type="collect_more_samples",
        current_value=12.0,
    )
    submit_proposal(p, store=store)
    reject = reject_proposal(
        p.proposal_id, reviewer="bob", rationale="not now", store=store
    )
    assert reject["ok"] is True
    assert reject["proposal"]["status"] == "rejected"

    p2 = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.thesis_min",
        proposal_type="tighten",
        current_value=0.55,
        proposed_value=0.6,
        rollback_value=0.55,
    )
    submit_proposal(p2, store=store)
    defer = defer_proposal(
        p2.proposal_id, reviewer="bob", rationale="wait", store=store
    )
    assert defer["ok"] is True


def test_acknowledge_audit_only(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="governor.dd_budget_pct",
        proposal_type="tighten",
        current_value=15.0,
        proposed_value=12.0,
        rollback_value=15.0,
    )
    submit_proposal(p, store=store)
    result = acknowledge_proposal(
        p.proposal_id, reviewer="ops", rationale="seen", store=store
    )
    assert result["ok"] is True
    assert len(store.load_decisions()) == 1


def test_rollback_live_change(tmp_path):
    store = _store(tmp_path)
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.deploy_score_min",
        proposal_type="tighten",
        current_value=72.0,
        proposed_value=75.0,
        rollback_value=72.0,
    )
    submit_proposal(p, store=store)
    promoted = promote_to_live(
        p.proposal_id,
        reviewer="alice",
        rationale="tighten",
        store=store,
    )
    change_id = promoted["live_change"]["change_id"]
    rolled = rollback_live_change(
        change_id,
        reviewer="alice",
        rationale="revert",
        store=store,
    )
    assert rolled["ok"] is True
