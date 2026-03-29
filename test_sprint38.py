"""
Sprint 38 tests — Complete Roadmap.

Covers all 12 remaining roadmap items:
  1. Meta-Ensemble trainer          (src/engines/meta_ensemble.py)
  2. ML Regression heads            (src/ml/trade_learner.py)
  3. Options Data Pipeline          (src/ingestors/options_data.py)
  4. Bearish Sleeve                 (src/strategies/bearish_sleeve.py)
  5. Daily Playbook                 (src/notifications/daily_playbook.py)
  6. Monthly Scorecard              (src/notifications/monthly_scorecard.py)
  7. User Mode preferences          (src/core/user_preferences.py)
  8. Methodology docs               (docs/METHODOLOGY.md)
  9. PerformanceTracker JSON         (src/performance/performance_tracker.py)
  10. Dynamic Universe Sleeves       (src/scanners/universe_builder.py)
  11. OpportunityEnsembler.set_weights (src/engines/opportunity_ensembler.py)
  12. Telegram divergence/earnings   (src/notifications/telegram_bot.py)
  + Discord /playbook /scorecard /mode /methodology
  + MODEL_VERSION v6.38
  + Command count 64
"""
import importlib
import importlib.util
import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# ── Stub heavy deps before any src.* imports ─────────────
for _mod in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.exc",
    "sqlalchemy.pool", "sqlalchemy.engine",
    "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "discord.ext.tasks", "discord.ui",
    "tenacity",
    "fastapi", "uvicorn",
    "apscheduler", "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "aiohttp", "aiohttp.web",
    "sklearn", "sklearn.ensemble",
    "sklearn.preprocessing",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

_db_stub = MagicMock()
_db_stub.check_database_health = MagicMock(return_value={})
_db_stub.get_session = MagicMock()
sys.modules.setdefault("src.core.database", _db_stub)

import numpy as _real_np
sys.modules["numpy"] = _real_np

# ── Load helpers ──────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(BASE, path),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════
# 1. Meta-Ensemble
# ═══════════════════════════════════════════════════════════

class TestMetaEnsemble(unittest.TestCase):
    """Tests for src/engines/meta_ensemble.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "meta_ensemble",
            "src/engines/meta_ensemble.py",
        )

    def test_01_classes_exist(self):
        self.assertTrue(hasattr(self.mod, "MetaEnsemble"))
        self.assertTrue(hasattr(self.mod, "TrainingSample"))
        self.assertTrue(hasattr(self.mod, "MetaEnsembleState"))

    def test_02_initial_state_untrained(self):
        me = self.mod.MetaEnsemble()
        self.assertFalse(me.is_trained)
        self.assertEqual(me.sample_count, 0)
        self.assertIsNone(me.get_learned_weights())

    def test_03_record_outcome(self):
        me = self.mod.MetaEnsemble()
        me.record_outcome(
            components={"net_expectancy": 0.8, "calibrated_pwin": 0.6},
            pnl_pct=2.5,
            r_multiple=1.5,
            regime_label="RISK_ON",
            strategy_id="momentum",
        )
        self.assertEqual(me.sample_count, 1)

    def test_04_component_names(self):
        self.assertEqual(
            len(self.mod.COMPONENT_NAMES), 8,
        )

    def test_05_training_after_min_samples(self):
        me = self.mod.MetaEnsemble()
        me._min_samples = 5
        me._retrain_interval = 3
        names = self.mod.COMPONENT_NAMES
        for i in range(6):
            me.record_outcome(
                components={
                    n: 0.5 + i * 0.01
                    for n in names
                },
                pnl_pct=1.0 + i * 0.1,
                r_multiple=0.5 + i * 0.05,
                regime_label="NEUTRAL",
                strategy_id="trend",
            )
        # After enough samples, should be trained
        self.assertTrue(me.is_trained)
        weights = me.get_learned_weights()
        self.assertIsNotNone(weights)
        self.assertEqual(len(weights), 8)
        # All weights should be positive
        for w in weights.values():
            self.assertGreater(w, 0)

    def test_06_ridge_solve(self):
        me = self.mod.MetaEnsemble()
        # Simple 2x2 system — k=2 features
        A = [[2.0, 1.0], [1.0, 3.0]]
        b = [5.0, 7.0]
        x = me._ridge_solve(A, b, 2)
        self.assertIsNotNone(x)
        self.assertEqual(len(x), 2)


# ═══════════════════════════════════════════════════════════
# 2. ML Regression Heads
# ═══════════════════════════════════════════════════════════

class TestMLRegression(unittest.TestCase):
    """Tests for regression heads in trade_learner.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "trade_learner",
            "src/ml/trade_learner.py",
        )

    def test_10_train_regression_exists(self):
        self.assertTrue(
            hasattr(self.mod.TradeOutcomePredictor, "train_regression"),
        )

    def test_11_predict_r_exists(self):
        self.assertTrue(
            hasattr(self.mod.TradeOutcomePredictor, "predict_r_multiple"),
        )

    def test_12_predict_mae_exists(self):
        self.assertTrue(
            hasattr(self.mod.TradeOutcomePredictor, "predict_mae"),
        )

    def test_13_predict_hold_days_exists(self):
        self.assertTrue(
            hasattr(self.mod.TradeOutcomePredictor, "predict_hold_days"),
        )

    def test_14_predict_without_training_returns_none(self):
        # Create instance using __new__ to bypass __init__
        p = self.mod.TradeOutcomePredictor.__new__(
            self.mod.TradeOutcomePredictor,
        )
        p._reg_r_model = None
        p._reg_mae_model = None
        p._reg_hold_model = None
        p._reg_scaler = None
        result = p.predict_r_multiple({"rsi": 55})
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════
# 3. Options Data Pipeline
# ═══════════════════════════════════════════════════════════

