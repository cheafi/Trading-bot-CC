"""Unit tests for portfolio decision console."""

import unittest

from src.services.portfolio_decision_console import (
    build_action_needed,
    build_allocation_monitor,
    build_allocator_summary,
    build_critical_risk_event,
    build_do_now,
    build_ibkr_linkage,
    build_return_attribution,
    compute_portfolio_heat,
)


class TestPortfolioDecisionConsole(unittest.TestCase):
    def test_allocation_monitor_policy_cap_not_equal_weight(self):
        positions = [{"ticker": "NVDA", "market_value": 10000, "pnl_pct": -5}]
        rows = build_allocation_monitor(positions)
        self.assertEqual(len(rows), 1)
        nvda = rows[0]
        self.assertEqual(nvda["target_weight_pct"], 12.0)
        self.assertEqual(nvda["current_weight_pct"], 100.0)
        self.assertEqual(nvda["excess_pct"], 88.0)
        self.assertEqual(nvda["action_required"], "TRIM URGENT")
        self.assertEqual(nvda["priority"], "critical")

    def test_allocation_monitor_drift_multi_name(self):
        positions = [
            {"ticker": "AAPL", "market_value": 8000, "pnl_pct": 2},
            {"ticker": "MSFT", "market_value": 2000, "pnl_pct": -1},
        ]
        rows = build_allocation_monitor(positions)
        self.assertEqual(len(rows), 2)
        aapl = next(r for r in rows if r["asset"] == "AAPL")
        self.assertTrue(str(aapl["action_required"]).startswith("TRIM"))

    def test_heat_stop_breach_not_zero_risk(self):
        positions = [
            {
                "ticker": "NVDA",
                "market_value": 10000,
                "current_price": 90,
                "entry_price": 100,
                "stop_price": 95,
                "shares": 100,
                "risk_status": "STOP BREACHED",
                "unrealized_r": -1.23,
            }
        ]
        heat = compute_portfolio_heat(positions, equity=10000)
        self.assertEqual(heat["stop_breached_count"], 1)
        self.assertEqual(heat["heat_model"], "disabled_stop_breach")
        self.assertFalse(heat["heat_available"])
        self.assertEqual(heat["heat_display"], "POST-BREACH")
        self.assertAlmostEqual(heat["post_breach_open_r"], -1.23)
        self.assertIn("misleading", heat["heat_warning"])

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

    def test_action_needed_critical_first(self):
        heat = compute_portfolio_heat(
            [
                {
                    "ticker": "NVDA",
                    "market_value": 10000,
                    "current_price": 90,
                    "entry_price": 100,
                    "stop_price": 95,
                    "shares": 100,
                    "risk_status": "STOP BREACHED",
                }
            ],
            equity=10000,
        )
        linkage = build_ibkr_linkage(
            source="manual",
            execution={"broker_connected": False, "mode": "manual"},
            positions=[{"ticker": "NVDA", "market_value": 10000}],
        )
        rows = build_allocation_monitor([{"ticker": "NVDA", "market_value": 10000}])
        actions = build_action_needed(
            [],
            rows,
            heat_pct=0,
            top_concentration_pct=100,
            heat=heat,
            ibkr_linkage=linkage,
        )
        self.assertTrue(actions)
        self.assertEqual(actions[0]["tier"], "critical")
        self.assertEqual(actions[0]["category"], "stop_breach")

    def test_critical_risk_event_dynamic_copy(self):
        heat = compute_portfolio_heat(
            [
                {
                    "ticker": "NVDA",
                    "market_value": 10000,
                    "current_price": 90,
                    "entry_price": 100,
                    "stop_price": 95,
                    "shares": 100,
                    "risk_status": "STOP BREACHED",
                }
            ],
            equity=10000,
        )
        linkage = build_ibkr_linkage(
            source="manual",
            execution={"broker_connected": False, "mode": "manual"},
            positions=[{"ticker": "NVDA", "market_value": 10000}],
        )
        rows = build_allocation_monitor([{"ticker": "NVDA", "market_value": 10000}])
        event = build_critical_risk_event(
            positions=[{"ticker": "NVDA", "market_value": 10000}],
            heat=heat,
            ibkr_linkage=linkage,
            allocation_rows=rows,
            top_concentration_pct=100,
        )
        self.assertTrue(event["active"])
        self.assertIn("NVDA", event["message"])
        self.assertIn("CRITICAL RISK EVENT", event["headline"])

    def test_do_now_order(self):
        heat = compute_portfolio_heat(
            [
                {
                    "ticker": "NVDA",
                    "market_value": 10000,
                    "current_price": 90,
                    "entry_price": 100,
                    "stop_price": 95,
                    "shares": 100,
                    "risk_status": "STOP BREACHED",
                }
            ],
            equity=10000,
        )
        linkage = build_ibkr_linkage(
            source="manual",
            execution={"broker_connected": False, "mode": "manual"},
            positions=[{"ticker": "NVDA", "market_value": 10000}],
        )
        rows = build_allocation_monitor([{"ticker": "NVDA", "market_value": 10000}])
        actions = build_action_needed(
            [],
            rows,
            heat=heat,
            ibkr_linkage=linkage,
            top_concentration_pct=100,
        )
        do_now = build_do_now(actions, heat, linkage, rows)
        self.assertTrue(do_now)
        self.assertEqual(do_now[0]["action"], "Confirm broker")


if __name__ == "__main__":
    unittest.main()
