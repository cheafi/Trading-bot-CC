"""Successful opportunity screener — 10 categories, sample thresholds."""

from __future__ import annotations

from src.services.successful_opportunity_screener import (
    SCREEN_CATEGORIES,
    screen_opportunity,
)


def test_ten_screen_categories():
    assert len(SCREEN_CATEGORIES) == 10


def test_promising_requires_sample():
    row = {"ticker": "AAPL", "score": 7.5, "risk_reward": 2.5, "sector": "tech"}
    evidence = {
        "families": [
            {"family": "setup_quality", "score": 0.7},
            {"family": "rr_quality", "score": 0.6},
            {"family": "regime", "score": 0.6},
            {"family": "liquidity", "score": 0.5},
            {"family": "trend", "score": 0.6},
            {"family": "volume", "score": 0.5},
            {"family": "catalyst", "score": 0.5},
            {"family": "portfolio_fit", "score": 0.6},
        ]
    }
    cal = {"sample_size": 3, "cost_drag_r": 0.2}
    result = screen_opportunity(row, evidence=evidence, calibration=cal, truth={})
    assert result["pattern_status"] != "successful_pattern"
    assert result["may_authorize_deploy"] is False


def test_successful_pattern_high_sample():
    row = {"ticker": "NVDA", "score": 8.0, "risk_reward": 3.0, "sector": "tech", "theme": "ai"}
    evidence = {
        "families": [
            {"family": "setup_quality", "score": 0.8},
            {"family": "rr_quality", "score": 0.7},
            {"family": "regime", "score": 0.7},
            {"family": "liquidity", "score": 0.6},
            {"family": "trend", "score": 0.7},
            {"family": "volume", "score": 0.6},
            {"family": "catalyst", "score": 0.6},
            {"family": "portfolio_fit", "score": 0.7},
        ]
    }
    cal = {"sample_size": 25, "cost_drag_r": 0.1}
    result = screen_opportunity(row, evidence=evidence, calibration=cal, truth={"regime_state": "SELECTIVE"})
    assert result["passed_count"] >= 5
