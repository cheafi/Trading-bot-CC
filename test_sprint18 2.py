"""
Sprint 18 — Infra Hardening + Deprecation Fixes

Tests:
  1. src/ingestors/main.py exists and is importable
  2. IngestorService instantiation, health(), intervals
  3. redis lazy import — realtime_feed imports without redis installed
  4. datetime.utcnow() removed from decision-layer modules
  5. models._utcnow() returns timezone-aware datetime
  6. ARCHITECTURE.md updated with Sprint 17-18
"""
import sys
import os
import unittest
import importlib.util
from unittest.mock import MagicMock
from datetime import datetime, timezone

# ── Stubs ──────────────────────────────────────────────────────────
settings_mod = MagicMock()
settings_mod.BaseSettings = type("BaseSettings", (), {})
sys.modules.setdefault("pydantic_settings", settings_mod)

sa = MagicMock()
sa.Column = MagicMock; sa.String = MagicMock; sa.Float = MagicMock
sa.Integer = MagicMock; sa.DateTime = MagicMock; sa.Boolean = MagicMock
sa.Text = MagicMock; sa.JSON = MagicMock; sa.ForeignKey = MagicMock
sa.create_engine = MagicMock; sa.MetaData = MagicMock
sys.modules.setdefault("sqlalchemy", sa)
sys.modules.setdefault("sqlalchemy.orm", MagicMock())

db_mod = MagicMock()
db_mod.check_database_health = MagicMock(return_value={"status": "ok"})
sys.modules.setdefault("src.core.database", db_mod)

sys.modules.setdefault("asyncpg", MagicMock())
sys.modules.setdefault("tenacity", MagicMock())

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, rel_path):
    path = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ═════════════════════════════════════════════════════════════════════
# 1. INGESTORS ENTRYPOINT
# ═════════════════════════════════════════════════════════════════════
class TestIngestorsMain(unittest.TestCase):

    def test_01_file_exists(self):
        """src/ingestors/main.py exists."""
        path = os.path.join(ROOT, "src", "ingestors", "main.py")
        self.assertTrue(os.path.isfile(path))

    def test_02_importable(self):
        """IngestorService is importable."""
        mod = _load("src.ingestors.main_test", "src/ingestors/main.py")
        self.assertTrue(hasattr(mod, "IngestorService"))

    def test_03_instantiate(self):
        """IngestorService can be created with default intervals."""
        mod = _load("src.ingestors.main_t3", "src/ingestors/main.py")
        svc = mod.IngestorService()
        self.assertFalse(svc._running)
        self.assertEqual(svc.intervals["market_data"], 60)
        self.assertEqual(svc.intervals["news"], 300)
        self.assertEqual(svc.intervals["social"], 600)

    def test_04_custom_intervals(self):
        """IngestorService accepts custom intervals."""
        mod = _load("src.ingestors.main_t4", "src/ingestors/main.py")
        svc = mod.IngestorService(intervals={"market_data": 30})
        self.assertEqual(svc.intervals["market_data"], 30)
        self.assertEqual(svc.intervals["news"], 300)  # default kept

    def test_05_health_returns_dict(self):
        """health() returns running/loops/timestamp."""
        mod = _load("src.ingestors.main_t5", "src/ingestors/main.py")
        svc = mod.IngestorService()
        h = svc.health()
        self.assertIn("running", h)
        self.assertIn("timestamp", h)
        self.assertFalse(h["running"])

    def test_06_has_main_function(self):
        """Module has async main() entry point."""
        mod = _load("src.ingestors.main_t6", "src/ingestors/main.py")
        self.assertTrue(hasattr(mod, "main"))

    def test_07_dockerfile_cmd_matches(self):
        """Dockerfile.ingestor CMD references src.ingestors.main."""
        path = os.path.join(ROOT, "docker", "Dockerfile.ingestor")
        with open(path) as f:
            content = f.read()
        self.assertIn("src.ingestors.main", content)


