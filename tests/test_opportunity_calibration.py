"""Opportunity calibration — learning mode, walk-forward gate."""

from __future__ import annotations

from src.services.opportunity_calibration import calibrate_opportunity


def test_learning_mode_low_sample():
    row = {"ticker": "AAPL", "score": 7.0}
    cal = calibrate_opportunity(row, forward_summary={"sample_size": 2})
    assert cal["learning_mode"] is True
    assert cal["state"] == "learning"
    assert cal["hit_rate_range"]["display"] == "learning"


def test_no_validated_without_walk_forward():
    row = {"ticker": "NVDA", "setup_family": "breakout"}
    cal = calibrate_opportunity(
        row,
        forward_summary={"sample_size": 25, "walk_forward_n": 5},
        attribution_calibrations={
            "breakout": {"sample_size": 25, "forward_r_mean": 0.5, "win_rate": 0.55}
        },
    )
    assert cal["state"] != "validated"
    assert cal["validated_requires_walk_forward"] is True


def test_cost_adjusted_included():
    row = {"ticker": "TSLA", "risk_reward": 2.5, "liquidity_score": 0.6, "expected_r": 1.2}
    cal = calibrate_opportunity(row, forward_summary={"sample_size": 10, "avg_forward_r_5d": 0.4})
    assert "cost_drag_r" in cal
    assert cal["may_authorize_deploy"] is False
