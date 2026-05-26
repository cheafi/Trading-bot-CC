"""Decision bar and AOS services."""

import unittest

from src.services.decision_bar import (
    bar_from_portfolio,
    bar_from_today,
    build_decision_bar,
    evidence_quality_block,
)
from src.services.confluence_engine import build_confluence
from src.services.portfolio_fit import build_portfolio_fit
from src.services.rebalance_sim import simulate_rebalance


class TestDecisionBar(unittest.TestCase):
    def test_evidence_quality_live(self):
        eq = evidence_quality_block(basis="live", source_quality="high")
        self.assertGreaterEqual(eq["score"], 60)

    def test_bar_from_today_warming(self):
        bar = bar_from_today({}, None)
        self.assertEqual(bar["surface"], "today")
        self.assertIn(bar["verdict"], ("WAIT", "DEPLOY", "REDUCE"))

    def test_bar_from_portfolio(self):
        bar = bar_from_portfolio(
            {"stance": "REBALANCE", "recommended_action": "Trim NVDA", "evidence_quality": "manual", "confidence": "medium"},
            {"aligned_with_regime": False, "position_count": 3, "note": "Misaligned"},
            rebalance_urgency=True,
        )
        self.assertEqual(bar["surface"], "portfolio")

    def test_portfolio_fit_empty(self):
        fit = build_portfolio_fit("AAPL", [])
        self.assertIn("score", fit)

    def test_rebalance_sim(self):
        sim = simulate_rebalance(
            [
                {"ticker": "AAPL", "market_value": 6000},
                {"ticker": "MSFT", "market_value": 4000},
            ]
        )
        self.assertTrue(sim["feasible"])

    def test_confluence_minimal(self):
        c = build_confluence(
            dossier={"technicals": {"above_sma50": True, "rsi": 55}, "regime": {"should_trade": True}},
            unified={"label": "WATCH", "confidence": 0.5, "reason": "test"},
            smart_money={"insider": "neutral", "options_flow": "no_data"},
            pm_answer={"action_now": "WAIT"},
            regime={"should_trade": True},
        )
        self.assertIn("score", c)


if __name__ == "__main__":
    unittest.main()
