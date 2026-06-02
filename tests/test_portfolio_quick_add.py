"""Portfolio quick-add — local-first record builder and API shape."""

from __future__ import annotations

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


class TestPortfolioQuickAdd(unittest.TestCase):
    def test_nvda_simple_add_normalizes_ticker(self):
        req = _req(ticker="nvda", shares=10, entry_price=220.0)
        pos = build_position_record(req, price=None, now="2026-06-01T00:00:00Z")
        self.assertEqual(pos["ticker"], "NVDA")
        self.assertEqual(pos["shares"], 10.0)
        self.assertEqual(pos["entry_price"], 220.0)
        self.assertFalse(pos["stop_defined"])
        self.assertTrue(pos["quote_pending"])

    def test_only_ticker_shares_entry_required(self):
        req = _req(ticker="AAPL", shares=5, entry_price=100.0)
        pos = build_position_record(req, price=101.0, now="2026-06-01T00:00:00Z")
        self.assertEqual(pos["stop_price"], 0)
        self.assertEqual(pos["target_1r"], 0)
        self.assertEqual(pos["target_2r"], 0)
        self.assertIsNone(pos["r_multiple"])

    def test_portfolio_header_snapshot_manual_offline(self):
        from src.services.portfolio_positions import portfolio_header_snapshot

        snap = portfolio_header_snapshot(ibkr_connected=False)
        self.assertEqual(snap["mode"], "portfolio")
        self.assertEqual(snap["book_label"], "Manual book")
        self.assertEqual(snap["positions_label"], "No positions")
        self.assertEqual(snap["broker_sync"], "unavailable")
        self.assertEqual(snap["broker_sync_label"], "Broker sync unavailable")
        self.assertTrue(snap["rebalance_only"])


if __name__ == "__main__":
    unittest.main()
