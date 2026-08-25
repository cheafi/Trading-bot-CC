"""RS decision surface unit tests."""

from __future__ import annotations

import unittest

from src.services.rs_decision_surface import _buyability, _period_return_pct


class TestRsDecision(unittest.TestCase):
    def test_buyability_extended(self):
        row = {
            "rs_composite": 135,
            "rs_change_1w": 2,
            "rs_change_1m": 8,
            "rs_percentile": 90,
            "rs_3m": 120,
            "trend": "ACCELERATING",
            "price": 100,
            "stale": False,
        }
        out = _buyability(row, "TRADE")
        self.assertEqual(out["buyability"], "EXTENDED")
        self.assertFalse(out["actionable"])

    def test_buyability_pullback_actionable(self):
        row = {
            "rs_composite": 112,
            "rs_change_1w": -2,
            "rs_change_1m": 1,
            "rs_percentile": 80,
            "rs_3m": 108,
            "trend": "STEADY",
            "price": 50,
            "stale": False,
        }
        out = _buyability(row, "SELECTIVE")
        self.assertEqual(out["buyability"], "PULLBACK")
        self.assertTrue(out["actionable"])


if __name__ == "__main__":
    unittest.main()
