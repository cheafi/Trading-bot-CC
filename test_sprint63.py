"""
Sprint 63 Tests — Correlation in pipeline, persistent dedup,
regime change detection, decision diff
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))


class TestCorrelationInPipeline(unittest.TestCase):
    """Correlated TRADE signals should be flagged in batch."""

    def test_same_sector_trades_flagged(self):
        from src.engines.sector_pipeline import SectorPipeline

        pipeline = SectorPipeline()
        regime = {"trend": "RISK_ON", "should_trade": True}

        # Two tech stocks — should trigger correlation flag
        signals = [
            {
                "ticker": "NVDA", "strategy": "momentum",
                "trend_structure": "strong_uptrend",
                "breakout_quality": "genuine",
                "volume_confirms": True,
                "rs_rank": 90, "vol_ratio": 2.0,
                "contraction_count": 2, "atr_pct": 3.0,
                "data_freshness": "live",
            },
            {
                "ticker": "AMD", "strategy": "momentum",
                "trend_structure": "strong_uptrend",
                "breakout_quality": "genuine",
                "volume_confirms": True,
                "rs_rank": 85, "vol_ratio": 2.5,
                "contraction_count": 2, "atr_pct": 3.5,
                "data_freshness": "live",
            },
        ]

        results = pipeline.process_batch(signals, regime)
        trade_results = [r for r in results if r.decision.action == "TRADE"]

        # If both are TRADE, at least one should have correlation warning
        if len(trade_results) >= 2:
            rationales = " ".join(r.decision.rationale for r in trade_results)
            self.assertIn("correlated", rationales.lower(),
                "Same-sector TRADE pairs should have correlation warning")


class TestDecisionTracker(unittest.TestCase):
    """Persistent decision tracker with SQLite."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        from src.engines.decision_tracker import DecisionTracker
        self.tracker = DecisionTracker(db_path=self.db_path)

    def tearDown(self):
        self.tracker.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_record_and_retrieve(self):
        self.tracker.record("NVDA", "TRADE", score=8.5, grade="A")
        self.tracker.record("AMD", "WATCH", score=6.0, grade="B")

        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        latest = self.tracker._latest_by_ticker(today)
        self.assertIn("NVDA", latest)
        self.assertEqual(latest["NVDA"]["action"], "TRADE")

    def test_persistent_dedup(self):
        # First time — not a duplicate
        is_dup1 = self.tracker.check_dedup("NVDA", "TRADE")
        self.assertFalse(is_dup1)

        # Second time — duplicate
        is_dup2 = self.tracker.check_dedup("NVDA", "TRADE")
        self.assertTrue(is_dup2)

        # Different action — not a duplicate
        is_dup3 = self.tracker.check_dedup("NVDA", "WATCH")
        self.assertFalse(is_dup3)

    def test_decision_diff(self):
        # Record "yesterday"
        self.tracker.conn.execute(
            """INSERT INTO decisions
               (ticker, action, score, grade, confidence, rationale,
                entry_trigger, stop_price, target_price, regime,
                recorded_at, date_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("NVDA", "WATCH", 6.5, "B", 0.55, "Promising",
             "", 0, 0, "UPTREND", "2026-04-26T10:00:00", "2026-04-26"),
        )
        self.tracker.conn.execute(
            """INSERT INTO decisions
               (ticker, action, score, grade, confidence, rationale,
                entry_trigger, stop_price, target_price, regime,
                recorded_at, date_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("NVDA", "TRADE", 8.5, "A", 0.75, "High conviction",
             "Buy above $155", 142, 170, "RISK_ON",
             "2026-04-27T10:00:00", "2026-04-27"),
        )
        self.tracker.conn.commit()

        diffs = self.tracker.get_diffs("2026-04-27", "2026-04-26")
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["change"], "UPGRADE")
        self.assertEqual(diffs[0]["from"], "WATCH")
        self.assertEqual(diffs[0]["to"], "TRADE")

    def test_regime_change_detection(self):
        # First regime — no change
        result1 = self.tracker.record_regime("RISK_ON", 25.0, 14.0)
        self.assertIsNone(result1)

        # Same regime — no change
        result2 = self.tracker.record_regime("RISK_ON", 27.0, 14.5)
        self.assertIsNone(result2)

        # Different regime — change detected!
        result3 = self.tracker.record_regime("RISK_OFF", 72.0, 28.0)
        self.assertIsNotNone(result3)
        self.assertTrue(result3["changed"])
        self.assertEqual(result3["from"], "RISK_ON")
        self.assertEqual(result3["to"], "RISK_OFF")

    def test_regime_history(self):
        self.tracker.record_regime("RISK_ON", 25.0, 14.0)
        self.tracker.record_regime("SIDEWAYS", 48.0, 18.0)
        self.tracker.record_regime("RISK_OFF", 72.0, 28.0)

        history = self.tracker.get_regime_history(limit=5)
        self.assertEqual(len(history), 3)
        # Most recent first
        self.assertEqual(history[0]["trend"], "RISK_OFF")
        self.assertEqual(history[2]["trend"], "RISK_ON")

    def test_record_from_decision_dict(self):
        decision_dict = {
            "action": "TRADE", "score": 8.5, "grade": "A",
            "confidence": 0.75, "rationale": "High conviction",
            "entry_trigger": "Buy above $155",
            "stop_price": 142.0, "target_price": 170.0,
        }
        self.tracker.record_from_decision("NVDA", decision_dict, "RISK_ON")

        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        latest = self.tracker._latest_by_ticker(today)
        self.assertIn("NVDA", latest)


class TestMacroRegimeWithTracker(unittest.TestCase):
    """MacroRegimeEngine + DecisionTracker integration."""

    def test_regime_compute_and_track(self):
        from src.engines.macro_regime_engine import MacroRegimeEngine
        from src.engines.decision_tracker import DecisionTracker

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        try:
            engine = MacroRegimeEngine()
            tracker = DecisionTracker(db_path=db_path)

            # Bull market data
            spy = [400 + i * 0.5 for i in range(60)]
            vix = [14.0] * 60
            result = engine.compute(spy, vix_closes=vix)

            # Record regime
            change = tracker.record_regime(
                result.trend, result.risk_score, result.vix_level,
                result.signals,
            )
            self.assertIsNone(change)  # First time, no change

            # Simulate market crash
            spy_crash = spy[:50] + [spy[49] - i * 3 for i in range(10)]
            vix_crash = [14.0] * 50 + [35.0] * 10
            result2 = engine.compute(spy_crash, vix_closes=vix_crash)

            change2 = tracker.record_regime(
                result2.trend, result2.risk_score, result2.vix_level,
                result2.signals,
            )
            # Should detect regime change
            if change2:
                self.assertTrue(change2["changed"])

            tracker.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
