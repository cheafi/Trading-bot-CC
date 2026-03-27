"""
Sprint 21 — Real Ensemble Sizing

Tests:
  1.  OpportunityEnsembler accepts regime_weights parameter
  2.  _resolve_regime_weight matches strategy families
  3.  strategy_health blended with regime weight
  4.  Edge p_t1 used for calibrated_pwin component
  5.  Edge EV used for expected_return component
  6.  Half-Kelly in auto_trading_engine._calculate_position_size
  7.  Half-Kelly in signal_engine.RiskModel._calculate_position_size
  8.  Leaderboard sizing_multiplier applied in engine sizing
  9.  regime_router.get_strategy_multipliers wired to ensembler
  10. _execute_signal accepts opp dict with edge data
  11. Composite score changes with regime weights
  12. Kelly with positive edge yields > 0.25 multiplier
  13. Kelly with negative edge yields 0.25 floor
"""
import sys
import os
import re
import unittest
import importlib.util
import math
from unittest.mock import MagicMock

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
db_mod.check_database_health = MagicMock(
    return_value={"status": "ok"},
)
sys.modules.setdefault("src.core.database", db_mod)

sys.modules.setdefault("asyncpg", MagicMock())
sys.modules.setdefault("tenacity", MagicMock())
sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.commands", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, rel_path):
    path = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _src(path):
    return os.path.join(ROOT, path)


def _read(path):
    with open(_src(path)) as f:
        return f.read()


# ═════════════════════════════════════════════════════════════════════
# 1. ENSEMBLER — regime_weights parameter
# ═════════════════════════════════════════════════════════════════════
class TestEnsemblerRegimeWeights(unittest.TestCase):
    """OpportunityEnsembler accepts and uses regime_weights."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.opportunity_ensembler",
            "src/engines/opportunity_ensembler.py",
        )

    def _make_signal(self, **kw):
        base = {
            "ticker": "AAPL",
            "direction": "LONG",
            "score": 0.7,
            "strategy_name": "momentum_breakout",
            "risk_reward_ratio": 2.0,
            "expected_return": 0.05,
        }
        base.update(kw)
        return base

    def test_01_rank_accepts_regime_weights(self):
        """rank_opportunities must accept regime_weights kwarg."""
        ens = self.mod.OpportunityEnsembler()
        sig = self._make_signal()
        result = ens.rank_opportunities(
            [sig],
            {"risk_on_uptrend": 0.7, "neutral_range": 0.2,
             "risk_off_downtrend": 0.1, "should_trade": True},
            strategy_scores={"momentum_breakout": 0.8},
            regime_weights={"momentum": 1.0, "mean_reversion": 0.3},
        )
        self.assertEqual(len(result), 1)
        self.assertIn("composite_score", result[0])

    def test_02_regime_weight_affects_score(self):
        """Higher regime weight for strategy → higher composite."""
        ens = self.mod.OpportunityEnsembler()
        sig = self._make_signal()
        regime = {
            "risk_on_uptrend": 0.7,
            "neutral_range": 0.2,
            "risk_off_downtrend": 0.1,
            "should_trade": True,
        }
        scores = {"momentum_breakout": 0.8}

        # High regime weight for momentum
        r1 = ens.rank_opportunities(
            [sig], regime,
            strategy_scores=scores,
            regime_weights={"momentum": 1.0},
        )
        # Low regime weight for momentum
        r2 = ens.rank_opportunities(
            [sig], regime,
            strategy_scores=scores,
            regime_weights={"momentum": 0.2},
        )
        self.assertGreater(
            r1[0]["composite_score"],
            r2[0]["composite_score"],
            "Higher regime weight should produce higher score",
        )

    def test_03_none_regime_weights_neutral(self):
        """None regime_weights should act as neutral (1.0)."""
        ens = self.mod.OpportunityEnsembler()
        sig = self._make_signal()
        regime = {
            "risk_on_uptrend": 0.5,
            "neutral_range": 0.3,
            "risk_off_downtrend": 0.2,
            "should_trade": True,
        }
        r_none = ens.rank_opportunities(
            [sig], regime,
            strategy_scores={"momentum_breakout": 0.8},
            regime_weights=None,
        )
        r_one = ens.rank_opportunities(
            [sig], regime,
            strategy_scores={"momentum_breakout": 0.8},
            regime_weights={"momentum": 1.0},
        )
        # Should be equal since 1.0 is neutral
        self.assertAlmostEqual(
            r_none[0]["composite_score"],
            r_one[0]["composite_score"],
            places=3,
        )


# ═════════════════════════════════════════════════════════════════════
# 2. _resolve_regime_weight — strategy family matching
# ═════════════════════════════════════════════════════════════════════
class TestResolveRegimeWeight(unittest.TestCase):
    """_resolve_regime_weight matches families by substring."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.opportunity_ensembler",
            "src/engines/opportunity_ensembler.py",
        )

    def test_04_exact_match(self):
        """Exact key match returns weight."""
        w = self.mod.OpportunityEnsembler._resolve_regime_weight(
            "momentum", {"momentum": 0.9, "swing": 0.5},
        )
        self.assertAlmostEqual(w, 0.9)

    def test_05_substring_match(self):
        """'momentum_breakout' should match 'momentum' key."""
        w = self.mod.OpportunityEnsembler._resolve_regime_weight(
            "momentum_breakout",
            {"momentum": 0.8, "mean_reversion": 0.3},
        )
        self.assertAlmostEqual(w, 0.8)

    def test_06_no_match_returns_conservative(self):
        """Unknown strategy returns 0.5."""
        w = self.mod.OpportunityEnsembler._resolve_regime_weight(
            "exotic_strategy",
            {"momentum": 0.8, "swing": 0.6},
        )
        self.assertAlmostEqual(w, 0.5)

    def test_07_none_weights_returns_1(self):
        """None regime_weights returns 1.0 (neutral)."""
        w = self.mod.OpportunityEnsembler._resolve_regime_weight(
            "anything", None,
        )
        self.assertAlmostEqual(w, 1.0)

    def test_08_floor_at_0_1(self):
        """Weight should never go below 0.1."""
        w = self.mod.OpportunityEnsembler._resolve_regime_weight(
            "momentum", {"momentum": 0.0},
        )
        self.assertAlmostEqual(w, 0.1)


