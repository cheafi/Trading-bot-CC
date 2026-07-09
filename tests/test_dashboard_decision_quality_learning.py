"""Dashboard decision quality learning metrics — compact block contract."""

from __future__ import annotations

from src.services.opportunity_quality_engine import build_decision_quality_dashboard


def test_dashboard_learning_mode_when_n_low():
    dq = build_decision_quality_dashboard(
        truth={"deploy_qualified_count": 0},
        forward_summary={"sample_size": 2, "learning_mode": True},
        family_health={"aggregate_sample_size": 3, "learning_mode": True},
        journal={"events": [], "summary": {"total": 5}},
        journal_store_summary={"total": 5},
        outcome_store_summary={"total_outcomes": 0, "distinct_events": 0},
        no_edge_tracking={"no_edge_samples": 1, "quality_label": "learning"},
        capital={"capital_mode": "monitor_only", "learning_adjustment_reason": "LOW_SAMPLE_SIZE"},
    )
    assert dq["state_label"] == "Learning mode"
    assert dq["metrics"]["learning_mode"] is True
    assert dq["metrics"]["forward_r_5d"] is None
    assert dq["metrics"]["false_deploy_rate"] is None
    assert dq["metrics"]["journal_events_n"] == 5
    assert dq["may_authorize_deploy"] is False
    assert dq["authority_effect"] == "none"


def test_dashboard_includes_governor_and_store_counts():
    dq = build_decision_quality_dashboard(
        truth={"deploy_qualified_count": 2},
        forward_summary={
            "sample_size": 25,
            "avg_forward_r_5d": 0.4,
            "false_deploy_rate": 0.1,
            "learning_mode": False,
        },
        family_health={
            "aggregate_sample_size": 30,
            "useful_families": ["setup_quality"],
            "noisy_families": ["timing"],
            "best_validated_family": "setup_quality",
            "noisy_family": "timing",
        },
        journal_store_summary={"total": 40},
        outcome_store_summary={"total_outcomes": 100, "distinct_events": 20},
        no_edge_tracking={"no_edge_samples": 8, "quality_label": "good_avoidance"},
        capital={
            "capital_mode": "selective_deploy",
            "learning_adjustment_reason": "NO_EDGE_GOOD_AVOIDANCE",
            "risk_mode_adjustment": None,
            "requires_human_review": False,
        },
    )
    assert dq["metrics"]["journal_events_n"] == 40
    assert dq["metrics"]["forward_outcomes_n"] == 100
    assert dq["metrics"]["no_edge_samples_n"] == 8
    assert dq["governor_adjustment"] == "NO_EDGE_GOOD_AVOIDANCE"
    assert dq["metrics"]["useful_families"] == ["setup_quality"]
    assert dq["metrics"]["noisy_families"] == ["timing"]
