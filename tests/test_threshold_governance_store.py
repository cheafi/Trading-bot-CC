"""Threshold governance store — append-only audit."""

from __future__ import annotations

from src.services.threshold_governance_store import (
    ThresholdDecision,
    ThresholdGovernanceStore,
    ThresholdLiveChange,
    ThresholdProposal,
    make_change_id,
    make_decision_id,
    make_proposal_id,
)


def test_append_proposal(tmp_path):
    store = ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.deploy_score_min",
        proposal_type="tighten",
        current_value=72.0,
        proposed_value=75.0,
        rationale="test",
    )
    store.append_proposal(p)
    rows = store.load_proposals()
    assert len(rows) == 1
    assert rows[0]["can_auto_loosen"] is False
    assert rows[0]["may_authorize_deploy"] is False


def test_open_and_shadow_counts(tmp_path):
    store = ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    open_p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="alpha.min_sample_lift",
        proposal_type="collect_more_samples",
        status="open",
        current_value=12.0,
    )
    shadow_p = ThresholdProposal(
        proposal_id=make_proposal_id(),
        threshold_key="playbook.deploy_rr_min",
        proposal_type="tighten",
        status="approved_shadow",
        current_value=2.5,
        proposed_value=2.7,
    )
    store.append_proposal(open_p)
    store.append_proposal(shadow_p)
    assert len(store.open_proposals()) == 1
    assert len(store.shadow_proposals()) == 1
    summary = store.summary()
    assert summary["no_live_changes_from_analytics"] is True


def test_live_change_with_rollback(tmp_path):
    store = ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    change = ThresholdLiveChange(
        change_id=make_change_id(),
        proposal_id="tprop_test",
        threshold_key="playbook.deploy_score_min",
        prior_value=72.0,
        new_value=75.0,
        rollback_value=72.0,
        reviewer="operator",
        rationale="promoted",
    )
    store.append_live_change(change)
    store.append_decision(
        ThresholdDecision(
            decision_id=make_decision_id(),
            proposal_id="tprop_test",
            action="promote_to_live",
            reviewer="operator",
            rationale="ok",
            prior_status="approved_shadow",
            new_status="promoted",
        )
    )
    assert len(store.load_live_changes()) == 1
    assert store.load_live_changes()[0]["rollback_value"] == 72.0
