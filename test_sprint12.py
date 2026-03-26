"""
Sprint 12 Tests — Engine Entrypoint, Boot Sequence, Structured Logging,
                   Discord Cache Wiring

Verifies:
  1-3.  logging_config module: JSONFormatter, ConsoleFormatter, setup_logging
  4-5.  Correlation ID: set/get round-trip
  6.    engines/main.py exists with main() and validate_config()
  7.    engines/main.py imports setup_logging
  8-9.  _boot() method exists and validates components
  10.   Correlation ID set in _run_cycle
  11.   /recommendations wired to cached_state
  12-14. JSONFormatter output structure
  15.   Docker CMD target file exists (engines/main.py)
  16-17. Boot checks all critical components
"""
import importlib.util
import json
import logging
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
    "ta", "mplfinance", "tenacity",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── load logging_config (no heavy deps) ────────────────────
logging_mod = _load(
    "src.core.logging_config",
    "src/core/logging_config.py",
)

# Read source code for text-based tests
with open(os.path.join(ROOT, "src", "engines",
          "auto_trading_engine.py")) as f:
    engine_src = f.read()

with open(os.path.join(ROOT, "src", "engines", "main.py")) as f:
    main_src = f.read()

with open(os.path.join(ROOT, "src", "discord_bot.py")) as f:
    discord_src = f.read()


# ═════════════════════════════════════════════════════════════
class TestLoggingConfig(unittest.TestCase):
    """Tests 1-3: Structured logging module."""

    def test_01_json_formatter_exists(self):
        self.assertTrue(hasattr(logging_mod, "JSONFormatter"))

    def test_02_console_formatter_exists(self):
        self.assertTrue(hasattr(logging_mod, "ConsoleFormatter"))

    def test_03_setup_logging_callable(self):
        self.assertTrue(callable(logging_mod.setup_logging))


class TestCorrelationID(unittest.TestCase):
    """Tests 4-5: Correlation ID context var."""

    def test_04_set_and_get_roundtrip(self):
        cid = logging_mod.set_correlation_id("test-abc")
        self.assertEqual(cid, "test-abc")
        self.assertEqual(logging_mod.get_correlation_id(), "test-abc")

    def test_05_auto_generate_id(self):
        cid = logging_mod.set_correlation_id()
        self.assertTrue(len(cid) > 0)
        self.assertEqual(logging_mod.get_correlation_id(), cid)


class TestEngineMain(unittest.TestCase):
    """Tests 6-7: Engine entrypoint."""

    def test_06_main_has_entrypoint(self):
        self.assertIn("def main()", main_src)
        self.assertIn("def validate_config()", main_src)

    def test_07_main_imports_setup_logging(self):
        self.assertIn("setup_logging", main_src)

    def test_15_docker_cmd_target_exists(self):
        path = os.path.join(ROOT, "src", "engines", "main.py")
        self.assertTrue(os.path.exists(path))


class TestBootMethod(unittest.TestCase):
    """Tests 8-9, 16-17: _boot() method in engine."""

    def test_08_boot_method_exists(self):
        self.assertIn("async def _boot(self)", engine_src)

    def test_09_boot_checks_components(self):
        boot_start = engine_src.find("async def _boot(self)")
        nxt = engine_src.find(
            "\n    async def run(self):", boot_start + 10
        )
        block = engine_src[boot_start:nxt]
        for comp in ["regime_router", "ensembler",
                      "context_assembler", "leaderboard",
                      "position_mgr", "learning_loop"]:
            self.assertIn(
                comp, block,
                f"_boot missing check for {comp}",
            )

    def test_16_boot_checks_broker(self):
        boot_start = engine_src.find("async def _boot(self)")
        nxt = engine_src.find(
            "\n    async def run(self):", boot_start + 10
        )
        block = engine_src[boot_start:nxt]
        self.assertIn("_get_broker", block)

    def test_17_boot_checks_database(self):
        boot_start = engine_src.find("async def _boot(self)")
        nxt = engine_src.find(
            "\n    async def run(self):", boot_start + 10
        )
        block = engine_src[boot_start:nxt]
        self.assertIn("check_database_health", block)


class TestCorrelationInCycle(unittest.TestCase):
    """Test 10: Correlation ID set per cycle."""

    def test_10_correlation_in_run_cycle(self):
        cycle_start = engine_src.find("async def _run_cycle")
        cycle_block = engine_src[cycle_start:cycle_start + 500]
        self.assertIn("set_correlation_id", cycle_block)


class TestDiscordRecsWiring(unittest.TestCase):
    """Test 11: /recommendations uses cached state."""

    def test_11_recommendations_uses_cache(self):
        # Find recommendations_cmd and look for get_cached_state
        recs_idx = discord_src.find("recommendations_cmd")
        self.assertGreater(recs_idx, 0)
        recs_block = discord_src[recs_idx:recs_idx + 2000]
        self.assertIn(
            "get_cached_state", recs_block,
            "/recommendations not wired to engine cache",
        )


class TestJSONFormatterOutput(unittest.TestCase):
    """Tests 12-14: JSONFormatter produces valid JSON."""

    def setUp(self):
        self.formatter = logging_mod.JSONFormatter()
        self.logger = logging.getLogger("test_json")
        self.logger.setLevel(logging.DEBUG)

    def test_12_valid_json_output(self):
        record = self.logger.makeRecord(
            "test", logging.INFO, "mod", 1,
            "hello world", (), None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        self.assertEqual(parsed["message"], "hello world")

    def test_13_json_has_required_fields(self):
        record = self.logger.makeRecord(
            "test", logging.WARNING, "mod", 42,
            "warning msg", (), None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        for key in ["ts", "level", "logger", "message", "line"]:
            self.assertIn(key, parsed, f"Missing key: {key}")
        self.assertEqual(parsed["level"], "WARNING")

    def test_14_json_includes_correlation_id(self):
        logging_mod.set_correlation_id("test-corr-123")
        record = self.logger.makeRecord(
            "test", logging.INFO, "mod", 1,
            "correlated", (), None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        self.assertEqual(
            parsed.get("correlation_id"), "test-corr-123",
        )


if __name__ == "__main__":
    unittest.main()