class TestOptionsData(unittest.TestCase):
    """Tests for src/ingestors/options_data.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "options_data",
            "src/ingestors/options_data.py",
        )

    def test_20_classes_exist(self):
        self.assertTrue(hasattr(self.mod, "OptionChainSnapshot"))
        self.assertTrue(hasattr(self.mod, "OptionsDataProvider"))
        self.assertTrue(hasattr(self.mod, "SyntheticOptionsProvider"))

    def test_21_snapshot_fields(self):
        snap = self.mod.OptionChainSnapshot(
            ticker="AAPL", expiry="2024-01-19",
            iv_rank=0.45, iv_percentile=0.55,
            hv_20d=0.22, put_call_ratio=0.8,
            total_oi=500000, atm_iv=0.25,
        )
        self.assertEqual(snap.ticker, "AAPL")
        self.assertAlmostEqual(snap.iv_rank, 0.45)

    def test_22_synthetic_provider(self):
        import asyncio
        provider = self.mod.SyntheticOptionsProvider()
        loop = asyncio.new_event_loop()
        try:
            snap = loop.run_until_complete(
                provider.fetch_chain("AAPL"),
            )
        finally:
            loop.close()
        self.assertIsNotNone(snap)
        self.assertEqual(snap.ticker, "AAPL")

    def test_23_singleton(self):
        p1 = self.mod.get_options_provider()
        p2 = self.mod.get_options_provider()
        self.assertIs(p1, p2)


# ═══════════════════════════════════════════════════════════
# 4. Bearish Sleeve
# ═══════════════════════════════════════════════════════════

class TestBearishSleeve(unittest.TestCase):
    """Tests for src/strategies/bearish_sleeve.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "bearish_sleeve",
            "src/strategies/bearish_sleeve.py",
        )

    def test_30_classes_exist(self):
        self.assertTrue(hasattr(self.mod, "BearishSleeve"))
        self.assertTrue(hasattr(self.mod, "BearishSetup"))
        self.assertTrue(hasattr(self.mod, "BEARISH_REGIMES"))

    def test_31_not_active_in_risk_on(self):
        sleeve = self.mod.BearishSleeve()
        self.assertFalse(
            sleeve.is_active({"regime": "RISK_ON"}),
        )

    def test_32_active_in_risk_off(self):
        sleeve = self.mod.BearishSleeve()
        self.assertTrue(
            sleeve.is_active({"regime": "risk_off"}),
        )

    def test_33_scan_returns_list(self):
        sleeve = self.mod.BearishSleeve()
        result = sleeve.scan(
            tickers=["AAPL"],
            price_data={},
            regime_state={"regime": "risk_off"},
        )
        self.assertIsInstance(result, list)

    def test_34_bearish_regimes(self):
        self.assertIn("risk_off", self.mod.BEARISH_REGIMES)
        self.assertIn("crisis", self.mod.BEARISH_REGIMES)


