"""
Sprint 9 Tests — BrokerError in Brokers, Discord Commands, Smoke Test, Cleanup

Tests:
1-4:  BrokerError in all concrete brokers
5-7:  Discord decision-layer commands
8-10: Asyncio smoke test (dry-run engine)
11-12: Patch file cleanup + .gitignore
13-15: Full pipeline integration checks
"""
import asyncio
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

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
    "discord", "discord.ext", "discord.ext.commands",
    "discord.ext.tasks",
    "aiohttp",
]:
    if stub not in sys.modules:
        sys.modules[stub] = MagicMock()

# Stub database before loading core (avoids asyncpg/tenacity)
import types as _types
_db_stub = _types.ModuleType("src.core.database")
_db_stub.get_session = MagicMock()
_db_stub.get_read_session = MagicMock()
_db_stub.check_database_health = MagicMock()
_db_stub.Base = MagicMock()
sys.modules["src.core.database"] = _db_stub

_load("src.core.config", "src/core/config.py")
_load("src.core.models", "src/core/models.py")
_load("src.core.errors", "src/core/errors.py")

# Stub trade_repo so engine import succeeds
_repo_stub = _types.ModuleType("src.core.trade_repo")
_repo_stub.TradeOutcomeRepository = MagicMock
sys.modules["src.core.trade_repo"] = _repo_stub


class TestBrokerErrorInConcreteBrokers(unittest.TestCase):
    """Tests 1-4: BrokerError present in all broker implementations."""

    def _check_broker(self, path, cls_name):
        src = (ROOT / path).read_text()
        self.assertIn(
            "BrokerError", src,
            f"{cls_name} missing BrokerError",
        )

    def test_01_futu_has_broker_error(self):
        self._check_broker("src/brokers/futu_broker.py", "FutuBroker")

    def test_02_ib_has_broker_error(self):
        self._check_broker("src/brokers/ib_broker.py", "IBBroker")

    def test_03_mt5_has_broker_error(self):
        self._check_broker("src/brokers/mt5_broker.py", "MetaTraderBroker")

    def test_04_paper_has_broker_error(self):
        self._check_broker("src/brokers/paper_broker.py", "PaperBroker")


class TestDiscordDecisionCommands(unittest.TestCase):
    """Tests 5-7: New Discord commands for decision layer."""

    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/discord_bot.py").read_text()

    def test_05_regime_command(self):
        """/regime command exists."""
        self.assertIn('name="regime"', self.src)
        self.assertIn("regime_cmd", self.src)

    def test_06_leaderboard_command(self):
        """/leaderboard command exists."""
        self.assertIn('name="leaderboard"', self.src)
        self.assertIn("leaderboard_cmd", self.src)

    def test_07_recommendations_command(self):
        """/recommendations command exists."""
        self.assertIn('name="recommendations"', self.src)
        self.assertIn("recommendations_cmd", self.src)


class TestAsyncSmokeTest(unittest.TestCase):
    """Tests 8-10: Async smoke test for AutoTradingEngine."""

    def test_08_engine_instantiates(self):
        """AutoTradingEngine can be instantiated in dry-run mode."""
        # Mock all external deps
        for m in [
            "src.engines.regime_router",
            "src.engines.opportunity_ensembler",
            "src.engines.context_assembler",
            "src.engines.strategy_leaderboard",
            "src.algo.position_manager",
            "src.ml.trade_learner",
            "src.engines.insight_engine",
        ]:
            if m not in sys.modules:
                sys.modules[m] = MagicMock()

        engine_mod = _load(
            "src.engines.auto_trading_engine",
            "src/engines/auto_trading_engine.py",
        )
        engine = engine_mod.AutoTradingEngine(dry_run=True)
        self.assertTrue(engine.dry_run)
        self.assertEqual(engine._cycle_count, 0)

    def test_09_engine_has_all_components(self):
        """Engine has all Sprint 3-8 components."""
        for m in [
            "src.engines.regime_router",
            "src.engines.opportunity_ensembler",
            "src.engines.context_assembler",
            "src.engines.strategy_leaderboard",
            "src.algo.position_manager",
            "src.ml.trade_learner",
            "src.engines.insight_engine",
        ]:
            if m not in sys.modules:
                sys.modules[m] = MagicMock()

        engine_mod = _load(
            "src.engines.auto_trading_engine",
            "src/engines/auto_trading_engine.py",
        )
        engine = engine_mod.AutoTradingEngine(dry_run=True)

        self.assertTrue(hasattr(engine, "regime_router"))
        self.assertTrue(hasattr(engine, "ensembler"))
        self.assertTrue(hasattr(engine, "context_assembler"))
        self.assertTrue(hasattr(engine, "leaderboard"))
        self.assertTrue(hasattr(engine, "position_mgr"))
        self.assertTrue(hasattr(engine, "learning_loop"))
        self.assertTrue(hasattr(engine, "circuit_breaker"))
        self.assertTrue(hasattr(engine, "position_monitor"))

    def test_10_get_cached_state_returns_dict(self):
        """get_cached_state returns dict with expected keys."""
        for m in [
            "src.engines.regime_router",
            "src.engines.opportunity_ensembler",
            "src.engines.context_assembler",
            "src.engines.strategy_leaderboard",
            "src.algo.position_manager",
            "src.ml.trade_learner",
            "src.engines.insight_engine",
        ]:
            if m not in sys.modules:
                sys.modules[m] = MagicMock()

        engine_mod = _load(
            "src.engines.auto_trading_engine",
            "src/engines/auto_trading_engine.py",
        )
        engine = engine_mod.AutoTradingEngine(dry_run=True)
        state = engine.get_cached_state()

        self.assertIsInstance(state, dict)
        for key in [
            "regime", "recommendations",
            "leaderboard", "cycle_count",
        ]:
            self.assertIn(key, state)


