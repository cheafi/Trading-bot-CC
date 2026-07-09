"""Baseline comparison — lift only with sample threshold."""

from __future__ import annotations

from src.services.opportunity_baseline_comparison import compare_oi_to_baselines


def test_lift_learning_when_n_low():
    out = compare_oi_to_baselines(
        oi_outcomes=[{"forward_r": 0.3}],
        discovery_hits=[{"forward_r": 0.1}],
        min_sample=12,
    )
    assert out["oi_lift_display"] == "learning"
    assert out["learning_mode"] is True
    assert out["may_authorize_deploy"] is False
    assert out["authority_effect"] == "none"


def test_lift_reported_when_sample_ok():
    oi = [{"forward_r": 0.5} for _ in range(15)]
    scanner = [{"forward_r": 0.1} for _ in range(15)]
    out = compare_oi_to_baselines(
        oi_outcomes=oi,
        discovery_hits=scanner,
        min_sample=12,
    )
    assert out["learning_mode"] is False
    assert out["oi_lift_display"] != "learning"
    assert out["oi_cohort"]["mean_forward_r"] == 0.5
