"""Opportunity quality engine — authority-gated recommendations."""

from __future__ import annotations

from src.services.opportunity_quality_engine import evaluate_opportunity_quality


def _truth(*, deploy=False, broker=False):
    return {
        "deploy_authority": deploy,
        "execution_readiness": {
            "broker_connected": broker,
            "trade_handoff_ready": broker,
        },
        "primary_blocker": "broker offline",
    }


def test_broker_offline_prevents_deploy_candidate():
    q = evaluate_opportunity_quality(
        {"ticker": "NVDA", "action": "TRADE", "execution_ready": True, "score": 9.0},
        truth=_truth(deploy=True, broker=False),
    )
    assert q["quality_bucket"] != "deploy_candidate"
    assert q["recommended_action"] != "deploy_review"


def test_research_only_prevents_deploy_recommendation():
    q = evaluate_opportunity_quality(
        {"ticker": "AAPL", "action": "TRADE", "execution_ready": True},
        truth=_truth(deploy=True, broker=True),
        surface="dossier",
    )
    assert q["quality_bucket"] == "research_only"
    assert q["recommended_action"] == "review_dossier"


def test_conflicting_signal_families_downgrade_quality():
    q = evaluate_opportunity_quality(
        {
            "ticker": "KO",
            "action": "WATCH",
            "score": 8.0,
            "evidence_conflict": True,
            "risk_reward": 2.5,
        },
        truth=_truth(deploy=True, broker=True),
    )
    assert q["evidence_conflict"] is True
    assert q["opportunity_quality"] < 0.75


def test_low_sample_size_widens_confidence_band():
    q = evaluate_opportunity_quality(
        {"ticker": "XLP", "action": "WATCH", "score": 7.5},
        truth=_truth(),
    )
    assert "wide" in q["confidence_band"] or "learning" in q["confidence_band"]


def test_cost_slippage_can_downgrade():
    q = evaluate_opportunity_quality(
        {
            "ticker": "IBM",
            "action": "WATCH",
            "score": 8.0,
            "gross_edge_score": 8.0,
            "net_edge_score": 4.0,
        },
        truth=_truth(deploy=True, broker=True),
    )
    assert q["cost_adjusted_pass"] is False
    assert "cost/slippage" in " ".join(q["missing_evidence"]).lower() or not q["cost_adjusted_pass"]
