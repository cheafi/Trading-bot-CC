"""Smoke tests for P2 platform services (no live market data)."""

from __future__ import annotations

import unittest

from src.services.backtest_lab import (
    _strategy_attribution,
    _strategy_name,
    _trade_level_review,
)
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
                {"strategy": "momentum", "total_return": 20, "sharpe": 1.2},
                {"strategy": "swing", "total_return": 5, "sharpe": 0.5},
            ],
        }
        out = _strategy_attribution(core)
        self.assertEqual(out["ranked"][0]["name"], "momentum")

    def test_strategy_name_fallback(self):
        self.assertEqual(_strategy_name({"strategy": "breakout"}), "breakout")
        self.assertEqual(_strategy_name({"name": "swing"}), "swing")

    def test_trade_level_review_best_strategy_string(self):
        core = {
            "best_strategy": "momentum",
            "strategies": [
                {
                    "strategy": "momentum",
                    "trades": [{"pnl_pct": 2.5, "hold_days": 3}],
                }
            ],
        }
        out = _trade_level_review(core)
        self.assertEqual(out["strategy"], "momentum")
        self.assertEqual(out["trade_count"], 1)


if __name__ == "__main__":
    unittest.main()