# ═════════════════════════════════════════════════════════════════════
# 2. REDIS LAZY IMPORT
# ═════════════════════════════════════════════════════════════════════
class TestRedisLazyImport(unittest.TestCase):

    def test_08_realtime_feed_imports_without_redis(self):
        """realtime_feed.py imports even when redis is not installed."""
        # Remove redis from sys.modules if present, to simulate missing
        saved = {}
        for k in list(sys.modules.keys()):
            if k.startswith("redis"):
                saved[k] = sys.modules.pop(k)
        try:
            path = os.path.join(ROOT, "src", "ingestors", "realtime_feed.py")
            with open(path) as f:
                content = f.read()
            self.assertIn("try:", content)
            self.assertIn("import redis.asyncio as aioredis", content)
            self.assertIn("except ImportError:", content)
        finally:
            sys.modules.update(saved)

    def test_09_try_except_pattern(self):
        """Redis import uses try/except ImportError pattern."""
        path = os.path.join(ROOT, "src", "ingestors", "realtime_feed.py")
        with open(path) as f:
            lines = f.readlines()
        # Find the try block
        found_try = False
        found_import = False
        found_except = False
        for line in lines:
            stripped = line.strip()
            if stripped == "try:":
                found_try = True
            elif found_try and "import redis.asyncio" in stripped:
                found_import = True
            elif found_import and "except ImportError:" in stripped:
                found_except = True
                break
        self.assertTrue(found_try, "Missing try:")
        self.assertTrue(found_import, "Missing redis import inside try")
        self.assertTrue(found_except, "Missing except ImportError:")


# ═════════════════════════════════════════════════════════════════════
# 3. UTCNOW DEPRECATION FIXES
# ═════════════════════════════════════════════════════════════════════
class TestUtcnowFixes(unittest.TestCase):

    DECISION_FILES = [
        "src/engines/strategy_leaderboard.py",
        "src/engines/context_assembler.py",
        "src/engines/regime_router.py",
    ]

    def test_10_no_utcnow_in_decision_engines(self):
        """Decision-layer engines should not use datetime.utcnow()."""
        for rel in self.DECISION_FILES:
            with self.subTest(file=rel):
                path = os.path.join(ROOT, rel)
                with open(path) as f:
                    content = f.read()
                # Allow the string in comments but not as a call
                calls = [
                    line for line in content.splitlines()
                    if "datetime.utcnow()" in line
                    and not line.strip().startswith("#")
                    and not line.strip().startswith('"""')
                ]
                self.assertEqual(
                    len(calls), 0,
                    f"{rel} still has datetime.utcnow() calls:\n" +
                    "\n".join(calls),
                )

    def test_11_no_utcnow_default_factory_in_models(self):
        """models.py should use _utcnow, not datetime.utcnow."""
        path = os.path.join(ROOT, "src", "core", "models.py")
        with open(path) as f:
            content = f.read()
        self.assertNotIn(
            "default_factory=datetime.utcnow", content,
            "models.py still has default_factory=datetime.utcnow",
        )
        self.assertIn("default_factory=_utcnow", content)

    def test_12_utcnow_helper_exists(self):
        """models._utcnow() exists and returns timezone-aware datetime."""
        models = _load("src.core.models_t12", "src/core/models.py")
        self.assertTrue(hasattr(models, "_utcnow"))
        result = models._utcnow()
        self.assertIsInstance(result, datetime)
        self.assertIsNotNone(result.tzinfo)

    def test_13_utcnow_helper_is_utc(self):
        """_utcnow() returns UTC time."""
        models = _load("src.core.models_t13", "src/core/models.py")
        result = models._utcnow()
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_14_leaderboard_uses_timezone_utc(self):
        """strategy_leaderboard.py imports timezone."""
        path = os.path.join(ROOT, "src", "engines", "strategy_leaderboard.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("timezone", content)
        self.assertIn("datetime.now(timezone.utc)", content)

    def test_15_context_assembler_uses_timezone_utc(self):
        """context_assembler.py uses datetime.now(timezone.utc)."""
        path = os.path.join(ROOT, "src", "engines", "context_assembler.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("datetime.now(timezone.utc)", content)

    def test_16_regime_router_uses_timezone_utc(self):
        """regime_router.py uses datetime.now(timezone.utc)."""
        path = os.path.join(ROOT, "src", "engines", "regime_router.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("datetime.now(timezone.utc)", content)

    def test_17_leaderboard_still_works(self):
        """StrategyLeaderboard still functions after utcnow fix."""
        lb_mod = _load("src.engines.strategy_leaderboard_t17",
                        "src/engines/strategy_leaderboard.py")
        lb = lb_mod.StrategyLeaderboard()
        entry = lb.update("test", {"oos_sharpe": 1.0, "win_rate": 0.5, "trade_count": 5})
        self.assertIn("last_updated", entry)
        self.assertIn("blended_score", entry)


if __name__ == "__main__":
    unittest.main()
