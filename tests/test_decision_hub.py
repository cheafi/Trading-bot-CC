"""Unit tests for platform decision hub."""

import unittest

from src.services.decision_hub import (
    _best_rr,
    _pick_best_by_style,
    build_monitoring_system,
    build_user_roles_guide,
)


class TestDecisionHub(unittest.TestCase):
    def test_best_rr_picks_highest(self):
        rows = [
            {"ticker": "A", "risk_reward": 2.0},
            {"ticker": "B", "risk_reward": 4.5},
        ]
        best = _best_rr(rows)
        self.assertIsNotNone(best)
        self.assertEqual(best["ticker"], "B")
        self.assertEqual(best["risk_reward"], 4.5)

    def test_pick_momentum_style(self):
        rows = [
            {"ticker": "X", "strategy": "defensive", "score": 9},
            {"ticker": "Y", "strategy": "momentum_breakout", "score": 7},
        ]
        pick = _pick_best_by_style(rows, ("momentum", "breakout"))
        self.assertEqual(pick["ticker"], "Y")

    def test_monitoring_four_classes(self):
        mon = build_monitoring_system(
            today={"near_miss": [{"ticker": "NVDA", "upgrade_trigger": "RS>80"}]},
            market_posture={"deploy_posture": "WAIT"},
        )
        for key in ("stock", "portfolio", "market", "smart_money"):
            self.assertIn(key, mon)
        self.assertTrue(mon["stock"])
        self.assertEqual(mon["posture"], "WAIT")

    def test_user_roles_guide(self):
        roles = build_user_roles_guide()
        self.assertIn("allocator", roles)
        self.assertIn("funds", roles["allocator"])


if __name__ == "__main__":
    unittest.main()
