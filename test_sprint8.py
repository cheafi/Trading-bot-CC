"""
Sprint 8 Tests — Singleton BrokerManager, EdgeCalculator, Position Sizing, Persistence

Tests:
1-4:  Singleton BrokerManager (no more BrokerManager() in hot paths)
5-6:  BrokerError in BrokerManager
7-9:  EdgeCalculator.compute() invocation in signal ranking
10-12: Position sizing via PositionManager
13-16: Learning loop JSON persistence
17:   Full regression anchor
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent


def _load(name, rel_path):
    full = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(full))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


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

_load("src.core.config", "src/core/config.py")
_load("src.core.models", "src/core/models.py")
_load("src.core.errors", "src/core/errors.py")


class TestSingletonBrokerManager(unittest.TestCase):
    """Tests 1-4: No more BrokerManager() instantiation in hot paths."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_01_get_broker_method_exists(self):
        """_get_broker() singleton helper exists."""
        self.assertIn("async def _get_broker(self)", self.src)

    def test_02_broker_mgr_in_init(self):
        """self._broker_mgr initialized to None in __init__."""
        self.assertIn("self._broker_mgr = None", self.src)

    def test_03_no_broker_manager_in_execute_signal(self):
        """Execution path uses _get_broker() not BrokerManager()."""
        idx = self.src.find("async def _execute_recommendation(")
        next_method = self.src.find("\n    async def ", idx + 10)
        if next_method == -1:
            next_method = self.src.find("\n    def ", idx + 10)
        block = self.src[idx:next_method]
        self.assertNotIn("BrokerManager()", block)
        self.assertIn("_get_broker()", block)

    def test_04_no_broker_manager_in_monitor(self):
        """_monitor_positions uses _get_broker() not BrokerManager()."""
        idx = self.src.find("async def _monitor_positions(")
        next_method = self.src.find("\n    async def ", idx + 10)
        if next_method == -1:
            next_method = self.src.find("\n    def ", idx + 10)
        block = self.src[idx:next_method]
        self.assertNotIn("BrokerManager()", block)
        self.assertIn("_get_broker()", block)


class TestBrokerManagerError(unittest.TestCase):
    """Tests 5-6: BrokerError in BrokerManager."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/brokers/broker_manager.py").read_text()

    def test_05_broker_error_imported(self):
        """BrokerError imported in broker_manager.py."""
        self.assertIn("BrokerError", self.src)

    def test_06_place_order_raises_broker_error(self):
        """place_order raises BrokerError when no broker available."""
        self.assertIn("raise BrokerError", self.src)
        idx = self.src.find("raise BrokerError")
        block = self.src[idx:idx + 200]
        self.assertIn("No broker available", block)


class TestEdgeCalculatorInvocation(unittest.TestCase):
    """Tests 7-9: EdgeCalculator.compute() called in signal ranking."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_07_edge_compute_called(self):
        """EdgeCalculator.compute() called in signal ranking."""
        self.assertIn("self.edge_calculator.compute(", self.src)

    def test_08_edge_data_in_signal_dict(self):
        """Edge fields exist on TradeRecommendation (formerly signal dict)."""
        model_src = (ROOT / "src/core/models.py").read_text()
        for field in ["edge_p_t1", "edge_p_stop", "edge_ev"]:
            self.assertIn(
                field, self.src + model_src,
                f"Missing edge field: {field}",
            )

    def test_09_edge_graceful_fallback(self):
        """EdgeCalculator errors are caught gracefully."""
        idx = self.src.find("edge_calculator.compute(")
        block = self.src[idx:idx + 800]
        self.assertIn("except", block)
        # Accepts either bare pass or typed catch with logging
        has_fallback = "pass" in block or "logger.debug" in block
        self.assertTrue(has_fallback, "Edge fallback must use pass or logger.debug")


class TestPositionSizingUpgrade(unittest.TestCase):
    """Tests 10-12: Position sizing via PositionManager."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/engines/auto_trading_engine.py").read_text()

    def test_10_uses_position_manager(self):
        """_calculate_position_size calls position_mgr."""
        idx = self.src.find("def _calculate_position_size(")
        block = self.src[idx:idx + 2000]
        self.assertIn(
            "self.position_mgr.calculate_position_size(",
            block,
        )

    def test_11_has_fallback(self):
        """Still has fallback simple calculation."""
        idx = self.src.find("def _calculate_position_size(")
        block = self.src[idx:idx + 3000]
        self.assertTrue(
            "allback" in block.lower(),
            "Should have a fallback path for position sizing",
        )

    def test_12_uses_config_stop_loss(self):
        """Uses trading_config.stop_loss_pct for stop calculation."""
        idx = self.src.find("def _calculate_position_size(")
        block = self.src[idx:idx + 1500]
        self.assertIn("trading_config.stop_loss_pct", block)


class TestLearningPersistence(unittest.TestCase):
    """Tests 13-16: JSON persistence for trade outcomes."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/ml/trade_learner.py").read_text()

    def test_13_persist_method_exists(self):
        """_persist_outcomes() method exists."""
        self.assertIn("def _persist_outcomes(self)", self.src)

    def test_14_load_method_exists(self):
        """_load_persisted_outcomes() method exists."""
        self.assertIn("def _load_persisted_outcomes(self)", self.src)

    def test_15_load_called_in_init(self):
        """_load_persisted_outcomes called in __init__."""
        idx = self.src.find("class TradeLearningLoop")
        init_idx = self.src.find("def __init__(self)", idx)
        next_method = self.src.find("\n    def ", init_idx + 10)
        init_block = self.src[init_idx:next_method]
        self.assertIn(
            "_load_persisted_outcomes",
            init_block,
        )

    def test_16_persist_on_retrain(self):
        """_persist_outcomes called after auto-retrain."""
        idx = self.src.find("def record_outcome(self")
        block = self.src[idx:idx + 800]
        self.assertIn("_persist_outcomes", block)

    def test_17_json_file_path(self):
        """Persistence uses trade_outcomes.json."""
        self.assertIn("trade_outcomes.json", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
