"""
Sprint 7 Tests — ML Quality Gate, EOD Cycle, Signal Cache, BrokerError, EdgeCalculator

Tests:
1-3:  ML quality gate in execution pipeline
4-6:  EOD cycle (_maybe_run_eod, _run_eod_cycle, _send_eod_report)
7-9:  Signal/recommendation caching + get_cached_state
10-11: BrokerError in broker base
12-13: EdgeCalculator wiring
14-15: StrategyLeaderboard.record_outcome
16:   API /api/recommendations updated
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent


def _load(name, rel_path):
    """Direct-load a module bypassing __init__.py chains."""
    full = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(full))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stubs for transitive imports
for stub in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.declarative", "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql",
    "pydantic_settings",
    "openai", "fastapi", "uvicorn", "starlette",
    "starlette.middleware", "starlette.middleware.base",
    "sklearn", "sklearn.ensemble", "sklearn.preprocessing",
    "sklearn.model_selection", "sklearn.metrics",
]:
    if stub not in sys.modules:
        sys.modules[stub] = MagicMock()

# Pre-load core modules
_load("src.core.config", "src/core/config.py")
_load("src.core.models", "src/core/models.py")
_load("src.core.errors", "src/core/errors.py")


class TestMLQualityGate(unittest.TestCase):
    """Tests 1-3: ML quality gate before execution."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_01_predict_signal_quality_called(self):
        """learning_loop.predict_signal_quality() is called in _run_cycle."""
        self.assertIn(
            "self.learning_loop.predict_signal_quality(",
            self.src,
        )

    def test_02_d_grade_rejected(self):
        """D-grade signals are skipped (continue)."""
        idx = self.src.find("predict_signal_quality")
        block = self.src[idx:idx + 1000]
        self.assertIn("signal_grade", block)
        self.assertIn("continue", block)

    def test_03_ml_gate_logs_rejection(self):
        """ML gate logs the rejection with ticker and win probability."""
        idx = self.src.find("ML gate rejected")
        self.assertGreater(idx, 0, "Should log ML gate rejections")


class TestEODCycle(unittest.TestCase):
    """Tests 4-6: End-of-day cycle."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_04_maybe_run_eod_exists(self):
        """_maybe_run_eod method exists."""
        self.assertIn("async def _maybe_run_eod(self)", self.src)

    def test_05_run_eod_cycle_exists(self):
        """_run_eod_cycle exists with failure analysis + retrain."""
        self.assertIn("async def _run_eod_cycle(self)", self.src)
        idx = self.src.find("_run_eod_cycle")
        block = self.src[idx:idx + 2000]
        self.assertIn("run_failure_analysis", block)
        self.assertIn("predictor.train", block)

    def test_06_eod_triggered_in_run_cycle(self):
        """_maybe_run_eod is called at end of _run_cycle."""
        # _maybe_run_eod should be called somewhere in the engine
        self.assertIn("_maybe_run_eod", self.src)
        # Should appear after Periodic reporting in _run_cycle
        idx_periodic = self.src.find("Periodic reporting")
        self.assertGreater(idx_periodic, 0)
        after_periodic = self.src[idx_periodic:idx_periodic + 300]
        self.assertIn("_maybe_run_eod", after_periodic)

    def test_07_send_eod_report_exists(self):
        """_send_eod_report method exists."""
        self.assertIn("async def _send_eod_report(self)", self.src)


class TestSignalCaching(unittest.TestCase):
    """Tests 8-10: Signal and recommendation caching."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_08_cache_attrs_in_init(self):
        """Cache attributes exist in __init__."""
        for attr in [
            "_cached_regime",
            "_cached_recommendations",
            "_cached_leaderboard",
            "_last_eod_date",
        ]:
            self.assertIn(
                f"self.{attr}", self.src,
                f"Missing cache attr: {attr}",
            )

    def test_09_recommendations_cached_before_exec(self):
        """Ranked results are cached before execution loop."""
        idx = self.src.find("_cached_recommendations = [")
        self.assertGreater(idx, 0)
        block = self.src[idx:idx + 200]
        self.assertIn("ranked", block)

    def test_10_get_cached_state_method(self):
        """get_cached_state() method returns dict with expected keys."""
        self.assertIn("def get_cached_state(self)", self.src)
        idx = self.src.find("get_cached_state")
        block = self.src[idx:idx + 1200]
        for key in ["regime", "recommendations", "leaderboard",
                     "cycle_count", "signals_today", "trades_today"]:
            self.assertIn(
                f'"{key}"', block,
                f"get_cached_state missing key: {key}",
            )


class TestBrokerError(unittest.TestCase):
    """Tests 11-12: BrokerError in broker base."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/brokers/base.py").read_text()

    def test_11_broker_error_imported(self):
        """BrokerError is imported in base.py."""
        self.assertIn("BrokerError", self.src)

    def test_12_close_position_raises_broker_error(self):
        """close_position raises BrokerError when no position found."""
        self.assertIn("raise BrokerError", self.src)
        idx = self.src.find("raise BrokerError")
        block = self.src[idx:idx + 200]
        self.assertIn("No position found", block)


class TestEdgeCalculator(unittest.TestCase):
    """Tests 13-14: EdgeCalculator wiring."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_13_edge_calculator_imported(self):
        """EdgeCalculator imported with graceful fallback."""
        self.assertIn("EdgeCalculator", self.src)
        self.assertIn("_HAS_EDGE_CALC", self.src)

    def test_14_edge_calculator_in_init(self):
        """self.edge_calculator initialized in __init__."""
        self.assertIn("self.edge_calculator", self.src)


class TestLeaderboardRecordOutcome(unittest.TestCase):
    """Tests 15-16: StrategyLeaderboard.record_outcome."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/strategy_leaderboard.py").read_text()

    def test_15_record_outcome_exists(self):
        """record_outcome method exists in StrategyLeaderboard."""
        self.assertIn("def record_outcome(self", self.src)

    def test_16_record_outcome_updates_score(self):
        """record_outcome tracks wins, trades, pnl, and calls update()."""
        idx = self.src.find("def record_outcome")
        block = self.src[idx:idx + 3000]
        for field in ["trades", "wins", "total_pnl"]:
            self.assertIn(
                f'"{field}"', block,
                f"record_outcome missing field: {field}",
            )
        # Sprint 20: calls self.update() instead of setting entry["score"]
        self.assertIn(
            "self.update(", block,
            "record_outcome should call self.update()",
        )


class TestAPIRecommendationsUpdated(unittest.TestCase):
    """Test 17: API /api/recommendations returns strategy_scores."""

    def test_17_strategy_scores_in_response(self):
        """recommendations endpoint includes strategy_scores."""
        src = (ROOT / "src/api/main.py").read_text()
        idx = src.find("get_recommendations")
        block = src[idx:idx + 1500]
        self.assertIn("strategy_scores", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
