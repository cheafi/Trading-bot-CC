"""Tests for stock-intel (skipped when FastAPI/project deps not on PYTHONPATH)."""

import unittest

try:
    from src.services.stock_intel import _build_unified_decision, _narrative_structured

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

    def test_narrative_structured(self):
        dossier = {"why_buy": ["a"], "why_stop": ["b"]}
        n = _narrative_structured(dossier, None)
        self.assertIn("a", n["bull_case"][0])
        self.assertIn("b", n["bear_case"][0])


if __name__ == "__main__":
    unittest.main()
