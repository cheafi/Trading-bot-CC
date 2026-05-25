"""Unit tests for best_action service (no pytest required)."""

import unittest

from src.services.best_action import (
    build_best_action,
    compute_theme_overlap,
    enrich_ranked_payload,
)


class TestBestAction(unittest.TestCase):
    def test_build_best_action_picks_trade_and_watch(self):
        opps = [
            {
                "ticker": "QCOM",
                "action": "TRADE",
                "final_conf": 0.72,
                "entry_price": 180,
                "stop_price": 170,
            },
            {
                "ticker": "AMD",
                "action": "WATCH",
                "final_conf": 0.55,
                "upgrade_trigger": "Reclaim $165 on volume",
            },
        ]
        ba = build_best_action(
            opps,
            tradeability="SELECTIVE",
            should_trade=True,
            ibkr_connected=True,
            ibkr_mode="paper",
        )
        self.assertEqual(ba["best_trade_now"]["ticker"], "QCOM")
        self.assertEqual(ba["best_watch_upgrade"]["ticker"], "AMD")
        self.assertTrue(ba["execution_readiness"]["bracket_ready"])

    def test_overlap_warns_semi_cluster(self):
        opps = [{"ticker": t, "sector_type": "HIGH_GROWTH"} for t in ("NVDA", "AMD", "AVGO", "AMAT", "LRCX")]
        ow = compute_theme_overlap(opps)
        self.assertGreaterEqual(ow["semi_count"], 4)
        self.assertTrue(ow["warnings"])

    def test_enrich_ranked_payload(self):
        payload = enrich_ranked_payload(
            {
                "opportunities": [{"ticker": "SPY", "action": "WATCH", "final_conf": 0.5}],
                "stale": False,
                "source": "test",
            }
        )
        self.assertIn("best_action", payload)
        self.assertIn("overlap_warning", payload)


if __name__ == "__main__":
    unittest.main()