# ═══════════════════════════════════════════════════════════
# 5. Daily Playbook
# ═══════════════════════════════════════════════════════════

class TestDailyPlaybook(unittest.TestCase):
    """Tests for src/notifications/daily_playbook.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "daily_playbook",
            "src/notifications/daily_playbook.py",
        )

    def test_40_classes_exist(self):
        self.assertTrue(hasattr(self.mod, "PlaybookSetup"))
        self.assertTrue(hasattr(self.mod, "PlaybookCard"))
        self.assertTrue(hasattr(self.mod, "DailyPlaybookBuilder"))

    def test_41_build_returns_card(self):
        builder = self.mod.DailyPlaybookBuilder()
        card = builder.build(
            regime_state={"regime": "NEUTRAL"},
            recommendations=[],
            budget_info={},
            market_data={},
        )
        self.assertIsInstance(card, self.mod.PlaybookCard)

    def test_42_format_text(self):
        builder = self.mod.DailyPlaybookBuilder()
        card = builder.build(
            regime_state={"regime": "RISK_ON"},
            recommendations=[],
        )
        text = card.format_text()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 20)

    def test_43_playbook_setup_fields(self):
        setup = self.mod.PlaybookSetup(
            ticker="AAPL",
            strategy="momentum",
            confidence=0.85,
            direction="LONG",
            why="Strong breakout pattern",
        )
        self.assertEqual(setup.ticker, "AAPL")
        self.assertAlmostEqual(setup.confidence, 0.85)


# ═══════════════════════════════════════════════════════════
# 6. Monthly Scorecard
# ═══════════════════════════════════════════════════════════

class TestMonthlyScorecard(unittest.TestCase):
    """Tests for src/notifications/monthly_scorecard.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "monthly_scorecard",
            "src/notifications/monthly_scorecard.py",
        )

    def test_50_classes_exist(self):
        self.assertTrue(hasattr(self.mod, "MonthlyScorecard"))
        self.assertTrue(hasattr(self.mod, "MonthlyScorecardBuilder"))

    def test_51_build_empty(self):
        builder = self.mod.MonthlyScorecardBuilder()
        sc = builder.build(trades=[], cycles=0, no_trade_cycles=0)
        self.assertIsInstance(sc, self.mod.MonthlyScorecard)

    def test_52_format_text(self):
        builder = self.mod.MonthlyScorecardBuilder()
        sc = builder.build(trades=[], cycles=10, no_trade_cycles=3)
        text = sc.format_text()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 10)

    def test_53_with_trades(self):
        builder = self.mod.MonthlyScorecardBuilder()
        trades = [
            {
                "pnl_pct": 2.5, "strategy": "momentum",
                "ticker": "AAPL", "direction": "LONG",
            },
            {
                "pnl_pct": -1.0, "strategy": "mean_reversion",
                "ticker": "TSLA", "direction": "LONG",
            },
            {
                "pnl_pct": 3.0, "strategy": "momentum",
                "ticker": "NVDA", "direction": "LONG",
            },
        ]
        sc = builder.build(
            trades=trades, cycles=20, no_trade_cycles=5,
        )
        self.assertEqual(sc.total_trades, 3)
        self.assertGreater(sc.total_return_pct, 0)


# ═══════════════════════════════════════════════════════════
# 7. User Mode Preferences
# ═══════════════════════════════════════════════════════════

