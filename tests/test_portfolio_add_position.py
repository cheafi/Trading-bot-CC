"""Unit tests for simple-first portfolio add position flow."""

import unittest
from types import SimpleNamespace

from src.services.portfolio_positions import build_position_record


def _req(**kwargs):
    defaults = {
        "ticker": "",
        "shares": 0,
        "entry_price": 0,
        "stop_price": 0,
        "target_1r": 0,
        "target_2r": 0,
        "notes": "",
        "sleeve": "",
        "sector": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestBuildPositionRecord(unittest.TestCase):
    def test_simple_mode_no_stop(self):
        req = _req(ticker="aapl", shares=100, entry_price=150.0)
        pos = build_position_record(req, price=155.0, now="2026-01-01T00:00:00Z")
        self.assertEqual(pos["ticker"], "AAPL")
        self.assertFalse(pos["stop_defined"])
        self.assertEqual(pos["stop_price"], 0)
        self.assertEqual(pos["target_1r"], 0)
        self.assertEqual(pos["target_2r"], 0)
        self.assertIsNone(pos["r_multiple"])
        self.assertEqual(pos["market_value"], 15500.0)
        self.assertEqual(pos["cost_basis"], 15000.0)
        self.assertFalse(pos["quote_pending"])

    def test_quote_pending_when_no_price(self):
        req = _req(ticker="XYZ", shares=10, entry_price=50.0)
        pos = build_position_record(req, price=None, now="2026-01-01T00:00:00Z")
        self.assertTrue(pos["quote_pending"])
        self.assertIsNone(pos["current_price"])
        self.assertIsNone(pos["market_value"])
        self.assertEqual(pos["entry_price"], 50.0)

    def test_advanced_stop_auto_targets(self):
        req = _req(ticker="MSFT", shares=50, entry_price=400.0, stop_price=380.0)
        pos = build_position_record(req, price=410.0, now="2026-01-01T00:00:00Z")
        self.assertTrue(pos["stop_defined"])
        self.assertEqual(pos["stop_price"], 380.0)
        self.assertEqual(pos["target_1r"], 420.0)
        self.assertEqual(pos["target_2r"], 440.0)
        self.assertIsNotNone(pos["r_multiple"])

    def test_sleeve_sector_override(self):
        req = _req(
            ticker="NVDA",
            shares=20,
            entry_price=900.0,
            sleeve="growth sleeve",
            sector="Technology",
        )
        pos = build_position_record(req, price=920.0, now="2026-01-01T00:00:00Z")
        self.assertEqual(pos["sleeve"], "growth sleeve")
        self.assertEqual(pos["sector"], "Technology")


if __name__ == "__main__":
    unittest.main()
