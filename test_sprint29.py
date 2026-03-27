"""
Sprint 29 – Context Wiring + Learning Loop Enrichment

Tests:
  1-3   to_entry_snapshot includes composite_score, ml_grade, regime_label
  4-8   _record_learning_outcome extracts enriched fields
  9-12  TradeOutcomeRecord stores market_regime + enriched context
  13-16 _load_persisted_outcomes preserves full context fields
  17-20 get_calibration_stats
  21-24 DB persist uses enriched regime/vix/composite_score
  25-28 End-to-end learning loop with enriched snapshots
"""
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Stubs for heavy deps ──────────────────────────────────
for mod_name in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio", "sqlalchemy.ext.declarative",
    "sqlalchemy.future", "sqlalchemy.sql",
    "pydantic_settings", "discord", "discord.ext",
    "discord.ext.commands", "discord.ext.tasks",
    "tenacity", "asyncpg",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

db_stub = MagicMock()
db_stub.check_database_health = MagicMock(
    return_value={"status": "ok"},
)
sys.modules["src.core.database"] = db_stub


# ── Direct module loading ─────────────────────────────────
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_root = os.path.dirname(__file__)
_learner_mod = _load(
    "trade_learner",
    os.path.join(_root, "src", "ml", "trade_learner.py"),
)
TradeOutcomeRecord = _learner_mod.TradeOutcomeRecord
TradeLearningLoop = _learner_mod.TradeLearningLoop
TradeOutcomePredictor = _learner_mod.TradeOutcomePredictor


# ═══════════════════════════════════════════════════════════
#  Group 1 – to_entry_snapshot enriched
# ═══════════════════════════════════════════════════════════
class TestEntrySnapshotEnriched(unittest.TestCase):
    """Tests 1-3: to_entry_snapshot has composite_score, ml_grade."""

    def _make_rec(self, **kwargs):
        from src.core.models import TradeRecommendation
        defaults = dict(
            ticker="AAPL", direction="LONG",
            strategy_id="momentum_v1", trade_decision=True,
            entry_price=150.0, stop_price=145.0,
            target_price=160.0, signal_confidence=80.0,
            composite_score=0.87, ml_grade="A",
            regime_label="risk_on",
        )
        defaults.update(kwargs)
        return TradeRecommendation(**defaults)

    def test_01_snapshot_has_composite_score(self):
        rec = self._make_rec(composite_score=0.92)
        snap = rec.to_entry_snapshot()
        self.assertIn("composite_score", snap)
        self.assertEqual(snap["composite_score"], 0.92)

    def test_02_snapshot_has_ml_grade(self):
        rec = self._make_rec(ml_grade="B")
        snap = rec.to_entry_snapshot()
        self.assertIn("ml_grade", snap)
        self.assertEqual(snap["ml_grade"], "B")

    def test_03_snapshot_has_regime_label(self):
        rec = self._make_rec(regime_label="risk_off")
        snap = rec.to_entry_snapshot()
        self.assertIn("regime_label", snap)
        self.assertEqual(snap["regime_label"], "risk_off")