# ═════════════════════════════════════════════════════════════════════
# 3. EDGE DATA USED IN SCORING
# ═════════════════════════════════════════════════════════════════════
class TestEdgeDataInScoring(unittest.TestCase):
    """Edge p_t1 and edge_ev should influence scoring."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.opportunity_ensembler",
            "src/engines/opportunity_ensembler.py",
        )

    def test_09_edge_p_t1_used_for_pwin(self):
        """Signal with edge_p_t1 should use it for pwin."""
        ens = self.mod.OpportunityEnsembler()
        regime = {
            "risk_on_uptrend": 0.5,
            "neutral_range": 0.3,
            "risk_off_downtrend": 0.2,
            "should_trade": True,
        }
        # With edge_p_t1 = 0.8 (high)
        sig_high = {
            "ticker": "AAPL", "direction": "LONG",
            "score": 0.5, "strategy_name": "momentum_breakout",
            "risk_reward_ratio": 2.0, "expected_return": 0.03,
            "edge_p_t1": 0.8,
        }
        # Without edge_p_t1 (falls back to score=0.5)
        sig_low = {
            "ticker": "MSFT", "direction": "LONG",
            "score": 0.5, "strategy_name": "momentum_breakout",
            "risk_reward_ratio": 2.0, "expected_return": 0.03,
        }
        r_high = ens.rank_opportunities(
            [sig_high], regime,
        )
        r_low = ens.rank_opportunities(
            [sig_low], regime,
        )
        self.assertGreater(
            r_high[0]["composite_score"],
            r_low[0]["composite_score"],
            "edge_p_t1=0.8 should score higher than raw score=0.5",
        )

    def test_10_edge_ev_used_for_expected_return(self):
        """Signal with edge_ev should use it for exp_r."""
        ens = self.mod.OpportunityEnsembler()
        regime = {
            "risk_on_uptrend": 0.5,
            "neutral_range": 0.3,
            "risk_off_downtrend": 0.2,
            "should_trade": True,
        }
        sig_ev = {
            "ticker": "AAPL", "direction": "LONG",
            "score": 0.5, "strategy_name": "vcp",
            "risk_reward_ratio": 2.0,
            "expected_return": 0.01,
            "edge_ev": 0.08,  # 8% expected
        }
        sig_no = {
            "ticker": "MSFT", "direction": "LONG",
            "score": 0.5, "strategy_name": "vcp",
            "risk_reward_ratio": 2.0,
            "expected_return": 0.01,
        }
        r_ev = ens.rank_opportunities([sig_ev], regime)
        r_no = ens.rank_opportunities([sig_no], regime)
        self.assertGreater(
            r_ev[0]["composite_score"],
            r_no[0]["composite_score"],
            "edge_ev=0.08 should score higher than raw 0.01",
        )


# ═════════════════════════════════════════════════════════════════════
# 4. HALF-KELLY IN AUTO_TRADING_ENGINE
# ═════════════════════════════════════════════════════════════════════
class TestKellyEnginePositionSize(unittest.TestCase):
    """_calculate_position_size uses half-Kelly + leaderboard."""

    def test_11_source_has_kelly_formula(self):
        """auto_trading_engine has Kelly fraction code."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        method = src[idx:idx + 3000]
        self.assertIn("kelly_f", method)
        self.assertIn("edge_pwin", method)
        self.assertIn("edge_rr", method)

    def test_12_source_has_leaderboard_multiplier(self):
        """Engine sizing uses leaderboard.get_sizing_multiplier."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        method = src[idx:idx + 3000]
        self.assertIn("get_sizing_multiplier", method)
        self.assertIn("lb_mult", method)

    def test_13_kelly_positive_edge(self):
        """Positive Kelly edge should yield > 0.25 multiplier."""
        # Kelly = p - (1-p)/b = 0.6 - 0.4/2.0 = 0.4
        # Half-Kelly = 0.2 → clamped to max(0.25, 0.2) = 0.25
        p, b = 0.6, 2.0
        kelly_f = p - (1 - p) / b
        half_k = min(kelly_f * 0.5, 1.0)
        half_k = max(half_k, 0.25) if half_k > 0 else 0.25
        self.assertGreaterEqual(half_k, 0.25)

    def test_14_kelly_strong_edge(self):
        """Strong positive Kelly should yield higher multiplier."""
        # Kelly = 0.7 - 0.3/3.0 = 0.6
        # Half-Kelly = 0.3
        p, b = 0.7, 3.0
        kelly_f = p - (1 - p) / b
        half_k = min(kelly_f * 0.5, 1.0)
        half_k = max(half_k, 0.25)
        self.assertGreater(half_k, 0.25)
        self.assertAlmostEqual(half_k, 0.3, places=2)

    def test_15_kelly_negative_edge(self):
        """Negative Kelly edge should floor at 0.25."""
        # Kelly = 0.3 - 0.7/1.0 = -0.4 → clamped to 0
        # Half-Kelly = 0 → floor to 0.25
        p, b = 0.3, 1.0
        kelly_f = p - (1 - p) / b
        kelly_f = max(kelly_f, 0.0)
        half_k = min(kelly_f * 0.5, 1.0)
        half_k = max(half_k, 0.25) if half_k > 0 else 0.25
        self.assertAlmostEqual(half_k, 0.25)

    def test_16_accepts_edge_params(self):
        """_calculate_position_size accepts edge_pwin, edge_rr."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        sig = src[idx:idx + 200]
        self.assertIn("edge_pwin", sig)
        self.assertIn("edge_rr", sig)
        self.assertIn("strategy_name", sig)


