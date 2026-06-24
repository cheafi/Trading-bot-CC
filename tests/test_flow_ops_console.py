"""Flow / Ops decision surface unit tests."""

from __future__ import annotations

import unittest

from src.services.flow_decision_surface import _pm_action
from src.services.ops_operator_console import (
    build_degraded_ops_operator_console,
    build_ops_operator_console,
)


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
        self.assertEqual(out["verdict_code"], "NOT_RUNNABLE")
        self.assertIn("NOT READY", out["system_verdict"])
        self.assertTrue(len(out["blockers"]) >= 1)
        self.assertTrue(len(out["next_actions"]) >= 1)
        self.assertIn("metrics_display", out)
        self.assertIn("execution_layers", out)

    def test_metrics_reason_when_engine_off(self):
        out = build_ops_operator_console(
            ops_status={
                "uptime": "2h 0m",
                "engine": {"running": False},
                "latency": {"regime_ms": 12.0},
            },
        )
        self.assertEqual(out["metrics_display"]["uptime"]["display"], "2h 0m")
        self.assertIn("engine stopped", out["metrics_display"]["uptime"]["reason"].lower())
        self.assertEqual(out["metrics_display"]["regime_latency_ms"]["display"], "12.0ms")
        self.assertIn("engine_controls", out)
        self.assertTrue(out["engine_controls"]["can_start"])

    def test_signal_zero_reason_engine_stopped(self):
        out = build_ops_operator_console(
            ops_status={"engine": {"running": False, "cycle_count": 0, "signals_today": 0}},
        )
        codes = [r["code"] for r in out["signal_zero_reason"]]
        self.assertIn("no_cycle_run", codes)

    def test_degraded_ops_console_warmup_evidence(self):
        out = build_degraded_ops_operator_console(
            reason="backend importing", brief_ok=True
        )
        by_name = {c["name"]: c for c in out["component_evidence"]}
        self.assertEqual(by_name["market_data"]["probe"], "Probe OK")
        self.assertEqual(by_name["regime_router"]["probe"], "Warming")
        self.assertEqual(by_name["regime_router"]["tier"], "warming")
        self.assertIn("warming", by_name["regime_router"]["runtime_evidence"].lower())
        self.assertNotIn("RUNTIME OK", str(out).upper())
        self.assertTrue(out["diagnostics"]["warming_mode"])

    def test_degraded_ops_console_without_brief(self):
        out = build_degraded_ops_operator_console(brief_ok=False)
        by_name = {c["name"]: c for c in out["component_evidence"]}
        self.assertEqual(by_name["market_data"]["probe"], "Warming")
        self.assertEqual(out["verdict_code"], "WARMING")

    def test_probe_vs_runtime_evidence(self):
        out = build_ops_operator_console(
            ops_status={
                "engine": {"running": False, "cycle_count": 0, "signals_today": 0},
                "components": {
                    "market_data": True,
                    "regime_router": True,
                    "broker": True,
                    "leaderboard": True,
                    "learning_loop": True,
                },
            },
            cc_header={"components": {"market_data": True, "regime_router": True, "broker": True}},
        )
        by_name = {c["name"]: c for c in out["component_evidence"]}
        self.assertEqual(by_name["market_data"]["probe"], "Probe OK")
        self.assertIn("session", by_name["market_data"]["runtime_evidence"].lower())
        self.assertIn("No cycle executed", by_name["regime_router"]["runtime_evidence"])
        self.assertIn("diagnostics", out)
        self.assertTrue(out["diagnostics"]["probe_only_mode"])
        self.assertTrue(out["diagnostics"]["engine_stopped"])
        self.assertIn("no engine cycle", out["diagnostics"]["signals_today_note"].lower())
        self.assertIn("providers_honest", out)
        self.assertIn("not recently consumed", out["providers_honest"]["market_data"]["runtime"].lower())


if __name__ == "__main__":
    unittest.main()
