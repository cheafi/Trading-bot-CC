"""Alpha quality evaluator — report contract."""

from __future__ import annotations

from src.services.alpha_quality_evaluator import evaluate_alpha_quality


def _blocked_truth():
    return {
        "deploy_authority": False,
        "deploy_qualified_count": 0,
        "execution_readiness": {"broker_connected": False},
        "reason_codes": ["BROKER_OFFLINE"],
        "primary_blocker": "BROKER_OFFLINE",
    }


def test_evaluator_learning_mode_low_n():
    report = evaluate_alpha_quality(
        opportunities=[{"stage": "near_miss", "forward_r": 0.2}],
        forward_summary={"sample_size": 3},
        near_miss_rows=[{"ticker": "AAPL"}],
        capital_governor={"truth": _blocked_truth()},
        persist=False,
    )
    assert report["status"] == "learning"
    assert report["learning_mode"] is True
    assert report["oi_lift_display"] == "learning"
    assert report["may_authorize_deploy"] is False
    assert report["authority_effect"] == "none"


def test_evaluator_detects_hit_rate_trap():
    outcomes = [{"forward_r": 0.05} for _ in range(8)] + [{"forward_r": 1.2}]
    report = evaluate_alpha_quality(
        opportunities=outcomes,
        forward_outcomes=outcomes,
        forward_summary={"sample_size": 20, "false_deploy_rate": 0.1},
        persist=False,
    )
    assert report["sample_size"] == 20
    assert report["may_authorize_deploy"] is False


def test_evaluator_no_fake_precision_when_low_n():
    report = evaluate_alpha_quality(
        forward_summary={"sample_size": 2},
        persist=False,
    )
    assert report["false_positive_rate"] is None
    assert report["cost_adj_expectancy_display"] == "learning"
