"""Cost slippage model — spread/volume/ATR/liquidity drag."""

from __future__ import annotations

from src.services.cost_slippage_model import (
    cost_drag_r,
    estimate_cost_adjusted_r,
    estimate_spread_bps,
)


def test_low_liquidity_raises_spread():
    row = {"ticker": "SMALL", "liquidity_score": 0.2, "avg_volume": 100_000}
    bps = estimate_spread_bps(row)
    assert bps > 15.0


def test_cost_drag_r_positive():
    row = {"ticker": "AAPL", "risk_reward": 2.0, "liquidity_score": 0.7, "avg_volume": 5_000_000}
    result = cost_drag_r(row, expected_r=1.5)
    assert result["cost_drag_r"] > 0
    assert result["may_authorize_deploy"] is False


def test_estimate_cost_adjusted_r_learning_when_no_expected():
    row = {"ticker": "MSFT", "risk_reward": 2.5}
    result = estimate_cost_adjusted_r(row)
    assert result["cost_adjusted_expected_r"]["display"] == "learning"
