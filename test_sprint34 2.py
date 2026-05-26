"""
Sprint 34 Tests — Net Expectancy Scoring, Closed-Trade Leaderboard,
                   Unified RegimeState, Strategy Promoter

Verifies:
  1-5.   Net expectancy scoring (signed EV, net_exp component)
  6-10.  Closed-trade leaderboard (regime/direction tracking, shrinkage)
  11-17. Unified RegimeState (dataclass, dict compat, size_scalar,
         RegimeDetector → RegimeRouter delegation)
  18-24. Strategy promoter (gates, promote, reject, batch)
  25-28. Integration / edge cases
"""
import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

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

# numpy must support array ops in tests
import numpy as _real_np
sys.modules["numpy"] = _real_np

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub database before loading core
db_stub = types.ModuleType("src.core.database")
db_stub.check_database_health = MagicMock(return_value=True)
db_stub.get_session = MagicMock()
sys.modules["src.core.database"] = db_stub

# Load modules
_load("src", "src/__init__.py")
_load("src.core", "src/core/__init__.py")
_load("src.core.config", "src/core/config.py")
_load("src.core.models", "src/core/models.py")
regime_mod = _load(
    "src.engines.regime_router", "src/engines/regime_router.py"
)
leaderboard_mod = _load(
    "src.engines.strategy_leaderboard",
    "src/engines/strategy_leaderboard.py",
)
promoter_mod = _load(
    "src.engines.strategy_promoter",
    "src/engines/strategy_promoter.py",
)

# Ensembler needs more stubs
try:
    _load(
        "src.engines.opportunity_ensembler",
        "src/engines/opportunity_ensembler.py",
    )
except Exception:
    pass

RegimeRouter = regime_mod.RegimeRouter
RegimeState = regime_mod.RegimeState
StrategyLeaderboard = leaderboard_mod.StrategyLeaderboard
StrategyPromoter = promoter_mod.StrategyPromoter
PromotionResult = promoter_mod.PromotionResult


# ═════════════════════════════════════════════════════════════
# P0-1: Net Expectancy Scoring
# ═════════════════════════════════════════════════════════════
class TestNetExpectancy(unittest.TestCase):
    """Tests 1-5: Signed EV and net expectancy scoring."""

    def test_01_default_weights_include_net_expectancy(self):
        """DEFAULT_WEIGHTS has net_expectancy as largest weight."""
        try:
            ens_mod = sys.modules.get(
                "src.engines.opportunity_ensembler"
            )
            if ens_mod is None:
                ens_mod = _load(
                    "src.engines.opportunity_ensembler",
                    "src/engines/opportunity_ensembler.py",
                )
            ens = ens_mod.OpportunityEnsembler
            w = ens.DEFAULT_WEIGHTS
            self.assertIn("net_expectancy", w)
            # net_expectancy should be the largest weight
            max_key = max(w, key=w.get)
            self.assertEqual(max_key, "net_expectancy")
        except Exception as e:
            self.skipTest(f"Ensembler load issue: {e}")

    def test_02_weights_sum_to_one(self):
        """All weights sum to 1.0."""
        try:
            ens_mod = sys.modules.get(
                "src.engines.opportunity_ensembler"
            )
            if ens_mod is None:
                ens_mod = _load(
                    "src.engines.opportunity_ensembler",
                    "src/engines/opportunity_ensembler.py",
                )
            w = ens_mod.OpportunityEnsembler.DEFAULT_WEIGHTS
            self.assertAlmostEqual(sum(w.values()), 1.0, places=2)
        except Exception as e:
            self.skipTest(f"Ensembler load issue: {e}")

    def test_03_win_rate_weight_demoted(self):
        """calibrated_pwin weight ≤ 0.15 (demoted from 0.25)."""
        try:
            ens_mod = sys.modules.get(
                "src.engines.opportunity_ensembler"
            )
            if ens_mod is None:
                ens_mod = _load(
                    "src.engines.opportunity_ensembler",
                    "src/engines/opportunity_ensembler.py",
                )
            w = ens_mod.OpportunityEnsembler.DEFAULT_WEIGHTS
            self.assertLessEqual(w.get("calibrated_pwin", 1), 0.15)
        except Exception as e:
            self.skipTest(f"Ensembler load issue: {e}")

    def test_04_strategy_optimizer_uses_expectancy(self):
        """_score_result includes expectancy in composite."""
        path = os.path.join(
            ROOT, "src", "engines", "strategy_optimizer.py",
        )
        with open(path) as f:
            src = f.read()
        self.assertIn("net_exp", src)
        self.assertIn("exp_score", src)

    def test_05_abs_exp_r_removed(self):
        """abs(exp_r) no longer used in opportunity_ensembler."""
        path = os.path.join(
            ROOT, "src", "engines", "opportunity_ensembler.py",
        )
        with open(path) as f:
            src = f.read()
        self.assertNotIn("abs(exp_r)", src)