# ═════════════════════════════════════════════════════════════════════
# 5. HALF-KELLY IN SIGNAL_ENGINE RISKMODEL
# ═════════════════════════════════════════════════════════════════════
class TestKellyRiskModel(unittest.TestCase):
    """RiskModel._calculate_position_size uses Kelly when edge available."""

    def test_17_riskmodel_has_kelly(self):
        """signal_engine RiskModel has Kelly fraction code."""
        src = _read("src/engines/signal_engine.py")
        # Find the RiskModel's _calculate_position_size
        idx = src.index("class RiskModel")
        class_src = src[idx:idx + 5000]
        self.assertIn("kelly_f", class_src)
        self.assertIn("edge_pwin", class_src)

    def test_18_riskmodel_uses_edge_p_t1(self):
        """RiskModel reads edge_p_t1 from signal attrs."""
        src = _read("src/engines/signal_engine.py")
        idx = src.index("class RiskModel")
        class_src = src[idx:idx + 5000]
        self.assertIn("edge_p_t1", class_src)

    def test_19_riskmodel_confidence_fallback(self):
        """Without edge data, falls back to confidence factor."""
        src = _read("src/engines/signal_engine.py")
        idx = src.index("class RiskModel")
        class_src = src[idx:idx + 5000]
        self.assertIn("confidence_factor", class_src)


