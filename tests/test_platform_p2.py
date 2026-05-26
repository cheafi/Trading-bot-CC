"""Smoke tests for P2 platform services (no live market data)."""

from __future__ import annotations

import unittest

from src.services.backtest_lab import _strategy_attribution, _trade_level_review
from src.services.rebalance_sim import simulate_rebalance


class TestRebalanceSim(unittest.TestCase):
    def test_equal_weight_preview(self):
        positions = [
            {"ticker": "AAPL", "market_value": 6000},
            {"ticker": "MSFT", "market_value": 4000},
        ]
        out = simulate_rebalance(positions, policy="equal_weight")
        self.assertTrue(out["feasible"])
        self.assertGreaterEqual(out["trade_count"], 0)

    def test_custom_targets(self):
        positions = [
            {"ticker": "AAPL", "market_value": 8000},
            {"ticker": "MSFT", "market_value": 2000},
        ]
        out = simulate_rebalance(
            positions,
            target_weights={"AAPL": 0.5, "MSFT": 0.5},
        )
        self.assertTrue(out["feasible"])


class TestBacktestLabHelpers(unittest.TestCase):
    def test_trade_level_review_empty(self):
        out = _trade_level_review({})
        self.assertIn("summary", out)

    def test_attribution_ranking(self):
        core = {
            "benchmark_return": 10,
            "strategies": [
                {"name": "momentum", "total_return_pct": 20, "sharpe": 1.2},
                {"name": "swing", "total_return_pct": 5, "sharpe": 0.5},
            ],
        }
        out = _strategy_attribution(core)
        self.assertEqual(out["ranked"][0]["name"], "momentum")


if __name__ == "__main__":
    unittest.main()
