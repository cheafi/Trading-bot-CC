"""Unit tests for portfolio decision console."""

import unittest

from src.services.portfolio_decision_console import (
    build_action_needed,
    build_allocation_monitor,
    build_allocator_summary,
    build_return_attribution,
)


class TestPortfolioDecisionConsole(unittest.TestCase):
    def test_allocation_monitor_drift(self):
        positions = [
            {"ticker": "AAPL", "market_value": 8000, "pnl_pct": 2},
            {"ticker": "MSFT", "market_value": 2000, "pnl_pct": -1},
        ]
        rows = build_allocation_monitor(positions)
        self.assertEqual(len(rows), 2)
        aapl = next(r for r in rows if r["asset"] == "AAPL")
        self.assertEqual(aapl["action_required"], "TRIM")

    def test_return_attribution(self):
        positions = [
            {"ticker": "A", "market_value": 5000, "pnl_pct": 10},
            {"ticker": "B", "market_value": 5000, "pnl_pct": -5},
        ]
        attr = build_return_attribution(positions)
        self.assertTrue(attr["by_return"])
        self.assertIsNotNone(attr["top_contributor"])

    def test_allocator_summary_rebalance(self):
        rows = build_allocation_monitor(
            [
                {"ticker": "X", "market_value": 9000, "pnl_pct": 0},
                {"ticker": "Y", "market_value": 1000, "pnl_pct": 0},
            ]
        )
        summary = build_allocator_summary(
            positions=rows,
            summary={"total_pnl_pct": 0},
            regime={"tradeability": "TRADE"},
            allocation_rows=rows,
            execution={},
            fund_allocator={},
            source="manual",
        )
        self.assertIn(summary["stance"], ("REBALANCE", "HOLD", "REDUCE"))

    def test_action_needed_heat(self):
        actions = build_action_needed([], [], heat_pct=7.0, top_concentration_pct=15)
        self.assertTrue(any(a["category"] == "portfolio_heat" for a in actions))


if __name__ == "__main__":
    unittest.main()
