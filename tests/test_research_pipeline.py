"""Research pipeline — authority, workflow, exports (Strategy Lab / Shadow / Reports)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.services import research_store, vibe_agent_store
from src.services.operator_state_contract import build_page_capability
from src.services.reports_library import export_report
from src.services.research_pipeline import run_research_pipeline
from src.services.research_safety import PINE_DISCLAIMER, research_safety_contract, sanitize_research_payload
from src.services.strategy_builder import parse_strategy_prompt
from src.services.strategy_export import export_pine_draft
from src.services.validation_lab import run_validation
from src.services.shadow_account import analyze_shadow_account
from src.services.research_committee import run_committee_review


class IsolatedResearchStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        store = Path(self._tmpdir.name) / "research.json"
        vibe = Path(self._tmpdir.name) / "vibe.json"
        vibe_log = Path(self._tmpdir.name) / "vibe.log"
        self._p1 = mock.patch.object(research_store, "_STORE", store)
        self._p2 = mock.patch.object(vibe_agent_store, "_STORE", vibe)
        self._p3 = mock.patch.object(vibe_agent_store, "_LOG", vibe_log)
        self._p1.start()
        self._p2.start()
        self._p3.start()

    def tearDown(self):
        self._p1.stop()
        self._p2.stop()
        self._p3.stop()
        self._tmpdir.cleanup()


class TestResearchAuthority(unittest.TestCase):
    def test_strategy_builder_no_deploy(self):
        draft = parse_strategy_prompt("20/50 MA trend with VIX filter")
        self.assertFalse(draft.get("can_deploy", False))
        self.assertEqual(draft["action"], "research_only")
        self.assertNotIn("sizing", draft)

    def test_validation_no_deploy(self):
        draft = parse_strategy_prompt("RS leader strategy")
        val = run_validation(strategy_draft=draft, backtest_metrics={"sharpe": 1.2, "total_trades": 40, "stability_score": 70})
        self.assertFalse(val.get("can_deploy", False))
        self.assertIn(val["verdict"], ("Research pass", "Needs more data", "Overfit risk", "Regime-specific only", "Retire / do not use"))

    def test_backtest_pass_not_deploy_permission(self):
        val = run_validation(
            strategy_draft={"id": "d1"},
            backtest_metrics={"sharpe": 2.0, "total_trades": 50, "stability_score": 80},
            system_state={"tradeability": "WAIT", "deploy_open": False},
        )
        self.assertTrue(any("WAIT" in w for w in val.get("warnings", [])))

    def test_shadow_no_deploy(self):
        out = analyze_shadow_account(trades=[{"ticker": "NVDA", "pnl": -10, "chase": True}])
        self.assertFalse(out.get("can_deploy", False))
        self.assertNotIn("ibkr", out)

    def test_reports_contract_no_handoff(self):
        c = research_safety_contract(surface="reports")
        self.assertFalse(c["can_handoff"])
        self.assertFalse(c["can_deploy"])

    def test_page_capabilities_research_only(self):
        ss = {"tradeability": "WAIT", "deploy_open": False, "data_freshness": "FRESH", "blocker_compact": "WAIT", "repair_priority": "x"}
        for tab in ("strategy-lab", "shadow", "reports", "agent"):
            cap = build_page_capability(tab, system_state=ss)
            self.assertFalse(cap["can_deploy"])
            self.assertFalse(cap["can_size"])
            self.assertFalse(cap["can_handoff"])
            self.assertEqual(cap["surface_type"], "research_monitoring")


class TestSafetyAndExport(unittest.TestCase):
    def test_pine_has_disclaimer(self):
        code = export_pine_draft(entry_rules=["test entry"])
        self.assertIn("RESEARCH DRAFT ONLY", code)
        self.assertIn(PINE_DISCLAIMER.split("\n")[0], code)
        self.assertNotIn("strategy.order(", code)

    def test_stale_validation_provisional(self):
        val = run_validation(
            strategy_draft={"id": "x"},
            data_quality="STALE",
            backtest_metrics={"total_trades": 5},
        )
        self.assertTrue(val["provisional"])
        self.assertTrue(any("stale" in w.lower() for w in val["warnings"]))

    def test_pipeline_stops_without_live_execute(self):
        result = run_research_pipeline(
            prompt="MA trend strategy",
            system_state={"tradeability": "WAIT", "data_freshness": "FRESH", "deploy_open": False},
            backtest_metrics={"sharpe": 0.5, "total_trades": 10},
        )
        self.assertFalse(result.get("can_deploy"))
        self.assertFalse(result.get("can_handoff"))
        self.assertIn("draft", result["stepsCompleted"])
        self.assertEqual(result.get("stoppedAt"), "watch_rule_pending_validation")


class TestWorkflow(IsolatedResearchStore):
    def test_intent_to_watch_rule_via_pipeline(self):
        result = run_research_pipeline(
            prompt="幫我盯 NVDA pullback",
            system_state={"tradeability": "TRADE", "deploy_open": True, "data_freshness": "FRESH"},
            backtest_metrics={"sharpe": 1.5, "total_trades": 35, "stability_score": 75},
            steps=["draft", "validate", "watch_rule", "memory"],
        )
        self.assertTrue(result.get("strategyDraft"))
        self.assertTrue(result.get("validation"))
        self.assertTrue(result.get("memoryItem"))

    def test_strategy_draft_and_report(self):
        from src.services.research_store import save_strategy_draft
        from src.services.reports_library import create_report_from_validation

        draft = save_strategy_draft(parse_strategy_prompt("breakout with volume"))
        val = run_validation(strategy_draft=draft, backtest_metrics={"sharpe": 1.0, "total_trades": 25, "stability_score": 60})
        report = create_report_from_validation(val, strategy_draft=draft)
        self.assertTrue(report.get("id"))
        md = export_report(report["id"], "markdown")
        self.assertIn("非部署權限", md)

    def test_shadow_creates_report(self):
        from src.services.reports_library import create_report_from_shadow
        from src.services.research_store import save_shadow_run

        shadow = analyze_shadow_account(trades=[{"ticker": "AAPL", "pnl": 50}])
        saved = save_shadow_run(shadow)
        report = create_report_from_shadow({**shadow, "id": saved["id"]})
        self.assertEqual(report["type"], "shadow_account")

    def test_committee_cannot_grant_authority(self):
        draft = parse_strategy_prompt("trend follow")
        review = run_committee_review(subject=draft, system_state={"tradeability": "NO_TRADE"})
        self.assertFalse(review.get("can_deploy", False))
        self.assertIn("Cannot grant deploy", " ".join(review.get("authority_notice", [])))


if __name__ == "__main__":
    unittest.main()
