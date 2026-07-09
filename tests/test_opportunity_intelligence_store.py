"""Opportunity intelligence store — persist, dedupe, authority rules."""

from __future__ import annotations

from src.services.opportunity_intelligence_store import (
    FUNNEL_STAGES,
    OpportunityCandidate,
    OpportunityIntelligenceStore,
    OpportunityScoreSnapshot,
    OpportunityStageTransition,
    apply_authority_effect_rules,
    cap_stage_for_surface,
)


def test_persist_candidate_append_only(tmp_path):
    store = OpportunityIntelligenceStore(
        candidates_path=str(tmp_path / "candidates.jsonl"),
        snapshots_path=str(tmp_path / "snapshots.jsonl"),
        transitions_path=str(tmp_path / "transitions.jsonl"),
        index_path=str(tmp_path / "index.db"),
    )
    cand = OpportunityCandidate(
        candidate_id="cand_test_1",
        ticker="AAPL",
        stage="research_hit",
        source_surface="discovery",
        dedupe_key="abc123",
    )
    stored = store.persist_candidate(cand, deploy_authority=True)
    assert stored["ticker"] == "AAPL"
    assert stored["may_authorize_deploy"] is False
    assert stored["authority_effect"] == "none"
    loaded = store.load_candidates()
    assert len(loaded) == 1


def test_research_surface_authority_effect_none():
    auth = apply_authority_effect_rules(
        surface="discovery",
        stage="deploy_review",
        deploy_authority=True,
    )
    assert auth["authority_effect"] == "none"
    assert auth["may_authorize_deploy"] is False


def test_cap_stage_for_discovery():
    assert cap_stage_for_surface("playbook_review", "discovery") == "research_hit"
    assert cap_stage_for_surface("research_hit", "discovery") == "research_hit"


def test_snapshot_and_transition(tmp_path):
    store = OpportunityIntelligenceStore(
        candidates_path=str(tmp_path / "candidates.jsonl"),
        snapshots_path=str(tmp_path / "snapshots.jsonl"),
        transitions_path=str(tmp_path / "transitions.jsonl"),
        use_index=False,
    )
    snap = OpportunityScoreSnapshot(
        snapshot_id="snap_1",
        candidate_id="cand_1",
        ticker="NVDA",
        stage="evidence_candidate",
        evidence_grade="B",
        sample_size=3,
    )
    store.persist_snapshot(snap)
    trans = OpportunityStageTransition(
        transition_id="trans_1",
        candidate_id="cand_1",
        ticker="NVDA",
        from_stage="research_hit",
        to_stage="evidence_candidate",
        source_surface="rs",
    )
    store.persist_transition(trans)
    assert len(store.load_snapshots()) == 1
    assert len(store.load_transitions()) == 1


def test_funnel_stages_order():
    assert FUNNEL_STAGES[0] == "raw_universe"
    assert FUNNEL_STAGES[-1] == "capital_candidate"
