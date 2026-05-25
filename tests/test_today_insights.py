"""Unit tests for today_insights service."""

import unittest
from types import SimpleNamespace

from src.services.today_insights import (
    build_evidence_badges,
    build_near_miss_candidates,
    build_no_setup_diagnosis,
    build_regime_wait_explanation,
    build_sleeve_summary,
)


class _FakeConf:
    def __init__(self, timing=0.6, thesis=0.7, execution=0.5, final=0.65):
        self.timing = timing
        self.thesis = thesis
        self.execution = execution
        self.final = final


class _FakeDecision:
    def __init__(self, action="WATCH", entry_trigger=None):
        self.action = action
        self.entry_trigger = entry_trigger
        self.risk_reward_ratio = 2.0


class _FakeExpl:
    why_not_stronger = ["Extended"]


class _FakeFit:
    final_score = 7.2


class _FakePipeline:
    def __init__(self, ticker="AMD", action="WATCH"):
        self.signal = {
            "ticker": ticker,
            "entry_price": 100,
            "stop_price": 95,
            "target_price": 110,
            "risk_reward": 2.0,
        }
        self.decision = _FakeDecision(action=action)
        self.confidence = _FakeConf(timing=0.4)
        self.fit = _FakeFit()
        self.explanation = _FakeExpl()


class _FakeCouncil:
    def __init__(self, ticker="AMD", action="WATCH"):
        self.pipeline = _FakePipeline(ticker, action)


class TestTodayInsights(unittest.TestCase):
    def test_regime_wait_explanation(self):
        lines = build_regime_wait_explanation(
            trend_label="UPTREND",
            tradeability="WAIT",
            trade_count=0,
            actionable=3,
            should_trade=True,
            vix=19,
            breadth=42,
        )
        self.assertTrue(any("uptrend" in ln.lower() for ln in lines))

    def test_near_miss_excludes_top5(self):
        council = [_FakeCouncil("AMD"), _FakeCouncil("NVDA", "TRADE")]
        nm = build_near_miss_candidates(council, {"NVDA"}, limit=2)
        self.assertEqual(nm[0]["ticker"], "AMD")

    def test_no_setup_diagnosis_buckets(self):
        council = [_FakeCouncil("X", "WATCH"), _FakeCouncil("Y", "AVOID")]
        d = build_no_setup_diagnosis(council)
        self.assertIn("breakdown", d)
        self.assertGreaterEqual(sum(d["breakdown"].values()), 1)

    def test_sleeve_summary_gate(self):
        cards = [
            {
                "id": "A",
                "display_name": "Leader",
                "gate_status": "ACTIVE",
                "regime_fit": 85,
                "excess_return_pct": 10,
                "stance": "ATTACK",
                "mode": "training",
                "controls_capital": True,
                "max_drawdown_pct": -8,
                "equity_curve_20": [100, 101, 102],
            },
            {
                "id": "B",
                "display_name": "Tactical",
                "gate_status": "PAUSED",
                "regime_fit": 30,
                "excess_return_pct": 5,
                "stance": "OFF",
                "mode": "training",
            },
        ]
        s = build_sleeve_summary(cards, regime="BULL")
        self.assertEqual(s["strongest_live"]["display_name"], "Leader")
        self.assertEqual(s["fund_manager"]["active_sleeve_id"], "A")
        self.assertTrue(s["fund_manager"]["controls_capital"])

    def test_evidence_badges(self):
        b = build_evidence_badges(scanner_degraded=True)
        self.assertEqual(b["scanner"]["badge"], "stale")

    def test_near_miss_distance(self):
        nm = build_near_miss_candidates([_FakeCouncil("AMD")], set(), limit=1)
        self.assertIn("distance_to_pass", nm[0])


if __name__ == "__main__":
    unittest.main()
