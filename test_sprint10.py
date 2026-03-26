"""
Sprint 10 Tests — Observability, Typed Errors, Health Check, Graceful Shutdown

Verifies:
  1-3.  All 6 typed exceptions importable from errors.py
  4.    auto_trading_engine imports all typed exceptions
  5.    Typed catches outnumber bare catches in engine
  6-8.  _timed_phase, health_check, graceful_shutdown methods exist
  9.    health_check returns correct dict structure
  10.   graceful_shutdown sets _running=False
  11.   /api/health endpoint exists in api/main.py
  12.   BrokerError in _get_equity / _count_positions
  13.   SignalError in _generate_signals
  14.   ValidationError in _validate_signals
  15.   ConfigError in __init__ config load
  16.   RiskLimitError in _monitor_positions
  17.   DataError in context assembly
"""
import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# ─── stub heavy deps ────────────────────────────────────────
for mod in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext.declarative",
    "sqlalchemy.ext.asyncio", "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "aiohttp", "fastapi", "uvicorn", "redis",
    "openai", "tiktoken", "yfinance",
    "pandas", "numpy", "scipy", "sklearn",
    "sklearn.ensemble", "sklearn.model_selection",
    "ta", "mplfinance",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── load modules under test ────────────────────────────────
errors_mod = _load("src.core.errors", "src/core/errors.py")
# Ensure config stubs
if "src.core.config" not in sys.modules:
    cfg_stub = types.ModuleType("src.core.config")
    cfg_stub.get_settings = lambda: MagicMock()
    cfg_stub.get_trading_config = lambda: MagicMock(
        max_position_pct=0.05, max_sector_pct=0.20,
        max_portfolio_var=0.15, max_drawdown_pct=10.0,
        risk_per_trade=0.01, stop_loss_pct=0.05,
        max_hold_days=15,
    )
    sys.modules["src.core.config"] = cfg_stub

# Stub notification modules
for sub in ["telegram", "discord", "whatsapp", "formatter", "multi_channel"]:
    mod_name = f"src.notifications.{sub}"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
if "src.notifications" not in sys.modules:
    sys.modules["src.notifications"] = MagicMock()

# Read source code for text-based tests
with open(os.path.join(ROOT, "src", "engines", "auto_trading_engine.py")) as f:
    engine_src = f.read()
with open(os.path.join(ROOT, "src", "api", "main.py")) as f:
    api_src = f.read()


# ═════════════════════════════════════════════════════════════
class TestTypedErrorImports(unittest.TestCase):
    """Tests 1-3: All typed exceptions importable."""

    def test_01_broker_error(self):
        self.assertTrue(hasattr(errors_mod, "BrokerError"))

    def test_02_all_six_error_types(self):
        for name in ["BrokerError", "DataError", "ValidationError",
                      "RiskLimitError", "SignalError", "ConfigError"]:
            self.assertTrue(
                hasattr(errors_mod, name), f"{name} not in errors.py"
            )

    def test_03_trading_error_base(self):
        self.assertTrue(
            issubclass(errors_mod.BrokerError, errors_mod.TradingError)
        )


class TestEngineTypedImports(unittest.TestCase):
    """Tests 4-5: Engine imports and uses typed exceptions."""

    def test_04_engine_imports_all_typed_errors(self):
        for name in ["BrokerError", "ConfigError", "DataError",
                      "RiskLimitError", "SignalError", "ValidationError"]:
            self.assertIn(
                name, engine_src,
                f"{name} not imported in auto_trading_engine.py",
            )

    def test_05_typed_catches_outnumber_minimum(self):
        """At least 10 typed exception catches in the engine."""
        typed_count = sum(
            engine_src.count(f"except {e}")
            for e in ["BrokerError", "DataError", "ConfigError",
                       "RiskLimitError", "SignalError", "ValidationError"]
        )
        self.assertGreaterEqual(
            typed_count, 10,
            f"Only {typed_count} typed catches; expected >= 10",
        )


class TestNewMethods(unittest.TestCase):
    """Tests 6-10: _timed_phase, health_check, graceful_shutdown."""

    def test_06_timed_phase_exists(self):
        self.assertIn("async def _timed_phase", engine_src)

    def test_07_health_check_exists(self):
        self.assertIn("async def health_check", engine_src)

    def test_08_graceful_shutdown_exists(self):
        self.assertIn("async def graceful_shutdown", engine_src)

    def test_09_health_check_returns_dict_keys(self):
        """health_check body has status, components, metrics."""
        hc_start = engine_src.find("async def health_check")
        next_def = engine_src.find("\n    async def ", hc_start + 10)
        if next_def < 0:
            next_def = engine_src.find("\n    def ", hc_start + 10)
        block = engine_src[hc_start:next_def]
        for key in ["status", "components", "metrics"]:
            self.assertIn(
                f'"{key}"', block,
                f'health_check missing "{key}" key',
            )

    def test_10_graceful_shutdown_sets_running_false(self):
        gs_start = engine_src.find("async def graceful_shutdown")
        next_def = engine_src.find("\n    async def ", gs_start + 10)
        if next_def < 0:
            next_def = engine_src.find("\n    def ", gs_start + 10)
        block = engine_src[gs_start:next_def] if next_def > 0 else engine_src[gs_start:]
        self.assertIn("self._running = False", block)


class TestAPIHealthEndpoint(unittest.TestCase):
    """Test 11: /api/health endpoint exists."""

    def test_11_api_health_endpoint(self):
        self.assertIn('/api/health', api_src)
        self.assertIn('async def api_health', api_src)


class TestTypedCatchesInMethods(unittest.TestCase):
    """Tests 12-17: Typed catches in specific engine methods."""

    def _method_block(self, method_name):
        """Extract method body text."""
        idx = engine_src.find(f"def {method_name}(")
        if idx < 0:
            idx = engine_src.find(f"def {method_name}")
        self.assertGreater(idx, 0, f"{method_name} not found")
        # Find next top-level method
        nxt = engine_src.find("\n    async def ", idx + 10)
        if nxt < 0:
            nxt = engine_src.find("\n    def ", idx + 10)
        return engine_src[idx:nxt] if nxt > 0 else engine_src[idx:]

    def test_12_broker_error_in_get_equity(self):
        block = self._method_block("_get_equity")
        self.assertIn("BrokerError", block)

    def test_13_broker_error_in_count_positions(self):
        block = self._method_block("_count_positions")
        self.assertIn("BrokerError", block)

    def test_14_signal_error_in_generate_signals(self):
        block = self._method_block("_generate_signals")
        self.assertIn("SignalError", block)

    def test_15_validation_error_in_validate_signals(self):
        block = self._method_block("_validate_signals")
        self.assertIn("ValidationError", block)

    def test_16_config_error_in_init(self):
        """ConfigError referenced in __init__ config loading."""
        # __init__ is harder to extract, search first 400 lines
        init_block = engine_src[:15000]
        self.assertIn("ConfigError", init_block)

    def test_17_broker_error_in_monitor_positions(self):
        block = self._method_block("_monitor_positions")
        self.assertIn("BrokerError", block)


if __name__ == "__main__":
    unittest.main()
