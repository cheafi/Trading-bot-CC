"""
Sprint 11 Tests — DB Persistence, _timed_phase Wiring, Retry, TradeOutcomeRepository

Verifies:
  1-3.  SQL migration file exists with expected tables
  4-5.  TradeOutcomeRepository class structure
  6.    TradeOutcomeRepository has all CRUD methods
  7.    Engine imports TradeOutcomeRepository
  8.    Engine initializes trade_repo in __init__
  9-12. _timed_phase wired into 4 pipeline phases
  13.   _with_retry method exists
  14.   Regime snapshot persistence in _run_cycle
  15.   Trade outcome DB persistence in _record_learning_outcome
  16.   SQL migration has proper indexes
  17.   SQL migration has materialized view
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
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── load modules under test ────────────────────────────────
# Stub config
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

# Stub database
if "src.core.database" not in sys.modules:
    db_stub = types.ModuleType("src.core.database")
    db_stub.get_session = MagicMock()
    db_stub.get_read_session = MagicMock()
    sys.modules["src.core.database"] = db_stub

# Stub notification modules
for sub in ["telegram", "discord", "whatsapp",
            "formatter", "multi_channel"]:
    mod_name = f"src.notifications.{sub}"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
if "src.notifications" not in sys.modules:
    sys.modules["src.notifications"] = MagicMock()

# Read source files for text-based tests
with open(os.path.join(ROOT, "src", "engines",
          "auto_trading_engine.py")) as f:
    engine_src = f.read()

sql_path = os.path.join(ROOT, "init", "postgres",
                        "03_decision_layer.sql")
with open(sql_path) as f:
    sql_src = f.read()

repo_path = os.path.join(ROOT, "src", "core", "trade_repo.py")
with open(repo_path) as f:
    repo_src = f.read()


# ═════════════════════════════════════════════════════════════
class TestSQLMigration(unittest.TestCase):
    """Tests 1-3, 16-17: SQL migration file."""

    def test_01_migration_file_exists(self):
        self.assertTrue(os.path.exists(sql_path))

    def test_02_trade_outcomes_table(self):
        self.assertIn(
            "analytics.trade_outcomes", sql_src,
        )

    def test_03_strategy_leaderboard_table(self):
        self.assertIn(
            "analytics.strategy_leaderboard", sql_src,
        )

    def test_16_indexes_defined(self):
        self.assertIn("idx_outcomes_ticker", sql_src)
        self.assertIn("idx_outcomes_strategy", sql_src)
        self.assertIn("idx_leaderboard_date", sql_src)
        self.assertIn("idx_regime_time", sql_src)
        self.assertIn("idx_health_time", sql_src)

    def test_17_daily_view(self):
        self.assertIn(
            "v_daily_strategy_performance", sql_src,
        )


class TestTradeOutcomeRepository(unittest.TestCase):
    """Tests 4-6: Repository class structure."""

    def test_04_repo_file_exists(self):
        self.assertTrue(os.path.exists(repo_path))

    def test_05_repo_class_defined(self):
        self.assertIn(
            "class TradeOutcomeRepository", repo_src,
        )

    def test_06_repo_has_crud_methods(self):
        for method in [
            "save_outcome",
            "save_outcomes_batch",
            "save_leaderboard_snapshot",
            "save_regime_snapshot",
            "save_health_snapshot",
            "get_recent_outcomes",
            "get_strategy_stats",
        ]:
            self.assertIn(
                f"def {method}", repo_src,
                f"{method} not in TradeOutcomeRepository",
            )


class TestEngineRepoIntegration(unittest.TestCase):
    """Tests 7-8: Engine imports and inits the repo."""

    def test_07_engine_imports_repo(self):
        self.assertIn("TradeOutcomeRepository", engine_src)

    def test_08_engine_inits_trade_repo(self):
        self.assertIn("self.trade_repo", engine_src)
        # Verify it appears in __init__ region (first 500 lines)
        init_block = engine_src[:20000]
        self.assertIn(
            "self.trade_repo = TradeOutcomeRepository()",
            init_block,
        )


class TestTimedPhaseWiring(unittest.TestCase):
    """Tests 9-12: _timed_phase used in _run_cycle."""

    def _run_cycle_block(self):
        start = engine_src.find("async def _run_cycle")
        nxt = engine_src.find(
            "\n    def _get_active_markets", start + 10
        )
        return engine_src[start:nxt] if nxt > 0 else ""

    def test_09_timed_context_assembly(self):
        block = self._run_cycle_block()
        self.assertIn(
            '_timed_phase("context_assembly")', block,
        )

    def test_10_timed_signal_generation(self):
        block = self._run_cycle_block()
        self.assertIn(
            '_timed_phase("signal_generation")', block,
        )

    def test_11_timed_signal_validation(self):
        block = self._run_cycle_block()
        self.assertIn(
            '_timed_phase("signal_validation")', block,
        )

    def test_12_timed_position_monitoring(self):
        block = self._run_cycle_block()
        self.assertIn(
            '_timed_phase("position_monitoring")', block,
        )


class TestRetryAndPersistence(unittest.TestCase):
    """Tests 13-15: _with_retry + DB persistence."""

    def test_13_with_retry_exists(self):
        self.assertIn("async def _with_retry", engine_src)

    def test_14_regime_snapshot_persistence(self):
        self.assertIn("save_regime_snapshot", engine_src)

    def test_15_outcome_db_persistence(self):
        self.assertIn("save_outcome", engine_src)
        # Verify it's in _record_learning_outcome
        rec_start = engine_src.find(
            "def _record_learning_outcome"
        )
        rec_end = engine_src.find(
            "\n    async def _maybe_run_eod", rec_start + 10
        )
        if rec_end < 0:
            rec_end = engine_src.find(
                "\n    async def ", rec_start + 40
            )
        block = engine_src[rec_start:rec_end]
        self.assertIn(
            "save_outcome", block,
            "save_outcome not in _record_learning_outcome",
        )


# Additional SQL structure tests
class TestSQLAdditionalTables(unittest.TestCase):
    """Extra coverage for SQL migration."""

    def test_18_regime_snapshots_table(self):
        self.assertIn(
            "analytics.regime_snapshots", sql_src,
        )

    def test_19_engine_health_log_table(self):
        self.assertIn(
            "system.engine_health_log", sql_src,
        )


if __name__ == "__main__":
    unittest.main()