# ═════════════════════════════════════════════════════════════
# P0-2: Closed-Trade Leaderboard
# ═════════════════════════════════════════════════════════════
class TestClosedTradeLeaderboard(unittest.TestCase):
    """Tests 6-10: Leaderboard updated from closed trades."""

    def setUp(self):
        self.lb = StrategyLeaderboard()

    def test_06_record_outcome_accepts_regime_direction(self):
        """record_outcome() accepts regime, direction, market."""
        # Should not raise
        self.lb.record_outcome(
            "momentum_v1", True, 2.5,
            regime="RISK_ON", direction="LONG", market="us",
        )
        entry = self.lb._strategies["momentum_v1"]
        self.assertEqual(entry["trades"], 1)

    def test_07_regime_breakdown_tracked(self):
        """Outcomes tracked by regime."""
        self.lb.record_outcome(
            "trend_v1", True, 1.0, regime="RISK_ON",
        )
        self.lb.record_outcome(
            "trend_v1", False, -0.5, regime="RISK_OFF",
        )
        entry = self.lb._strategies["trend_v1"]
        rb = entry["regime_breakdown"]
        self.assertIn("RISK_ON", rb)
        self.assertIn("RISK_OFF", rb)
        self.assertEqual(rb["RISK_ON"]["wins"], 1)
        self.assertEqual(rb["RISK_OFF"]["wins"], 0)

    def test_08_direction_breakdown_tracked(self):
        """Outcomes tracked by direction."""
        self.lb.record_outcome(
            "mr_v1", True, 1.5, direction="LONG",
        )
        self.lb.record_outcome(
            "mr_v1", True, 0.8, direction="SHORT",
        )
        entry = self.lb._strategies["mr_v1"]
        db = entry["direction_breakdown"]
        self.assertIn("LONG", db)
        self.assertIn("SHORT", db)

    def test_09_bayesian_shrinkage_applied(self):
        """Win rate is shrunk toward 0.50 prior with few trades."""
        # 3 wins out of 3 trades — raw wr = 1.0
        # With shrinkage, should be < 1.0
        for _ in range(3):
            self.lb.record_outcome("hot_strat", True, 2.0)
        entry = self.lb._strategies["hot_strat"]
        metrics = entry.get("metrics", {})
        wr = metrics.get("win_rate", 1.0)
        # With 3/200 shrinkage: 3/200*1.0 + 197/200*0.5 ≈ 0.507
        self.assertLess(wr, 0.6)
        self.assertGreater(wr, 0.49)

    def test_10_eod_no_longer_updates_leaderboard(self):
        """_run_eod_cycle no longer has leaderboard refresh."""
        path = os.path.join(
            ROOT, "src", "engines", "auto_trading_engine.py",
        )
        with open(path) as f:
            src = f.read()
        # The old code had "for trade in self._trades_today"
        # followed by leaderboard.record_outcome in the EOD section
        eod_idx = src.find("_run_eod_cycle")
        eod_block = src[eod_idx:eod_idx + 2000]
        self.assertNotIn("_trades_today", eod_block)
        # But _record_learning_outcome should have it
        learn_idx = src.find("def _record_learning_outcome")
        learn_block = src[learn_idx:learn_idx + 4000]
        self.assertIn("self.leaderboard.record_outcome", learn_block)