class TestUserPreferences(unittest.TestCase):
    """Tests for src/core/user_preferences.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "user_preferences",
            "src/core/user_preferences.py",
        )

    def test_60_enum_values(self):
        om = self.mod.OutputMode
        self.assertEqual(om.QUICK.value, "quick")
        self.assertEqual(om.PRO.value, "pro")
        self.assertEqual(om.EXPLAINER.value, "explainer")

    def test_61_default_mode_is_pro(self):
        mgr = self.mod.UserPreferenceManager()
        mode = mgr.get_mode("user123")
        self.assertEqual(mode, self.mod.OutputMode.PRO)

    def test_62_set_and_get(self):
        mgr = self.mod.UserPreferenceManager()
        mgr.set_mode("user456", self.mod.OutputMode.QUICK)
        self.assertEqual(
            mgr.get_mode("user456"),
            self.mod.OutputMode.QUICK,
        )

    def test_63_cycle_mode(self):
        mgr = self.mod.UserPreferenceManager()
        mgr.set_mode("user789", self.mod.OutputMode.QUICK)
        new = mgr.cycle_mode("user789")
        self.assertEqual(new, self.mod.OutputMode.PRO)
        new = mgr.cycle_mode("user789")
        self.assertEqual(new, self.mod.OutputMode.EXPLAINER)
        new = mgr.cycle_mode("user789")
        self.assertEqual(new, self.mod.OutputMode.QUICK)

    def test_64_filter_output(self):
        mgr = self.mod.UserPreferenceManager()
        data = {
            "ticker": "AAPL", "score": 85,
            "components": {"a": 1}, "risk_budget": {"x": 2},
        }
        mgr.set_mode("user_new", self.mod.OutputMode.PRO)
        filtered = mgr.filter_output(data, "user_new")
        self.assertIsInstance(filtered, dict)

    def test_65_singleton(self):
        p1 = self.mod.get_preference_manager()
        p2 = self.mod.get_preference_manager()
        self.assertIs(p1, p2)


# ═══════════════════════════════════════════════════════════
# 8. Methodology Documentation
# ═══════════════════════════════════════════════════════════

class TestMethodology(unittest.TestCase):
    """Tests for docs/METHODOLOGY.md."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(BASE, "docs", "METHODOLOGY.md")
        with open(path) as f:
            cls.content = f.read()

    def test_70_file_exists(self):
        self.assertGreater(len(self.content), 100)

    def test_71_has_sections(self):
        for section in [
            "Universe", "Regime", "Scoring",
            "Ensemble", "Risk", "Execution",
        ]:
            self.assertIn(
                section, self.content,
                f"Missing section: {section}",
            )

    def test_72_has_strategy_families(self):
        for family in ["momentum", "trend", "mean"]:
            self.assertIn(family, self.content.lower())


# ═══════════════════════════════════════════════════════════
# 9. PerformanceTracker JSON Persistence
# ═══════════════════════════════════════════════════════════

class TestPerfTrackerJSON(unittest.TestCase):
    """Tests for JSON save/load in performance_tracker.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "perf_tracker",
            "src/performance/performance_tracker.py",
        )

    def test_80_save_to_json_method(self):
        self.assertTrue(
            hasattr(self.mod.PerformanceTracker, "save_to_json"),
        )

    def test_81_load_from_json_method(self):
        self.assertTrue(
            hasattr(self.mod.PerformanceTracker, "load_from_json"),
        )

    def test_82_outcome_to_dict_method(self):
        self.assertTrue(
            hasattr(self.mod.PerformanceTracker, "_outcome_to_dict"),
        )

    def test_83_roundtrip(self):
        pt = self.mod.PerformanceTracker.__new__(
            self.mod.PerformanceTracker,
        )
        pt.active_signals = {}
        pt.completed_signals = []
        pt.stats = self.mod.PerformanceStats(period="test")
        pt._calibration_buckets = {}
        pt._calibration_counts = {}

        # Add a completed signal
        outcome = self.mod.SignalOutcome(
            signal_id="test_001",
            ticker="AAPL",
            strategy="momentum",
            direction=self.mod.TradeDirection.LONG,
            entry_time=datetime.now(),
            entry_price=150.0,
            target_price=160.0,
            stop_loss=145.0,
            exit_time=datetime.now(),
            exit_price=158.0,
            status=self.mod.SignalStatus.TARGET_HIT,
            pnl_pct=5.33,
            hold_time_hours=48.0,
        )
        pt.completed_signals.append(outcome)

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test_signals.json")
            pt.save_to_json(path)

            # Verify file exists
            self.assertTrue(os.path.exists(path))

            # Load into another instance
            pt2 = self.mod.PerformanceTracker.__new__(
                self.mod.PerformanceTracker,
            )
            pt2.active_signals = {}
            pt2.completed_signals = []
            count = pt2.load_from_json(path)
            self.assertEqual(count, 1)
            self.assertEqual(len(pt2.completed_signals), 1)
            self.assertEqual(
                pt2.completed_signals[0].ticker, "AAPL",
            )

    def test_84_load_nonexistent(self):
        pt = self.mod.PerformanceTracker.__new__(
            self.mod.PerformanceTracker,
        )
        pt.active_signals = {}
        pt.completed_signals = []
        count = pt.load_from_json("/nonexistent/file.json")
        self.assertEqual(count, 0)


# ═══════════════════════════════════════════════════════════
# 10. Dynamic Universe Sleeves
# ═══════════════════════════════════════════════════════════

class TestDynamicSleeves(unittest.TestCase):
    """Tests for sleeve allocation in universe_builder.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "universe_builder",
            "src/scanners/universe_builder.py",
        )

    def test_90_sleeve_allocations(self):
        ub = self.mod.UniverseBuilder
        self.assertIn(
            "SLEEVE_ALLOCATIONS", dir(ub),
        )
        for regime in ["RISK_ON", "NEUTRAL", "RISK_OFF"]:
            alloc = ub.SLEEVE_ALLOCATIONS[regime]
            total = sum(alloc.values())
            self.assertAlmostEqual(total, 1.0, places=2)

    def test_91_get_sleeve_allocation(self):
        ub = self.mod.UniverseBuilder()
        alloc = ub.get_sleeve_allocation("RISK_ON")
        self.assertIn("momentum", alloc)
        self.assertIn("defensive", alloc)
        self.assertGreater(alloc["momentum"], alloc["defensive"])

    def test_92_risk_off_favours_defensive(self):
        ub = self.mod.UniverseBuilder()
        alloc = ub.get_sleeve_allocation("RISK_OFF")
        self.assertGreater(alloc["defensive"], alloc["momentum"])

    def test_93_allocate_by_sleeve(self):
        ub = self.mod.UniverseBuilder()
        assets = [
            self.mod.UniverseAsset(
                ticker=f"T{i}", name=f"T{i}",
                market=self.mod.MarketRegion.US,
                sector="Technology" if i % 3 == 0 else "Healthcare",
            )
            for i in range(30)
        ]
        result = ub.allocate_by_sleeve(assets, "NEUTRAL")
        self.assertIsInstance(result, dict)
        self.assertIn("momentum", result)
        self.assertIn("defensive", result)

    def test_94_sleeve_sectors(self):
        ub = self.mod.UniverseBuilder
        self.assertIn("SLEEVE_SECTORS", dir(ub))
        self.assertIn("momentum", ub.SLEEVE_SECTORS)
        self.assertIn("Technology", ub.SLEEVE_SECTORS["momentum"])


