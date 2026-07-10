"""Shadow threshold simulator — historical what-if."""

from __future__ import annotations

from src.services.shadow_threshold_simulator import (
    batch_simulate_proposals,
    simulate_proposal,
    simulate_threshold_change,
    would_pass_threshold,
)


def _rows():
    return [
        {"ticker": "AAPL", "composite_score": 80, "risk_reward": 3.0, "forward_r_5d": 1.2},
        {"ticker": "MSFT", "composite_score": 68, "risk_reward": 2.8, "forward_r_5d": -0.5},
        {"ticker": "NVDA", "composite_score": 74, "risk_reward": 2.2, "forward_r_5d": 0.3},
    ]


def test_would_pass_score_threshold():
    row = {"composite_score": 75}
    assert would_pass_threshold(row, "playbook.deploy_score_min", 72.0)
    assert not would_pass_threshold(row, "playbook.deploy_score_min", 80.0)


def test_simulate_tighten_rejects_more():
    result = simulate_threshold_change(
        threshold_key="playbook.deploy_score_min",
        current_value=72.0,
        proposed_value=78.0,
        historical_rows=_rows(),
    )
    assert result["would_reject"] >= 0
    assert result["risk_reducing"] is True
    assert result["may_authorize_deploy"] is False
    assert result["no_live_changes"] is True
    assert result["recommendation"] in (
        "approve_shadow",
        "defer",
        "reject",
        "collect_more_samples",
    )


def test_simulate_proposal_wrapper():
    proposal = {
        "proposal_id": "tprop_sim",
        "threshold_key": "playbook.deploy_rr_min",
        "proposal_type": "tighten",
        "current_value": 2.5,
        "proposed_value": 2.8,
    }
    result = simulate_proposal(proposal, historical_rows=_rows())
    assert result["proposal_id"] == "tprop_sim"
    assert "recommendation" in result


def test_batch_simulate():
    proposals = [
        {
            "proposal_id": "p1",
            "threshold_key": "playbook.deploy_score_min",
            "proposal_type": "tighten",
            "current_value": 72.0,
            "proposed_value": 76.0,
        }
    ]
    batch = batch_simulate_proposals(proposals, historical_rows=_rows())
    assert batch["count"] == 1
    assert batch["authority_effect"] == "none"