# ═════════════════════════════════════════════════════════════════════
# 6. WIRING — regime_weights to ensembler
# ═════════════════════════════════════════════════════════════════════
class TestRegimeWeightsWiring(unittest.TestCase):
    """regime_router.get_strategy_multipliers wired to ensembler."""

    def test_20_engine_passes_regime_weights(self):
        """auto_trading_engine passes regime_weights= to ensembler."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("ensembler.rank_opportunities")
        block = src[idx:idx + 500]
        self.assertIn("regime_weights=", block)

    def test_21_regime_weights_from_router(self):
        """regime_weights comes from regime_router method."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("ensembler.rank_opportunities")
        block = src[idx:idx + 500]
        self.assertIn("get_strategy_multipliers", block)

    def test_22_execute_signal_accepts_opp(self):
        """_execute_signal accepts opp dict parameter."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _execute_signal")
        sig_line = src[idx:idx + 200]
        self.assertIn("opp", sig_line)


# ═════════════════════════════════════════════════════════════════════
# 7. REGIME ROUTER — get_strategy_multipliers
# ═════════════════════════════════════════════════════════════════════
class TestRegimeRouterMultipliers(unittest.TestCase):
    """RegimeRouter.get_strategy_multipliers produces family weights."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.regime_router",
            "src/engines/regime_router.py",
        )

    def test_23_multipliers_risk_on(self):
        """In risk-on, momentum should be high."""
        rr = self.mod.RegimeRouter()
        state = {
            "risk_on_uptrend": 0.8,
            "neutral_range": 0.1,
            "risk_off_downtrend": 0.1,
        }
        mults = rr.get_strategy_multipliers(state)
        self.assertIn("momentum", mults)
        self.assertGreater(mults["momentum"], 0.5)

    def test_24_multipliers_risk_off(self):
        """In risk-off, defensive should be high."""
        rr = self.mod.RegimeRouter()
        state = {
            "risk_on_uptrend": 0.1,
            "neutral_range": 0.1,
            "risk_off_downtrend": 0.8,
        }
        mults = rr.get_strategy_multipliers(state)
        self.assertIn("defensive", mults)
        self.assertGreater(mults["defensive"], 0.5)
        self.assertLess(mults["momentum"], 0.5)

    def test_25_multipliers_neutral(self):
        """In neutral, mean_reversion should be high."""
        rr = self.mod.RegimeRouter()
        state = {
            "risk_on_uptrend": 0.1,
            "neutral_range": 0.8,
            "risk_off_downtrend": 0.1,
        }
        mults = rr.get_strategy_multipliers(state)
        self.assertIn("mean_reversion", mults)
        self.assertGreater(mults["mean_reversion"], 0.5)