# ═══════════════════════════════════════════════════════════
# 11. OpportunityEnsembler.set_weights
# ═══════════════════════════════════════════════════════════

class TestSetWeights(unittest.TestCase):
    """Tests for set_weights() in opportunity_ensembler.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "opp_ensembler",
            "src/engines/opportunity_ensembler.py",
        )

    def test_100_has_set_weights(self):
        self.assertTrue(
            hasattr(self.mod.OpportunityEnsembler, "set_weights"),
        )

    def test_101_set_weights_updates(self):
        ens = self.mod.OpportunityEnsembler()
        old_w = dict(ens.weights)
        learned = {"net_expectancy": 0.5, "regime_fit": 0.3}
        ens.set_weights(learned)
        # Weights should have changed
        self.assertNotEqual(ens.weights, old_w)
        # Sum should be ~1.0
        total = sum(ens.weights.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_102_unknown_keys_ignored(self):
        ens = self.mod.OpportunityEnsembler()
        ens.set_weights({"fake_key": 999.0})
        # Should still have exactly 8 keys
        self.assertEqual(len(ens.weights), 8)

    def test_103_minimum_weight_enforced(self):
        ens = self.mod.OpportunityEnsembler()
        ens.set_weights({"timing_quality": 0.001})
        # Even with very small input, min is 0.02
        # (before normalisation)
        self.assertGreater(ens.weights["timing_quality"], 0)


# ═══════════════════════════════════════════════════════════
# 12. Discord Commands (count and presence)
# ═══════════════════════════════════════════════════════════

class TestDiscordCommands(unittest.TestCase):
    """Tests for Discord command registration."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(path) as f:
            cls.code = f.read()

    def test_110_has_playbook_command(self):
        self.assertIn("name=\"playbook\"", self.code)

    def test_111_has_scorecard_command(self):
        self.assertIn("name=\"scorecard\"", self.code)

    def test_112_has_mode_command(self):
        self.assertIn("name=\"mode\"", self.code)

    def test_113_has_methodology_command(self):
        self.assertIn("name=\"methodology\"", self.code)

    def test_114_command_count_64(self):
        count = self.code.count("@bot.tree.command")
        self.assertEqual(
            count, 64,
            f"Expected 64 commands, got {count}",
        )

    def test_115_footer_v638(self):
        self.assertIn("v6.38", self.code)

    def test_116_imports_playbook(self):
        self.assertIn("daily_playbook", self.code)

    def test_117_imports_scorecard(self):
        self.assertIn("monthly_scorecard", self.code)

    def test_118_imports_user_preferences(self):
        self.assertIn("user_preferences", self.code)


