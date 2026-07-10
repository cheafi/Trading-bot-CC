"""Threshold proposal service — from Alpha Review signals."""

from __future__ import annotations

from src.services.threshold_proposal_service import (
    build_threshold_proposals,
    propose_from_alpha_review,
    propose_from_review_item,
    threshold_governance_summary_for_dashboard,
)
from src.services.threshold_governance_store import ThresholdGovernanceStore


def test_propose_tighten_from_overfit_item():
    item = {
        "item_id": "ari_test",
        "title": "Overfit risk elevated",
        "category": "overfit",
        "recommended_action": "tighten",
        "summary": "Raise deploy score gate",
        "evidence": {"threshold_key": "playbook.deploy_score_min"},
    }
    p = propose_from_review_item(item)
    assert p is not None
    assert p.proposal_type == "tighten"
    assert p.proposed_value > p.current_value
    assert p.can_auto_loosen is False


def test_infrastructure_miss_skips_loosen():
    item = {
        "item_id": "ari_infra",
        "title": "Data gap",
        "category": "infrastructure",
        "recommended_action": "human_review",
        "summary": "Broker offline",
        "evidence": {"infrastructure_miss": True},
    }
    assert propose_from_review_item(item) is None


def test_propose_from_alpha_review_governor_qa():
    report = {
        "report_id": "arpt_test",
        "sample_size": 3,
        "review_items": [],
        "human_review_items": [],
        "governor_review": {
            "human_review_suggested": True,
            "qa_adjustment": "tighten_capital",
        },
    }
    proposals = propose_from_alpha_review(report)
    types = {p.proposal_type for p in proposals}
    assert "collect_more_samples" in types
    assert "tighten" in types
    assert all(p.can_auto_loosen is False for p in proposals)


def test_build_threshold_proposals_persist(tmp_path):
    store = ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    report = {
        "report_id": "arpt_persist",
        "sample_size": 2,
        "review_items": [
            {
                "item_id": "x",
                "title": "Low sample",
                "category": "sample",
                "recommended_action": "collect_more_samples",
                "summary": "Need more data",
            }
        ],
    }
    batch = build_threshold_proposals(alpha_review=report, persist=True, store=store)
    assert batch["count"] >= 1
    assert batch["may_authorize_deploy"] is False
    assert len(store.load_proposals()) >= 1


def test_dashboard_summary_line(tmp_path):
    store = ThresholdGovernanceStore(
        proposals_path=str(tmp_path / "proposals.jsonl"),
        decisions_path=str(tmp_path / "decisions.jsonl"),
        live_changes_path=str(tmp_path / "live.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    s = threshold_governance_summary_for_dashboard(store=store)
    assert "Threshold Review:" in s["status_line"]
    assert s["can_auto_loosen"] is False
    assert s["may_authorize_deploy"] is False
