"""Flow / Ops decision surface unit tests."""

from __future__ import annotations

import unittest

from src.services.flow_decision_surface import _pm_action
from src.services.ops_operator_console import build_ops_operator_console


class TestFlowPmAction(unittest.TestCase):
    def test_mock_not_actionable(self):
        row = {"quality_grade": "A", "tradeability_score": 80, "spread_pct": 2}
        out = _pm_action(row, regime_tradeability="TRADE", synthetic=True)
        self.assertEqual(out["pm_action"], "NOT_ACTIONABLE")

    def test_watch_for_confirm(self):
        row = {
            "quality_grade": "A",
            "tradeability_score": 50,
            "spread_pct": 4,
            "stock_move_pct": 0.5,
            "call_put": "C",
            "radar_score": 70,
        }
        out = _pm_action(row, regime_tradeability="SELECTIVE", synthetic=False)
        self.assertEqual(out["pm_action"], "WATCH_FOR_STOCK_CONFIRM")


class TestOpsConsole(unittest.TestCase):
    def test_not_runnable_when_stopped(self):
        out = build_ops_operator_console(
            ops_status={"engine": {"running": False, "dry_run": True, "cycle_count": 0}},
            cc_header={"engine": {"running": False}},
        )
        self.assertEqual(out["system_verdict"], "NOT_RUNNABLE")
        self.assertTrue(len(out["blockers"]) >= 1)


if __name__ == "__main__":
    unittest.main()