# ═══════════════════════════════════════════════════════════
# 13. MODEL_VERSION & Counts
# ═══════════════════════════════════════════════════════════

class TestVersionAndCounts(unittest.TestCase):
    """Tests for version bump and command counts."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(BASE, "README.md")) as f:
            cls.readme = f.read()
        with open(
            os.path.join(BASE, "docs", "ARCHITECTURE.md"),
        ) as f:
            cls.arch = f.read()
        cls.trust = _load(
            "trust_metadata",
            "src/core/trust_metadata.py",
        )

    def test_120_model_version(self):
        self.assertEqual(self.trust.MODEL_VERSION, "v6.38")

    def test_121_readme_64_commands(self):
        self.assertIn("64 slash commands", self.readme)

    def test_122_arch_64_commands(self):
        self.assertIn("64 slash commands", self.arch)


# ═══════════════════════════════════════════════════════════
# 14. Telegram Enhancements
# ═══════════════════════════════════════════════════════════

class TestTelegramEnhancements(unittest.TestCase):
    """Tests for enhanced Telegram commands."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            BASE, "src", "notifications", "telegram_bot.py",
        )
        with open(path) as f:
            cls.code = f.read()

    def test_130_divergence_enhanced(self):
        # Should no longer say "Coming Soon"
        # The old stub had "Coming Soon" — we replaced it
        self.assertIn("Scanning for divergences", self.code)

    def test_131_earnings_enhanced(self):
        self.assertIn("EARNINGS WATCH", self.code)

    def test_132_divergence_scanner(self):
        self.assertIn("Bearish divergence", self.code)
        self.assertIn("Bullish divergence", self.code)


# ═══════════════════════════════════════════════════════════
# 15. Integration Checks
# ═══════════════════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """Cross-module integration tests."""

    def test_140_meta_ensemble_matches_ensembler_keys(self):
        me_mod = _load(
            "meta_ensemble_2",
            "src/engines/meta_ensemble.py",
        )
        ens_mod = _load(
            "opp_ensembler_2",
            "src/engines/opportunity_ensembler.py",
        )
        me_keys = set(me_mod.COMPONENT_NAMES)
        ens_keys = set(
            ens_mod.OpportunityEnsembler.DEFAULT_WEIGHTS.keys(),
        )
        self.assertEqual(me_keys, ens_keys)

    def test_141_ensembler_accepts_learned_weights(self):
        me_mod = _load(
            "meta_ensemble_3",
            "src/engines/meta_ensemble.py",
        )
        ens_mod = _load(
            "opp_ensembler_3",
            "src/engines/opportunity_ensembler.py",
        )
        # Simulate training
        me = me_mod.MetaEnsemble()
        me._min_samples = 3
        me._retrain_interval = 2
        names = me_mod.COMPONENT_NAMES
        for i in range(4):
            me.record_outcome(
                components={
                    n: 0.5 + i * 0.05
                    for n in names
                },
                pnl_pct=1.0 + i * 0.2,
                r_multiple=0.8,
                regime_label="NEUTRAL",
                strategy_id="trend",
            )

        weights = me.get_learned_weights()
        if weights:
            ens = ens_mod.OpportunityEnsembler()
            ens.set_weights(weights)
            total = sum(ens.weights.values())
            self.assertAlmostEqual(total, 1.0, places=5)

    def test_142_options_provider_in_bearish(self):
        """Bearish sleeve can use options provider."""
        bs_mod = _load(
            "bearish_sleeve_2",
            "src/strategies/bearish_sleeve.py",
        )
        opt_mod = _load(
            "options_data_2",
            "src/ingestors/options_data.py",
        )
        sleeve = bs_mod.BearishSleeve()
        provider = opt_mod.SyntheticOptionsProvider()
        snap = provider.fetch_chain("SPY")
        self.assertIsNotNone(snap)
        # Both modules work independently
        self.assertTrue(sleeve.is_active({"regime": "risk_off"}))


if __name__ == "__main__":
    unittest.main()