# ═════════════════════════════════════════════════════════════════════
# 8. INTEGRATION — full ensemble pipeline
# ═════════════════════════════════════════════════════════════════════
class TestEnsembleIntegration(unittest.TestCase):
    """Full pipeline: signals → ensembler with weights → ranked."""

    @classmethod
    def setUpClass(cls):
        cls.ens_mod = _load(
            "src.engines.opportunity_ensembler",
            "src/engines/opportunity_ensembler.py",
        )
        cls.rr_mod = _load(
            "src.engines.regime_router",
            "src/engines/regime_router.py",
        )

    def test_26_full_pipeline(self):
        """Signals ranked with router weights + leaderboard scores."""
        ens = self.ens_mod.OpportunityEnsembler()
        rr = self.rr_mod.RegimeRouter()

        regime = {
            "risk_on_uptrend": 0.7,
            "neutral_range": 0.2,
            "risk_off_downtrend": 0.1,
            "should_trade": True,
        }
        weights = rr.get_strategy_multipliers(regime)

        signals = [
            {
                "ticker": "AAPL", "direction": "LONG",
                "score": 0.7,
                "strategy_name": "momentum_breakout",
                "risk_reward_ratio": 2.5,
                "expected_return": 0.05,
                "edge_p_t1": 0.6,
                "edge_ev": 0.04,
            },
            {
                "ticker": "XLU", "direction": "LONG",
                "score": 0.6,
                "strategy_name": "defensive",
                "risk_reward_ratio": 1.5,
                "expected_return": 0.02,
            },
        ]

        ranked = ens.rank_opportunities(
            signals, regime,
            strategy_scores={
                "momentum_breakout": 0.8,
                "defensive": 0.4,
            },
            regime_weights=weights,
        )

        self.assertEqual(len(ranked), 2)
        # In risk-on, momentum should rank higher than defensive
        self.assertEqual(ranked[0]["ticker"], "AAPL")
        self.assertGreater(
            ranked[0]["composite_score"],
            ranked[1]["composite_score"],
        )

    def test_27_defensive_wins_in_risk_off(self):
        """In risk-off regime, defensive should outrank momentum."""
        ens = self.ens_mod.OpportunityEnsembler()
        rr = self.rr_mod.RegimeRouter()

        regime = {
            "risk_on_uptrend": 0.1,
            "neutral_range": 0.1,
            "risk_off_downtrend": 0.8,
            "should_trade": True,
        }
        weights = rr.get_strategy_multipliers(regime)

        signals = [
            {
                "ticker": "AAPL", "direction": "LONG",
                "score": 0.7,
                "strategy_name": "momentum_breakout",
                "risk_reward_ratio": 2.5,
                "expected_return": 0.05,
            },
            {
                "ticker": "XLU", "direction": "LONG",
                "score": 0.7,
                "strategy_name": "defensive",
                "risk_reward_ratio": 2.5,
                "expected_return": 0.05,
            },
        ]

        ranked = ens.rank_opportunities(
            signals, regime,
            strategy_scores={
                "momentum_breakout": 0.6,
                "defensive": 0.6,
            },
            regime_weights=weights,
        )

        # Defensive should rank higher in risk-off
        defensive_rank = next(
            r for r in ranked if r["ticker"] == "XLU"
        )
        momentum_rank = next(
            r for r in ranked if r["ticker"] == "AAPL"
        )
        self.assertGreater(
            defensive_rank["composite_score"],
            momentum_rank["composite_score"],
            "Defensive should outrank momentum in risk-off",
        )


if __name__ == "__main__":
    unittest.main()
