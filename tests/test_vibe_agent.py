"""Vibe Agent — authority, stale/degraded, intent parsing, journal."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.services import vibe_agent_store
from src.services.operator_state_contract import build_page_capability, resolve_tab_id
from src.services.vibe_agent import (
    agent_status,
    build_watch_rule,
    create_calm_down_guardrail,
    evaluate_watch_rules,
    generate_overnight_brief,
    parse_vibe_intent,
    persist_intent_and_rules,
    review_agent_outcome,
)
from src.services.vibe_agent_safety import (
    agent_safety_contract,
    authority_notice_for_state,
    sanitize_agent_payload,
)


class IsolatedStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        store = Path(self._tmpdir.name) / "vibe_agent.json"
        log = Path(self._tmpdir.name) / "vibe_agent_audit.jsonl"
        self._patch_store = mock.patch.object(vibe_agent_store, "_STORE", store)
        self._patch_log = mock.patch.object(vibe_agent_store, "_LOG", log)
        self._patch_store.start()
        self._patch_log.start()

    def tearDown(self):
        self._patch_store.stop()
        self._patch_log.stop()
        self._tmpdir.cleanup()


class TestAgentSafetyContract(unittest.TestCase):
    def test_contract_denies_deploy_authority(self):
        c = agent_safety_contract()
        self.assertFalse(c["can_deploy"])
        self.assertFalse(c["can_size"])
        self.assertFalse(c["can_handoff"])
        self.assertTrue(c["can_monitor"])
        self.assertIn("Research / monitoring only", c["authority_notice"][0])

    def test_sanitize_strips_forbidden_fields(self):
        out = sanitize_agent_payload(
            {
                "can_deploy": True,
                "sizing": {"shares": 100},
                "ibkr": {"order": True},
                "action": "deploy",
            }
        )
        self.assertEqual(out["action"], "alert_only")
        self.assertNotIn("can_deploy", out)
        self.assertNotIn("sizing", out)
        self.assertEqual(out["authority_effect"], "none")

    def test_agent_page_capability_not_deploy_surface(self):
        ss = {
            "tradeability": "WAIT",
            "deploy_open": False,
            "data_freshness": "FRESH",
            "broker_state": "CONNECTED",
            "fallback_mode": False,
            "blocker_compact": "WAIT board gate",
            "repair_priority": "refresh",
        }
        cap = build_page_capability("agent", system_state=ss)
        self.assertFalse(cap["can_deploy"])
        self.assertFalse(cap["can_size"])
        self.assertFalse(cap["can_handoff"])
        self.assertEqual(cap["surface_type"], "research_monitoring")
        self.assertEqual(resolve_tab_id("agent"), "agent")


class TestStaleAndDegraded(IsolatedStore):
    def test_stale_data_marks_alerts_provisional(self):
        vibe_agent_store.save_rule(
            {
                "id": "r1",
                "asset": "NVDA",
                "status": "active",
                "name": "test",
                "ruleType": "setup_upgrade",
                "condition": "x",
                "authorityEffect": "none",
                "action": "alert_only",
            }
        )
        result = evaluate_watch_rules(
            system_state={
                "tradeability": "WAIT",
                "data_freshness": "STALE",
                "deploy_open": False,
            },
            playbook_state={
                "monitor_rows": [{"ticker": "NVDA", "action": "WATCH"}],
                "near_miss": [],
            },
        )
        self.assertEqual(result["triggeredAlerts"], [])
        self.assertGreaterEqual(len(result["provisionalAlerts"]), 1)
        self.assertEqual(result["provisionalAlerts"][0]["status"], "provisional")

    def test_broker_offline_notice(self):
        notices = authority_notice_for_state(
            {"broker_state": "GATEWAY_DOWN", "tradeability": "WAIT"}
        )
        self.assertTrue(any("Broker offline" in n for n in notices))
        self.assertTrue(any("只可監察" in n for n in notices))

    def test_mock_flow_guardrail(self):
        g = create_calm_down_guardrail(
            "chase",
            system_state={"tradeability": "WAIT", "data_freshness": "FRESH"},
            context={"mock_flow": True},
        )
        self.assertTrue(g["triggered"])
        self.assertIn("mock flow", " ".join(g.get("violated_rules") or []))


class TestIntentParsing(IsolatedStore):
    def test_vague_intent_becomes_structured_hypothesis(self):
        plan = parse_vibe_intent("我覺得 BTC 可能要突破，但唔想追高")
        self.assertEqual(plan["intentType"], "breakout_watch")
        self.assertIn("BTC", plan["assets"])
        self.assertTrue(plan["invalidation"])
        self.assertTrue(plan["expiry"])
        self.assertEqual(plan["action"], "alert_only")
        self.assertEqual(plan["authority_effect"], "none")

    def test_intent_creates_watch_rules_not_orders(self):
        result = persist_intent_and_rules("幫我盯 NVDA pullback")
        self.assertTrue(result["intent"]["id"])
        self.assertTrue(result["rules"])
        for rule in result["rules"]:
            self.assertEqual(rule["action"], "alert_only")
            self.assertEqual(rule["authorityEffect"], "none")
            self.assertNotIn("sizing", rule)
            self.assertNotIn("ibkr", rule)

    def test_build_watch_rule_from_plan(self):
        plan = parse_vibe_intent("今週只做高質素 RS leader")
        rules = build_watch_rule(plan, intent_id="intent-1")
        self.assertTrue(rules)
        self.assertTrue(all(r["confirmationRequired"] is True for r in rules))
        self.assertTrue(all(r["createdFromIntentId"] == "intent-1" for r in rules))


class TestAlertsAndJournal(IsolatedStore):
    def test_alerts_never_include_sizing(self):
        vibe_agent_store.save_rule(
            {
                "id": "r2",
                "asset": "QCOM",
                "status": "active",
                "name": "qcom",
                "ruleType": "price_zone_touch",
                "condition": "zone",
                "authorityEffect": "none",
                "action": "alert_only",
            }
        )
        result = evaluate_watch_rules(
            system_state={"tradeability": "WAIT", "data_freshness": "FRESH", "deploy_open": False},
            playbook_state={"monitor_rows": [{"ticker": "QCOM", "action": "WATCH"}], "near_miss": []},
        )
        for alert in result["triggeredAlerts"] + result["provisionalAlerts"]:
            self.assertNotIn("sizing", alert)
            self.assertNotIn("ibkr", alert)
            self.assertTrue(alert.get("candidate_only") is True)

    def test_every_alert_logged(self):
        vibe_agent_store.save_rule(
            {
                "id": "r3",
                "asset": "AAPL",
                "status": "active",
                "name": "aapl",
                "ruleType": "setup_upgrade",
                "condition": "x",
                "authorityEffect": "none",
                "action": "alert_only",
            }
        )
        evaluate_watch_rules(
            system_state={"tradeability": "TRADE", "data_freshness": "FRESH", "deploy_open": True},
            playbook_state={"monitor_rows": [{"ticker": "AAPL", "action": "WATCH"}], "near_miss": []},
        )
        journal = vibe_agent_store.list_journal(limit=10)
        self.assertTrue(any(j.get("type") == "alert_generated" for j in journal))

    def test_guardrail_override_logged(self):
        create_calm_down_guardrail(
            "deploy",
            system_state={"tradeability": "NO_TRADE", "data_freshness": "FRESH"},
        )
        journal = vibe_agent_store.list_journal(limit=5)
        self.assertTrue(any(j.get("type") == "guardrail" for j in journal))


class TestOvernightBrief(unittest.TestCase):
    def test_brief_includes_authority_notice(self):
        brief = generate_overnight_brief(
            system_state={"tradeability": "WAIT", "data_freshness": "STALE", "broker_state": "GATEWAY_DOWN"},
            today_payload={"market_regime": {"trend": "SIDEWAYS"}},
        )
        self.assertTrue(brief["title"])
        self.assertTrue(brief["authority_notice"])
        text = "\n".join(brief["lines"])
        self.assertTrue("資料過期" in text or "provisional" in text.lower())
        self.assertTrue("IBKR" in text)

    def test_agent_status_modes(self):
        st = agent_status(system_state={"data_freshness": "STALE"}, paused=False)
        self.assertEqual(st["mode"], "degraded")
        self.assertIn("非部署權限", st["authority_label"])


if __name__ == "__main__":
    unittest.main()
