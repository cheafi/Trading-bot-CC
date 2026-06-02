"""Tests for stock-intel (skipped when FastAPI/project deps not on PYTHONPATH)."""

import unittest

try:
    from src.services.stock_intel import (
        _apply_sizing_authority,
        _blocked_size_info,
        _build_confidence_metrics,
        _build_decision_stack,
        _build_why_not_now,
        _build_decision_hierarchy,
        _build_unified_decision,
        _catalyst_strip,
        _compute_size_shares,
        _narrative_structured,
        _price_in_entry_zone,
        _resolve_confidence_display,
        _sizing_block_reason,
        _timing_assessment,
    )

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False


@unittest.skipUnless(_HAS_DEPS, "requires project venv (fastapi, etc.)")
class TestStockIntelHelpers(unittest.TestCase):
    def test_unified_decision_merges_conviction(self):
        dossier = {
            "regime": {"should_trade": True},
            "why_buy": ["Above 50d"],
            "trade_plan": {"stop": 95, "target_1r": 110},
        }
        conviction = {"action": "BUY", "why_now": ["Options confirm"]}
        u = _build_unified_decision(dossier, conviction)
        self.assertEqual(u["label"], "TRADE")
        self.assertEqual(u["stop"], 95)

    def test_unified_decision_parses_rr_ratio_label(self):
        dossier = {
            "price": 100,
            "regime": {"should_trade": True},
            "trade_plan": {"rr_ratio_label": "1:2", "stop": 95},
            "technicals": {"atr": 2},
        }
        u = _build_unified_decision(dossier, None)
        self.assertEqual(u["rr_ratio"], 2.0)
        self.assertNotEqual(u["rr_ratio"], "1:2")

    def test_narrative_structured(self):
        dossier = {"why_buy": ["a"], "why_stop": ["b"]}
        n = _narrative_structured(dossier, None)
        self.assertIn("a", n["bull_case"][0])
        self.assertIn("b", n["bear_case"][0])

    def test_catalyst_strip_no_manual_check(self):
        c = _catalyst_strip(None, None)
        details = " ".join(i.get("detail", "") for i in c["items"])
        self.assertNotIn("Check earnings calendar manually", details)
        self.assertIn("unavailable", details.lower())
        self.assertTrue(c.get("catalyst_data_incomplete"))
        self.assertIn("Catalyst data incomplete", c.get("unavailable_guidance") or "")

    def test_confidence_unavailable_not_zero(self):
        dossier = {"regime": {"should_trade": True}, "trade_plan": {}}
        u = _build_unified_decision(dossier, None)
        self.assertIsNone(u["confidence"])
        display = _resolve_confidence_display(u, dossier, None)
        self.assertFalse(display["confidence_available"])
        self.assertEqual(display["confidence_label"], "Pending calibration")

    def test_decision_hierarchy_chain(self):
        unified = {"label": "WATCH", "reason": "Monitor"}
        action_box = {"state": "BUY_ON_PULLBACK", "reason": "Wait pullback"}
        pm = {"action_now": "WAIT", "one_line": "No trigger"}
        h = _build_decision_hierarchy(unified, action_box, pm)
        self.assertEqual(h["verdict"], "WATCH")
        self.assertEqual(h["execution_mode"], "BUY_ON_PULLBACK")
        self.assertEqual(h["current_action"], "WAIT")
        self.assertIn("→", h["chain_summary"])

    def test_decision_stack_replaces_chain_semantics(self):
        unified = {"label": "WATCH", "reason": "Monitor"}
        action_box = {"state": "BUY_ON_PULLBACK"}
        pm = {"action_now": "WAIT"}
        stack = _build_decision_stack(unified, action_box, pm, regime_ok=True)
        self.assertEqual(stack["primary_state"], "WATCH")
        self.assertEqual(stack["execution_style"], "BUY_ON_PULLBACK")
        self.assertEqual(stack["board_gate"], "WAIT")
        self.assertIn("do not support immediate action", stack["interpretation"].lower())

    def test_why_not_in_zone_extended_not_outside_zone(self):
        unified = {"entry_zone": [300, 310], "stop": 295}
        timing = {
            "in_entry_zone": True,
            "extended": True,
            "rsi_overheated": True,
        }
        reasons = _build_why_not_now("WAIT", unified, timing, "BUY_ON_PULLBACK")
        self.assertEqual(len(reasons), 1)
        self.assertIn("technically within the wider zone", reasons[0])
        self.assertNotIn("outside entry zone", reasons[0].lower())

    def test_why_not_outside_zone_when_not_in_zone(self):
        unified = {"entry_zone": [300, 310], "stop": 295}
        timing = {"in_entry_zone": False, "extended": False, "rsi_overheated": False}
        reasons = _build_why_not_now("WAIT", unified, timing, "WATCH_CONFIRM")
        self.assertIn("outside entry zone", reasons[0].lower())

    def test_price_in_entry_zone(self):
        self.assertTrue(_price_in_entry_zone(305.0, [300, 310]))
        self.assertFalse(_price_in_entry_zone(315.0, [300, 310]))

    def test_confidence_metrics_two_field_model(self):
        conf = {
            "confidence": 0.27,
            "confidence_pct": 27,
            "confidence_available": True,
            "confidence_source": "confluence",
            "confidence_label": "Low conviction",
        }
        metrics = _build_confidence_metrics(
            conf,
            {"score": 70},
            {"score": 70},
        )
        self.assertEqual(metrics["decision_confidence_pct"], 27)
        self.assertEqual(metrics["decision_confidence_label"], "low proxy")
        self.assertEqual(metrics["thesis_quality"], 70)
        self.assertIn("neutral-positive", metrics["thesis_quality_display"])

    def test_size_explanation_uses_midpoint_and_stop(self):
        dossier = {"price": 305, "technicals": {"atr": 4}}
        unified = {"entry_zone": [300, 310], "stop": 304.70}
        info = _compute_size_shares(dossier, unified, equity=100_000)
        self.assertGreater(info["shares"], 0)
        self.assertIn("entry zone midpoint", info["size_explanation"].lower())
        self.assertIn("$304.70", info["size_explanation"])

    def test_timing_assessment_flags_overheated_in_zone(self):
        dossier = {
            "price": 305,
            "why_buy": ["Above 50d"],
            "technicals": {"rsi": 72, "above_sma50": True},
        }
        unified = {"entry_zone": [300, 310]}
        t = _timing_assessment(dossier, unified)
        self.assertTrue(t["in_entry_zone"])
        self.assertTrue(t["rsi_overheated"])
        self.assertTrue(t["timing_weak"])

    def test_sizing_blocked_for_confirm_only_core_phase(self):
        dossier = {
            "price": 305,
            "technicals": {"atr": 4},
            "_partial": True,
            "trust": {"source": "instant-degraded"},
        }
        unified = {
            "label": "CONFIRM ONLY",
            "entry_zone": [300, 310],
            "stop": 295,
            "rr_ratio": None,
        }
        raw = _compute_size_shares(dossier, unified, equity=100_000)
        blocked, is_blocked = _apply_sizing_authority(
            raw,
            load_phase="core",
            unified=unified,
            dossier=dossier,
        )
        self.assertTrue(is_blocked)
        self.assertEqual(blocked["shares"], 0)
        self.assertTrue(blocked["sizing_blocked"])
        self.assertIn("live dossier", blocked["size_explanation"].lower())

    def test_sizing_blocked_when_rr_unavailable(self):
        dossier = {"price": 305, "technicals": {"atr": 4}}
        unified = {
            "label": "TRADE",
            "entry_zone": [300, 310],
            "stop": 295,
            "rr_ratio": None,
        }
        reason = _sizing_block_reason(
            load_phase="full",
            unified=unified,
            dossier=dossier,
        )
        self.assertEqual(reason, "Size unavailable")
        blocked = _blocked_size_info(reason or "")
        self.assertEqual(blocked["shares"], 0)


if __name__ == "__main__":
    unittest.main()