class TestCleanup(unittest.TestCase):
    """Tests 11-12: Patch file cleanup."""

    def test_11_gitignore_has_patch_pattern(self):
        """.gitignore includes _sprint*_patch.py."""
        gitignore = (ROOT / ".gitignore").read_text()
        self.assertIn("_sprint*_patch.py", gitignore)

    def test_12_old_patches_removed(self):
        """Old sprint patch files (5-8) should be removed."""
        import glob
        patches = glob.glob(str(ROOT / "_sprint[5678]_patch.py"))
        self.assertEqual(
            len(patches), 0,
            f"Old patch files should be cleaned up: {patches}",
        )


class TestPipelineIntegration(unittest.TestCase):
    """Tests 13-15: Full pipeline structural checks."""

    @classmethod
    def setUpClass(cls):
        cls.engine_src = (
            ROOT / "src/engines/auto_trading_engine.py"
        ).read_text()

    def test_13_no_duplicate_broker_init(self):
        """BrokerManager() only appears inside _get_broker() singleton."""
        # BrokerManager() should appear exactly once: inside _get_broker
        count = self.engine_src.count("BrokerManager()")
        self.assertLessEqual(
            count, 1,
            f"BrokerManager() appears {count} times; "
            "should only be in _get_broker() singleton",
        )
        # Verify none in hot paths
        for method in ["_execute_signal", "_monitor_positions",
                       "_get_equity", "_count_positions"]:
            idx = self.engine_src.find(f"def {method}(")
            if idx < 0:
                continue
            nxt = self.engine_src.find("\n    async def ", idx + 10)
            if nxt < 0:
                nxt = self.engine_src.find("\n    def ", idx + 10)
            block = self.engine_src[idx:nxt] if nxt > 0 else self.engine_src[idx:]
            self.assertNotIn(
                "BrokerManager()", block,
                f"{method} should use _get_broker() not BrokerManager()",
            )

    def test_14_complete_import_chain(self):
        """Engine imports all decision-layer components."""
        for imp in [
            "RegimeRouter",
            "OpportunityEnsembler",
            "ContextAssembler",
            "StrategyLeaderboard",
            "PositionManager",
            "TradeLearningLoop",
            "BrokerError",
            "DataError",
            "EdgeCalculator",
        ]:
            self.assertIn(imp, self.engine_src, f"Missing import: {imp}")

    def test_15_all_phases_in_run_cycle(self):
        """_run_cycle contains all pipeline phases."""
        cycle_start = self.engine_src.find("async def _run_cycle")
        # Find end of _run_cycle (next top-level method)
        next_def = self.engine_src.find("\n    def ", cycle_start + 10)
        if next_def < 0:
            next_def = len(self.engine_src)
        cycle_block = self.engine_src[cycle_start:next_def]
        phases = [
            "context_assembler",
            "regime_router",
            "_generate_signals",
            "_validate_signals",
            "rank_opportunities",
            "predict_signal_quality",
            "_execute_recommendation",
            "_monitor_positions",
            "_maybe_run_eod",
        ]
        for phase in phases:
            self.assertIn(
                phase, cycle_block,
                f"Missing pipeline phase: {phase}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
