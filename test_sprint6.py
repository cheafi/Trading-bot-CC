"""
Sprint 6 Tests — Learning Loop + Monitoring + API + Error Types

Tests:
1-3:  Structured error hierarchy
4-5:  Fixed open_position call signature
6-8:  TradeLearningLoop wiring
9-11: Upgraded _monitor_positions
12-14: API endpoints
15:   Structured error usage in engine
"""
import importlib.util
import inspect
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


def _load(name: str, rel_path: str):
    """Direct-load a module bypassing __init__.py chains."""
    full = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(full))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- Stubs required before loading modules ----
# Minimal stubs for transitive imports
for stub_name in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.declarative", "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql",
    "pydantic_settings",
    "openai", "fastapi", "uvicorn", "starlette",
    "starlette.middleware", "starlette.middleware.base",
    "sklearn", "sklearn.ensemble", "sklearn.preprocessing",
    "sklearn.model_selection", "sklearn.metrics",
]:
    if stub_name not in sys.modules:
        sys.modules[stub_name] = MagicMock()

# Pre-load core modules
config_mod = _load("src.core.config", "src/core/config.py")
models_mod = _load("src.core.models", "src/core/models.py")
errors_mod = _load("src.core.errors", "src/core/errors.py")


class TestErrorHierarchy(unittest.TestCase):
    """Tests 1-3: Structured error types."""

    def test_01_base_class_exists(self):
        """TradingError is the base and all subtypes inherit from it."""
        self.assertTrue(hasattr(errors_mod, "TradingError"))
        for name in ["BrokerError", "DataError", "ValidationError",
                      "RiskLimitError", "SignalError", "ConfigError"]:
            cls = getattr(errors_mod, name)
            self.assertTrue(
                issubclass(cls, errors_mod.TradingError),
                f"{name} should be a subclass of TradingError",
            )

    def test_02_error_to_dict(self):
        """Error instances serialize to dict with type, message, code."""
        err = errors_mod.BrokerError(message="timeout", broker="alpaca")
        d = err.to_dict()
        self.assertEqual(d["error_type"], "BrokerError")
        self.assertEqual(d["message"], "timeout")
        self.assertIn("alpaca", d["detail"])

    def test_03_error_is_catchable(self):
        """Catching TradingError catches all subtypes."""
        for cls in [errors_mod.BrokerError, errors_mod.DataError,
                     errors_mod.RiskLimitError]:
            with self.assertRaises(errors_mod.TradingError):
                raise cls("test")


class TestOpenPositionCallFix(unittest.TestCase):
    """Tests 4-5: Fixed open_position call kwargs."""

    def test_04_no_direction_kwarg(self):
        """open_position call no longer passes 'direction' kwarg."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        # Find the open_position call block
        idx = src.find("self.position_mgr.open_position(")
        self.assertGreater(idx, 0, "open_position call must exist")
        call_block = src[idx:idx + 500]
        self.assertNotIn("direction=", call_block,
                         "Should not pass 'direction' to PositionManager.open_position")

    def test_05_uses_strategy_id_and_stop_loss(self):
        """open_position call passes strategy_id and stop_loss_price."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        idx = src.find("self.position_mgr.open_position(")
        call_block = src[idx:idx + 2000]
        self.assertIn("strategy_id=", call_block)
        self.assertIn("stop_loss_price=", call_block)


class TestLearningLoopWiring(unittest.TestCase):
    """Tests 6-8: TradeLearningLoop connected to engine."""

    def test_06_import_present(self):
        """TradeLearningLoop is imported in auto_trading_engine."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        self.assertIn("from src.ml.trade_learner import TradeLearningLoop", src)
        self.assertIn("TradeOutcomeRecord", src)

    def test_07_init_creates_learning_loop(self):
        """AutoTradingEngine.__init__ creates self.learning_loop."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        self.assertIn("self.learning_loop = TradeLearningLoop()", src)

    def test_08_record_learning_outcome_method(self):
        """_record_learning_outcome method exists and creates TradeOutcomeRecord."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        self.assertIn("def _record_learning_outcome(self", src)
        self.assertIn("TradeOutcomeRecord(", src)
        self.assertIn("self.learning_loop.record_outcome(record)", src)


class TestUpgradedMonitoring(unittest.TestCase):
    """Tests 9-11: _monitor_positions uses PositionManager."""

    def test_09_uses_update_all_positions(self):
        """_monitor_positions calls self.position_mgr.update_all_positions."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        monitor_start = src.find("async def _monitor_positions(self)")
        self.assertGreater(monitor_start, 0)
        monitor_block = src[monitor_start:monitor_start + 2000]
        self.assertIn("self.position_mgr.update_all_positions(", monitor_block)

    def test_10_no_hardcoded_stop(self):
        """_monitor_positions no longer has hardcoded -0.03 stop."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        monitor_start = src.find("async def _monitor_positions(self)")
        monitor_end = src.find("\n    async def ", monitor_start + 1)
        if monitor_end == -1:
            monitor_end = src.find("\n    def ", monitor_start + 1)
        monitor_block = src[monitor_start:monitor_end]
        self.assertNotIn("-0.03", monitor_block,
                         "Hardcoded -3% stop should be replaced by PositionManager logic")

    def test_11_feeds_learning_loop(self):
        """_monitor_positions calls _record_learning_outcome on close."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        monitor_start = src.find("async def _monitor_positions(self)")
        # Find the next top-level method after _monitor_positions
        next_method = src.find("\n    async def ", monitor_start + 10)
        if next_method == -1:
            next_method = src.find("\n    def ", monitor_start + 10)
        monitor_block = src[monitor_start:next_method] if next_method > 0 else src[monitor_start:]
        self.assertIn("_record_learning_outcome", monitor_block)


class TestAPIEndpoints(unittest.TestCase):
    """Tests 12-14: New API endpoints exist."""

    def test_12_regime_endpoint(self):
        """/api/regime endpoint exists in main.py."""
        src = (ROOT / "src/api/main.py").read_text()
        self.assertIn('"/api/regime"', src)
        self.assertIn("get_regime_state", src)

    def test_13_recommendations_endpoint(self):
        """/api/recommendations endpoint exists."""
        src = (ROOT / "src/api/main.py").read_text()
        self.assertIn('"/api/recommendations"', src)
        self.assertIn("get_recommendations", src)

    def test_14_leaderboard_endpoint(self):
        """/api/leaderboard endpoint exists."""
        src = (ROOT / "src/api/main.py").read_text()
        self.assertIn('"/api/leaderboard"', src)
        self.assertIn("get_strategy_leaderboard", src)


class TestStructuredErrorUsage(unittest.TestCase):
    """Test 15: Structured errors used in engine."""

    def test_15_error_imports_in_engine(self):
        """auto_trading_engine imports BrokerError and DataError."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        self.assertIn("from src.core.errors import", src)
        self.assertIn("BrokerError", src)
        self.assertIn("DataError", src)

    def test_16_execute_signal_catches_broker_error(self):
        """_execute_signal has explicit BrokerError catch."""
        src = (ROOT / "src/engines/auto_trading_engine.py").read_text()
        exec_start = src.find("async def _execute_signal(")
        exec_end = src.find("\n    async def ", exec_start + 1)
        if exec_end == -1:
            exec_end = src.find("\n    def ", exec_start + 1)
        block = src[exec_start:exec_end]
        self.assertIn("except BrokerError", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
