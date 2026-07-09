"""Capital governor QA inputs — tighten-only from Alpha Quality."""

from __future__ import annotations

from src.services.capital_allocation_governor import evaluate_capital_allocation


def _deploy_truth():
    return {
        "deploy_authority": True,
        "deploy_qualified_count": 2,
        "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
    }


def test_qa_overfit_high_tightens():
    base = evaluate_capital_allocation(truth=_deploy_truth(), sample_size=20)
    qa = evaluate_capital_allocation(
        truth=_deploy_truth(),
        sample_size=20,
        overfit_risk="high",
        alpha_quality_status="noisy",
    )
    assert qa["max_new_risk_pct"] <= base["max_new_risk_pct"]
    assert qa["qa_adjustment"] == "tighten"
    assert "QA_OVERFIT_HIGH" in qa["qa_reason_codes"]
    assert qa["can_loosen_automatically"] is False


def test_qa_human_review_on_missed_conservative():
    out = evaluate_capital_allocation(
        truth=_deploy_truth(),
        sample_size=20,
        missed_opportunity_review={"too_conservative_count": 2, "human_review_suggested": True},
    )
    assert out["human_review_suggested"] is True
    assert out["requires_human_review"] is True
    assert "QA_MISSED_OPPORTUNITY_REVIEW" in out["qa_reason_codes"]


def test_qa_never_auto_loosen():
    out = evaluate_capital_allocation(
        truth=_deploy_truth(),
        alpha_quality_status="deteriorating",
        false_positive_rate=0.3,
        overfit_risk="medium",
        sample_size=25,
    )
    assert out["can_loosen_automatically"] is False
    assert out["learning_feedback"]["never_auto_loosen"] is True
    assert out["may_authorize_deploy"] is False
