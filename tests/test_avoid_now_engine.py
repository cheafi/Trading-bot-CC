"""Tests for categorized avoid-now engine."""

import unittest

from src.services.today_insights import build_avoid_now_engine


class TestAvoidNowEngine(unittest.TestCase):
    def test_regime_avoid_when_no_trade(self):
        items = build_avoid_now_engine(
            regime_label="RISK_OFF",
            should_trade=False,
            tradeability="NO_TRADE",
            vix=32,
            breadth=30,
            confidence=0.3,
        )
        cats = {i["category"] for i in items}
        self.assertIn("regime", cats)
        self.assertTrue(any(i["severity"] == "high" for i in items))

    def test_high_vix_category(self):
        items = build_avoid_now_engine(
            regime_label="UPTREND",
            should_trade=True,
            tradeability="WAIT",
            vix=30,
            breadth=55,
            confidence=0.6,
        )
        self.assertTrue(any(i["category"] == "stretched_vol" for i in items))


if __name__ == "__main__":
    unittest.main()