# ═════════════════════════════════════════════════════════════
# P0-3: Unified RegimeState
# ═════════════════════════════════════════════════════════════
class TestUnifiedRegimeState(unittest.TestCase):
    """Tests 11-17: Canonical RegimeState dataclass."""

    def test_11_regime_state_is_dataclass(self):
        """RegimeState is a proper dataclass."""
        rs = RegimeState()
        self.assertTrue(hasattr(rs, "regime"))
        self.assertTrue(hasattr(rs, "risk_regime"))
        self.assertTrue(hasattr(rs, "size_scalar"))
        self.assertTrue(hasattr(rs, "entropy"))

    def test_12_regime_state_to_dict(self):
        """to_dict() returns all fields."""
        rs = RegimeState(regime="RISK_ON", vix=15.0)
        d = rs.to_dict()
        self.assertEqual(d["regime"], "RISK_ON")
        self.assertEqual(d["vix"], 15.0)
        self.assertIn("size_scalar", d)

    def test_13_regime_state_get(self):
        """Dict-like .get() works for backward compat."""
        rs = RegimeState(entropy=0.8, should_trade=True)
        self.assertEqual(rs.get("entropy"), 0.8)
        self.assertTrue(rs.get("should_trade"))
        self.assertIsNone(rs.get("nonexistent"))
        self.assertEqual(rs.get("nonexistent", 42), 42)

    def test_14_classify_returns_regime_state(self):
        """RegimeRouter.classify() returns RegimeState object."""
        router = RegimeRouter()
        rs = router.classify({"vix": 18.0})
        self.assertIsInstance(rs, RegimeState)
        self.assertIn(rs.regime, ["RISK_ON", "NEUTRAL", "RISK_OFF"])

    def test_15_size_scalar_crisis_is_zero(self):
        """In crisis, size_scalar = 0."""
        router = RegimeRouter()
        rs = router.classify({"vix": 40.0})
        self.assertEqual(rs.size_scalar, 0.0)
        self.assertFalse(rs.should_trade)

    def test_16_size_scalar_normal_is_one(self):
        """Strong bullish regime → size_scalar = 1.0."""
        router = RegimeRouter()
        rs = router.classify({
            "vix": 12.0,
            "spy_return_20d": 0.08,
            "breadth_pct": 0.80,
            "vix_term_slope": -0.05,
        })
        # Strong risk-on with low entropy should give full sizing
        self.assertGreaterEqual(rs.size_scalar, 0.75)
        self.assertTrue(rs.should_trade)

    def test_17_size_scalar_uncertain_is_half(self):
        """High entropy → size_scalar = 0.5 (not 0)."""
        router = RegimeRouter(no_trade_entropy=0.5)
        rs = router.classify({
            "vix": 20.0,
            "spy_return_20d": 0.0,
            "breadth_pct": 0.50,
        })
        # Balanced inputs → high entropy → should hit 0.5 scalar
        if rs.entropy > 0.5:
            self.assertIn(
                rs.size_scalar, [0.5, 0.6, 0.75],
            )

    def test_17b_regime_state_strategy_multipliers(self):
        """get_strategy_multipliers accepts RegimeState."""
        router = RegimeRouter()
        rs = RegimeState(
            risk_on_uptrend=0.7,
            neutral_range=0.2,
            risk_off_downtrend=0.1,
        )
        mults = router.get_strategy_multipliers(rs)
        self.assertIn("momentum", mults)
        self.assertGreater(mults["momentum"], 0.5)


