"""Unit tests for fund_manager_console."""

import unittest

from src.services.fund_manager_console import (
    build_allocator_decision_strip,
    build_allocation_recommendation,
    build_fund_console_payload,
    enrich_fund_card,
)


class TestFundManagerConsole(unittest.TestCase):
    def test_enrich_paused_reason(self):
        card = enrich_fund_card(
            {
                "id": "LEADER_MOMENTUM",
                "display_name": "Leader",
                "gate_status": "PAUSED",
                "regime_fit": 15,
            },
            "UPTREND",
        )
        self.assertEqual(card["deployability"], "OFF")
        self.assertIn("15%", card["status_reason"])

    def test_allocation_when_active(self):
        cards = [
            enrich_fund_card(
                {"id": "A", "display_name": "Tactical", "gate_status": "ACTIVE", "regime_fit": 65},
                "BULL",
            ),
            enrich_fund_card(
                {"id": "B", "display_name": "Leader", "gate_status": "PAUSED", "regime_fit": 15},
                "BULL",
            ),
        ]
        alloc = build_allocation_recommendation(cards)
        self.assertTrue(alloc["weights"])

    def test_allocator_decision(self):
        cards = [
            enrich_fund_card(
                {
                    "id": "TACTICAL_DEF",
                    "display_name": "Tactical",
                    "gate_status": "REDUCED",
                    "regime_fit": 65,
                },
                "UPTREND",
            ),
        ]
        ad = build_allocator_decision_strip(
            cards,
            regime_display="UPTREND · WAIT",
            tradeability="WAIT",
            benchmark_return_pct=10.0,
        )
        self.assertIn("deploy_capital", ad)
        self.assertIn("why_not", ad)

    def test_manager_box(self):
        card = enrich_fund_card(
            {"id": "LEADER_MOMENTUM", "gate_status": "PAUSED", "regime_fit": 15},
            "BEAR",
        )
        self.assertIn("manager_box", card)
        self.assertEqual(card["manager_box"]["capital_deployed_pct"], 0.0)

    def test_console_payload(self):
        cards = [
            {
                "id": "TACTICAL_DEF",
                "display_name": "Tactical",
                "gate_status": "REDUCED",
                "regime_fit": 65,
                "controls_capital": True,
                "stance": "DEFEND",
                "mode": "training",
                "holdings": [{"ticker": "JNJ", "weight": 0.2}],
            }
        ]
        payload = build_fund_console_payload(
            cards=cards,
            regime="UPTREND",
            benchmark="SPY",
            market_regime_label="UPTREND · WAIT",
        )
        self.assertEqual(payload["regime_display"], "UPTREND · WAIT")
        self.assertTrue(payload["comparison_table"])


if __name__ == "__main__":
    unittest.main()