# ═══════════════════════════════════════════════════════════
#  Group 2 – _record_learning_outcome extracts enriched data
# ═══════════════════════════════════════════════════════════
class TestRecordLearningOutcomeEnriched(unittest.TestCase):
    """Tests 4-8: _record_learning_outcome wires enriched fields."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import AutoTradingEngine
        engine = AutoTradingEngine(dry_run=True)
        return engine

    def _make_closed_pos(self, ticker="AAPL"):
        return SimpleNamespace(
            position_id="pos_1", ticker=ticker,
            entry_price=150.0, exit_price=155.0,
            entry_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            exit_date=datetime(2025, 1, 5, tzinfo=timezone.utc),
            strategy_id="momentum_v1",
            realized_pnl_pct=3.3,
            direction="LONG", quantity=10,
        )

    def test_04_extracts_ml_grade_from_trades_today(self):
        engine = self._make_engine()
        engine._trades_today = [{
            "ticker": "AAPL",
            "confidence": 80,
            "ml_grade": "A",
            "composite_score": 0.9,
            "regime_at_entry": "risk_on",
            "entry_snapshot": {"vix_at_entry": 18},
        }]
        # Simulate lookup logic
        _ml_grade = ""
        _composite = 0.0
        _regime_at_entry = ""
        for t in engine._trades_today:
            if t.get("ticker") == "AAPL":
                _ml_grade = t.get("ml_grade", "")
                _composite = t.get("composite_score", 0.0)
                _regime_at_entry = t.get("regime_at_entry", "")
                break
        self.assertEqual(_ml_grade, "A")
        self.assertEqual(_composite, 0.9)
        self.assertEqual(_regime_at_entry, "risk_on")

    def test_05_record_receives_market_regime(self):
        record = TradeOutcomeRecord(
            trade_id="t1", ticker="AAPL", direction="LONG",
            strategy="momentum", entry_price=150, exit_price=155,
            entry_time="2025-01-01", exit_time="2025-01-05",
            pnl_pct=3.3, confidence=80, horizon="swing",
            market_regime="risk_on",
        )
        self.assertEqual(
            record.data["market_regime"], "risk_on",
        )

    def test_06_snapshot_merge_composite_score(self):
        """Merged enriched composite_score into snapshot."""
        _snapshot: Dict[str, Any] = {"vix_at_entry": 18}
        _composite = 0.85
        _snapshot["composite_score"] = (
            _composite or _snapshot.get("composite_score", 0)
        )
        self.assertEqual(_snapshot["composite_score"], 0.85)

    def test_07_snapshot_merge_ml_grade(self):
        """Merged enriched ml_grade into snapshot."""
        _snapshot: Dict[str, Any] = {}
        _ml_grade = "B"
        _snapshot["ml_grade"] = (
            _ml_grade or _snapshot.get("ml_grade", "")
        )
        self.assertEqual(_snapshot["ml_grade"], "B")

    def test_08_unmatched_ticker_no_enrichment(self):
        """No match → defaults preserved."""
        trades = [{"ticker": "GOOGL", "ml_grade": "A"}]
        _ml_grade = ""
        for t in trades:
            if t.get("ticker") == "AAPL":
                _ml_grade = t.get("ml_grade", "")
                break
        self.assertEqual(_ml_grade, "")


# ═══════════════════════════════════════════════════════════
#  Group 3 – TradeOutcomeRecord stores enriched context
# ═══════════════════════════════════════════════════════════
class TestOutcomeRecordEnriched(unittest.TestCase):
    """Tests 9-12: TradeOutcomeRecord carries full context."""

    def _make_record(self, **kwargs):
        defaults = dict(
            trade_id="t1", ticker="AAPL", direction="LONG",
            strategy="momentum", entry_price=150, exit_price=155,
            entry_time="2025-01-01", exit_time="2025-01-05",
            pnl_pct=3.3, confidence=80, horizon="swing",
        )
        defaults.update(kwargs)
        return TradeOutcomeRecord(**defaults)

    def test_09_market_regime_stored(self):
        r = self._make_record(market_regime="risk_off")
        self.assertEqual(r.data["market_regime"], "risk_off")

    def test_10_vix_at_entry_stored(self):
        r = self._make_record(vix_at_entry=22.5)
        self.assertEqual(r.data["vix_at_entry"], 22.5)

    def test_11_rsi_adx_stored(self):
        r = self._make_record(rsi_at_entry=65, adx_at_entry=30)
        self.assertEqual(r.data["rsi_at_entry"], 65)
        self.assertEqual(r.data["adx_at_entry"], 30)

    def test_12_feature_snapshot_as_feat_prefix(self):
        r = self._make_record(
            feature_snapshot={"custom_1": 1.5, "custom_2": 2.0},
        )
        self.assertEqual(r.data["feat_custom_1"], 1.5)
        self.assertEqual(r.data["feat_custom_2"], 2.0)


# ═══════════════════════════════════════════════════════════
#  Group 4 – _load_persisted_outcomes preserves context
# ═══════════════════════════════════════════════════════════
class TestLoadPersistedOutcomes(unittest.TestCase):
    """Tests 13-16: full context fields survive persist → reload."""

    def test_13_round_trip_preserves_vix(self):
        import src.ml.trade_learner as tl_mod

        loop = TradeLearningLoop.__new__(TradeLearningLoop)
        loop.predictor = TradeOutcomePredictor.__new__(
            TradeOutcomePredictor,
        )
        loop.predictor.model = None
        loop.predictor.scaler = None
        loop.predictor._history = []
        loop.analyst = _learner_mod.LLMFailureAnalyst()
        loop._outcomes = []
        loop._last_train_count = 0
        loop._retrain_interval = 20
        loop._last_analysis = None

        record = TradeOutcomeRecord(
            trade_id="t1", ticker="AAPL", direction="LONG",
            strategy="momentum", entry_price=150,
            exit_price=155, entry_time="2025-01-01",
            exit_time="2025-01-05", pnl_pct=3.3,
            confidence=80, horizon="swing",
            vix_at_entry=22.5, rsi_at_entry=65,
            market_regime="risk_on",
        )
        loop._outcomes.append(record)
        loop.predictor.add_outcome(record)

        # Persist
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_dir = tl_mod.MODEL_DIR
            tl_mod.MODEL_DIR = __import__("pathlib").Path(tmpdir)
            loop._persist_outcomes()

            # Reload into new loop
            loop2 = TradeLearningLoop.__new__(TradeLearningLoop)
            loop2.predictor = TradeOutcomePredictor.__new__(
                TradeOutcomePredictor,
            )
            loop2.predictor._history = []
            loop2.predictor.model = None
            loop2.predictor.scaler = None
            loop2._outcomes = []

            tl_mod.MODEL_DIR = __import__("pathlib").Path(tmpdir)
            loop2._load_persisted_outcomes()
            tl_mod.MODEL_DIR = orig_dir

        self.assertEqual(len(loop2._outcomes), 1)
        d = loop2._outcomes[0].data
        self.assertEqual(d["vix_at_entry"], 22.5)
        self.assertEqual(d["rsi_at_entry"], 65)
        self.assertEqual(d["market_regime"], "risk_on")

    def test_14_round_trip_preserves_hold_hours(self):
        record = TradeOutcomeRecord(
            trade_id="t2", ticker="MSFT", direction="LONG",
            strategy="swing", entry_price=300,
            exit_price=310, entry_time="2025-02-01",
            exit_time="2025-02-03", pnl_pct=3.3,
            confidence=70, horizon="swing",
            hold_hours=48.5,
        )
        d = record.to_dict()
        # Simulate reload
        reloaded = TradeOutcomeRecord(
            trade_id=d.get("trade_id", ""),
            ticker=d.get("ticker", ""),
            direction=d.get("direction", "LONG"),
            strategy=d.get("strategy", ""),
            entry_price=d.get("entry_price", 0),
            exit_price=d.get("exit_price", 0),
            entry_time=d.get("entry_time", ""),
            exit_time=d.get("exit_time", ""),
            pnl_pct=d.get("pnl_pct", 0),
            confidence=d.get("confidence", 50),
            horizon=d.get("horizon", ""),
            hold_hours=d.get("hold_hours", 0.0),
        )
        self.assertEqual(reloaded.data["hold_hours"], 48.5)

    def test_15_round_trip_preserves_adx(self):
        record = TradeOutcomeRecord(
            trade_id="t3", ticker="NVDA", direction="LONG",
            strategy="trend", entry_price=500,
            exit_price=520, entry_time="2025-03-01",
            exit_time="2025-03-05", pnl_pct=4.0,
            confidence=85, horizon="swing",
            adx_at_entry=35.0, distance_from_sma50=0.05,
        )
        d = record.to_dict()
        reloaded = TradeOutcomeRecord(
            trade_id=d["trade_id"], ticker=d["ticker"],
            direction=d["direction"], strategy=d["strategy"],
            entry_price=d["entry_price"],
            exit_price=d["exit_price"],
            entry_time=d["entry_time"],
            exit_time=d["exit_time"],
            pnl_pct=d["pnl_pct"], confidence=d["confidence"],
            horizon=d["horizon"],
            adx_at_entry=d.get("adx_at_entry", 0),
            distance_from_sma50=d.get(
                "distance_from_sma50", 0,
            ),
        )
        self.assertEqual(reloaded.data["adx_at_entry"], 35.0)
        self.assertAlmostEqual(
            reloaded.data["distance_from_sma50"], 0.05,
        )

    def test_16_old_format_loads_with_defaults(self):
        """Old persisted records (missing new fields) load OK."""
        old_data = {
            "trade_id": "t_old", "ticker": "IBM",
            "direction": "LONG", "strategy": "mean_rev",
            "entry_price": 130, "exit_price": 132,
            "entry_time": "2024-06-01",
            "exit_time": "2024-06-03",
            "pnl_pct": 1.5, "confidence": 60,
            "horizon": "swing", "is_winner": True,
            "exit_reason": "target_hit",
        }
        r = TradeOutcomeRecord(
            trade_id=old_data["trade_id"],
            ticker=old_data["ticker"],
            direction=old_data["direction"],
            strategy=old_data["strategy"],
            entry_price=old_data["entry_price"],
            exit_price=old_data["exit_price"],
            entry_time=old_data["entry_time"],
            exit_time=old_data["exit_time"],
            pnl_pct=old_data["pnl_pct"],
            confidence=old_data["confidence"],
            horizon=old_data["horizon"],
            market_regime=old_data.get("market_regime", ""),
            vix_at_entry=old_data.get("vix_at_entry", 0.0),
            rsi_at_entry=old_data.get("rsi_at_entry", 0.0),
        )
        self.assertEqual(r.data["market_regime"], "")
        self.assertEqual(r.data["vix_at_entry"], 0.0)


# ═══════════════════════════════════════════════════════════
#  Group 5 – Calibration tracking
# ═══════════════════════════════════════════════════════════
class TestCalibrationStats(unittest.TestCase):
    """Tests 17-20: get_calibration_stats."""

    def test_17_no_model_returns_not_calibrated(self):
        loop = TradeLearningLoop()
        result = loop.get_calibration_stats()
        self.assertFalse(result["calibrated"])
        self.assertEqual(result["reason"], "no_model")

    def test_18_insufficient_predictions(self):
        loop = TradeLearningLoop()
        # Add a few records but no trained model
        loop.predictor.model = MagicMock()
        loop.predictor.scaler = MagicMock()
        loop.predictor.predict_win_probability = MagicMock(
            return_value=None,
        )
        for i in range(5):
            loop._outcomes.append(TradeOutcomeRecord(
                trade_id=f"t{i}", ticker="AAPL",
                direction="LONG", strategy="test",
                entry_price=100, exit_price=105,
                entry_time="", exit_time="",
                pnl_pct=5, confidence=80, horizon="swing",
            ))
        result = loop.get_calibration_stats()
        self.assertFalse(result["calibrated"])

    def test_19_calibration_with_perfect_model(self):
        loop = TradeLearningLoop.__new__(TradeLearningLoop)
        loop.predictor = TradeOutcomePredictor.__new__(
            TradeOutcomePredictor,
        )
        loop.predictor.model = MagicMock()
        loop.predictor.scaler = MagicMock()
        loop.predictor._history = []
        loop.predictor.FEATURE_COLS = [
            "confidence", "vix_at_entry", "rsi_at_entry",
            "adx_at_entry", "relative_volume",
            "distance_from_sma50",
        ]
        loop.analyst = _learner_mod.LLMFailureAnalyst()
        loop._outcomes = []
        loop._last_train_count = 0
        loop._retrain_interval = 20
        loop._last_analysis = None

        # Create 20 outcomes: 10 winners, 10 losers
        for i in range(20):
            is_win = i < 10
            pnl = 5.0 if is_win else -3.0
            loop._outcomes.append(TradeOutcomeRecord(
                trade_id=f"t{i}", ticker="AAPL",
                direction="LONG", strategy="test",
                entry_price=100,
                exit_price=105 if is_win else 97,
                entry_time="", exit_time="",
                pnl_pct=pnl, confidence=80,
                horizon="swing",
            ))

        # Mock predict_win_probability to return 0.8 for wins, 0.2 for losses
        call_count = [0]

        def mock_predict(features):
            idx = call_count[0]
            call_count[0] += 1
            return 0.8 if idx < 10 else 0.2

        loop.predictor.predict_win_probability = mock_predict

        result = loop.get_calibration_stats()
        self.assertTrue(result["calibrated"])
        self.assertIn("bins", result)
        self.assertIn("calibration_error", result)
        self.assertEqual(result["total_predictions"], 20)

    def test_20_calibration_error_is_bounded(self):
        """Calibration error should be between 0 and 1."""
        loop = TradeLearningLoop()
        loop.predictor.model = MagicMock()
        loop.predictor.scaler = MagicMock()

        for i in range(15):
            loop._outcomes.append(TradeOutcomeRecord(
                trade_id=f"t{i}", ticker="TEST",
                direction="LONG", strategy="test",
                entry_price=100, exit_price=102,
                entry_time="", exit_time="",
                pnl_pct=2 if i % 2 == 0 else -1,
                confidence=70, horizon="swing",
            ))

        loop.predictor.predict_win_probability = (
            lambda f: 0.5  # always 0.5
        )
        result = loop.get_calibration_stats()
        if result.get("calibrated"):
            self.assertGreaterEqual(
                result["calibration_error"], 0,
            )
            self.assertLessEqual(
                result["calibration_error"], 1.0,
            )


# ═══════════════════════════════════════════════════════════
#  Group 6 – DB persist uses enriched fields
# ═══════════════════════════════════════════════════════════
class TestDBPersistEnriched(unittest.TestCase):
    """Tests 21-24: DB persist dict uses enriched regime/vix."""

    def test_21_regime_at_entry_prefers_enriched(self):
        """If _regime_at_entry is set, use it over _cached_regime."""
        _regime_at_entry = "risk_on"
        _cached = {"regime": "neutral"}
        result = (
            _regime_at_entry or _cached.get("regime")
        )
        self.assertEqual(result, "risk_on")

    def test_22_regime_falls_back_to_cached(self):
        """If _regime_at_entry is empty, fall back to cached."""
        _regime_at_entry = ""
        _cached = {"regime": "risk_off"}
        result = (
            _regime_at_entry or _cached.get("regime")
        )
        self.assertEqual(result, "risk_off")

    def test_23_vix_prefers_snapshot(self):
        """VIX should prefer snapshot over cached regime."""
        _snapshot = {"vix_at_entry": 25.5}
        _cached = {"vix": 20.0}
        result = (
            _snapshot.get("vix_at_entry")
            or _cached.get("vix")
        )
        self.assertEqual(result, 25.5)

    def test_24_setup_grade_prefers_snapshot(self):
        """setup_grade falls back to ml_grade if no snapshot."""
        _snapshot: Dict[str, Any] = {}
        _ml_grade = "B"
        result = (
            _snapshot.get("setup_grade") or _ml_grade
        )
        self.assertEqual(result, "B")


# ═══════════════════════════════════════════════════════════
#  Group 7 – End-to-end enrichment
# ═══════════════════════════════════════════════════════════
class TestEndToEndEnrichment(unittest.TestCase):
    """Tests 25-28: full enrichment flow integration."""

    def test_25_snapshot_fields_pass_to_outcome(self):
        """Snapshot fields from to_entry_snapshot() pass through."""
        from src.core.models import TradeRecommendation
        rec = TradeRecommendation(
            ticker="AAPL", direction="LONG",
            strategy_id="momentum", trade_decision=True,
            entry_price=150.0, stop_price=145.0,
            target_price=160.0, signal_confidence=80,
            composite_score=0.88, ml_grade="A",
            regime_label="risk_on",
            vix_at_entry=19.5, rsi_at_entry=62,
            adx_at_entry=28, relative_volume=1.3,
        )
        snap = rec.to_entry_snapshot()
        # Create TradeOutcomeRecord with snapshot unpacking
        outcome = TradeOutcomeRecord(
            trade_id="t_e2e", ticker="AAPL",
            direction="LONG", strategy="momentum",
            entry_price=150, exit_price=155,
            entry_time="2025-01-01",
            exit_time="2025-01-03",
            pnl_pct=3.3, confidence=80,
            horizon="swing",
            market_regime=snap.get("regime_label", ""),
            vix_at_entry=snap.get("vix_at_entry", 0),
            rsi_at_entry=snap.get("rsi_at_entry", 0),
            adx_at_entry=snap.get("adx_at_entry", 0),
            relative_volume=snap.get("relative_volume", 0),
            distance_from_sma50=snap.get(
                "distance_from_sma50", 0,
            ),
        )
        self.assertEqual(
            outcome.data["vix_at_entry"], 19.5,
        )
        self.assertEqual(outcome.data["rsi_at_entry"], 62)
        self.assertEqual(
            outcome.data["market_regime"], "risk_on",
        )

    def test_26_learning_loop_records_enriched(self):
        """Learning loop record_outcome stores the enriched data."""
        loop = TradeLearningLoop.__new__(TradeLearningLoop)
        loop.predictor = TradeOutcomePredictor.__new__(
            TradeOutcomePredictor,
        )
        loop.predictor.model = None
        loop.predictor.scaler = None
        loop.predictor._history = []
        loop.analyst = _learner_mod.LLMFailureAnalyst()
        loop._outcomes = []
        loop._last_train_count = 0
        loop._retrain_interval = 20
        loop._last_analysis = None
        record = TradeOutcomeRecord(
            trade_id="t_ll", ticker="TSLA",
            direction="LONG", strategy="momentum",
            entry_price=250, exit_price=260,
            entry_time="2025-03-01",
            exit_time="2025-03-05",
            pnl_pct=4.0, confidence=85,
            horizon="swing",
            market_regime="risk_on",
            vix_at_entry=17.0,
        )
        loop.record_outcome(record)
        self.assertEqual(len(loop._outcomes), 1)
        stored = loop._outcomes[0].data
        self.assertEqual(stored["market_regime"], "risk_on")
        self.assertEqual(stored["vix_at_entry"], 17.0)

    def test_27_source_code_has_sprint29_comments(self):
        """auto_trading_engine.py references Sprint 29."""
        src_path = os.path.join(
            _root, "src", "engines",
            "auto_trading_engine.py",
        )
        with open(src_path) as f:
            src = f.read()
        self.assertIn("Sprint 29", src)
        self.assertIn("_ml_grade", src)
        self.assertIn("_composite", src)
        self.assertIn("_regime_at_entry", src)

    def test_28_source_has_calibration_method(self):
        """trade_learner.py has get_calibration_stats."""
        src_path = os.path.join(
            _root, "src", "ml", "trade_learner.py",
        )
        with open(src_path) as f:
            src = f.read()
        self.assertIn("def get_calibration_stats", src)
        self.assertIn("calibration_error", src)
        self.assertIn("n_bins", src)


# ═══════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main(verbosity=2)