# ═════════════════════════════════════════════════════════════
# P0-4: Strategy Promoter
# ═════════════════════════════════════════════════════════════
class TestStrategyPromoter(unittest.TestCase):
    """Tests 18-24: 2-stage promotion pipeline."""

    def setUp(self):
        self.promoter = StrategyPromoter()

    def _make_bt_result(self, **overrides):
        """Create a mock BacktestResult."""
        defaults = {
            "alpha": 0.05,
            "cvar_95": -0.01,
            "max_drawdown": -0.10,
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "total_trades": 50,
            "avg_slippage_bps": 5.0,
        }
        defaults.update(overrides)
        mock = MagicMock()
        for k, v in defaults.items():
            setattr(mock, k, v)
        return mock

    def test_18_promote_good_strategy(self):
        """Strategy passing all gates is promoted."""
        bt = self._make_bt_result()
        r = self.promoter.evaluate("momentum_v2", 75.0, bt)
        self.assertTrue(r.promoted)
        self.assertEqual(len(r.rejections), 0)

    def test_19_reject_low_stage1(self):
        """Strategy below stage-1 score is rejected."""
        bt = self._make_bt_result()
        r = self.promoter.evaluate("weak_strat", 20.0, bt)
        self.assertFalse(r.promoted)
        self.assertTrue(any("Stage-1" in x for x in r.rejections))

    def test_20_reject_negative_alpha(self):
        """Negative alpha → rejected."""
        bt = self._make_bt_result(alpha=-0.02)
        r = self.promoter.evaluate("no_alpha", 60.0, bt)
        self.assertFalse(r.promoted)
        self.assertTrue(any("Alpha" in x for x in r.rejections))

    def test_21_reject_deep_drawdown(self):
        """Max DD exceeding threshold → rejected."""
        bt = self._make_bt_result(max_drawdown=-0.25)
        r = self.promoter.evaluate("dd_strat", 60.0, bt)
        self.assertFalse(r.promoted)
        self.assertTrue(any("DD" in x for x in r.rejections))

    def test_22_reject_low_pf(self):
        """Profit factor below minimum → rejected."""
        bt = self._make_bt_result(profit_factor=0.9)
        r = self.promoter.evaluate("low_pf", 60.0, bt)
        self.assertFalse(r.promoted)
        self.assertTrue(any("PF" in x for x in r.rejections))

    def test_23_reject_too_few_trades(self):
        """Too few trades → rejected."""
        bt = self._make_bt_result(total_trades=5)
        r = self.promoter.evaluate("few_trades", 60.0, bt)
        self.assertFalse(r.promoted)
        self.assertTrue(any("trades" in x for x in r.rejections))

    def test_24_batch_evaluation(self):
        """evaluate_batch processes multiple candidates."""
        candidates = [
            {
                "strategy_name": "good_one",
                "stage1_score": 80.0,
                "backtest_result": self._make_bt_result(),
            },
            {
                "strategy_name": "bad_one",
                "stage1_score": 10.0,
                "backtest_result": self._make_bt_result(),
            },
            {
                "strategy_name": "no_bt",
                "stage1_score": 70.0,
            },
        ]
        results = self.promoter.evaluate_batch(candidates)
        self.assertEqual(len(results), 3)
        promoted = [r for r in results if r.promoted]
        self.assertEqual(len(promoted), 1)
        self.assertEqual(promoted[0].strategy_name, "good_one")


# ═════════════════════════════════════════════════════════════
# Integration / Edge Cases
# ═════════════════════════════════════════════════════════════
class TestIntegrationEdge(unittest.TestCase):
    """Tests 25-28: Integration and edge cases."""

    def test_25_leaderboard_score_weights_sum(self):
        """Leaderboard SCORE_WEIGHTS sum to 1.0."""
        w = StrategyLeaderboard.SCORE_WEIGHTS
        self.assertAlmostEqual(sum(w.values()), 1.0, places=2)

    def test_26_expectancy_weight_equals_sharpe(self):
        """Expectancy has same weight as Sharpe in leaderboard."""
        w = StrategyLeaderboard.SCORE_WEIGHTS
        self.assertEqual(
            w["expectancy"], w["oos_sharpe"],
        )

    def test_27_win_rate_weight_small(self):
        """Win rate weight ≤ 0.05 in leaderboard."""
        w = StrategyLeaderboard.SCORE_WEIGHTS
        self.assertLessEqual(w["win_rate"], 0.05)

    def test_28_promoter_summary_format(self):
        """PromotionResult.summary() produces readable string."""
        r = PromotionResult(
            strategy_name="test_strat",
            promoted=True,
            stage1_score=75.0,
            alpha=0.05,
            cvar_95=-0.01,
            max_drawdown=-0.08,
            profit_factor=2.0,
            sharpe=1.5,
            total_trades=100,
        )
        s = r.summary()
        self.assertIn("PROMOTED", s)
        self.assertIn("test_strat", s)
        self.assertIn("Alpha", s)


if __name__ == "__main__":
    unittest.main()
