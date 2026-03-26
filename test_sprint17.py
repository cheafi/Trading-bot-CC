"""
Sprint 17 — Decision-Layer Unit Tests

Real instantiation + method-call tests for:
  1. OpportunityEnsembler  (rank_opportunities, _score_opportunity, _calc_regime_fit, _correlation_penalty, _apply_suppression)
  2. StrategyLeaderboard   (update, get_rankings, get_sizing_multiplier, record_outcome, lifecycle)
  3. EdgeCalculator        (compute with base-rate, regime adjustments, feature adjustments, calibration)
  4. ContextAssembler      (assemble sync/async, cache, defaults)
  5. errors.py             (typed hierarchy, to_dict, catch-by-base)

Stubs only: pydantic_settings, sqlalchemy, database (needed by import chain).
"""
import sys
import os
import unittest
import importlib.util
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from enum import Enum

# ── Stubs required by import chain ──────────────────────────────────
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


# ── Load modules ──────────────────────────────────────────────────────
errors_mod = _load("src.core.errors", "src/core/errors.py")
TradingError = errors_mod.TradingError
BrokerError = errors_mod.BrokerError
DataError = errors_mod.DataError
ValidationError_ = errors_mod.ValidationError  # avoid shadowing builtin
RiskLimitError = errors_mod.RiskLimitError
SignalError = errors_mod.SignalError
ConfigError = errors_mod.ConfigError

# Models — need pydantic
models_mod = _load("src.core.models", "src/core/models.py")

# Strategy leaderboard
lb_mod = _load("src.engines.strategy_leaderboard", "src/engines/strategy_leaderboard.py")
StrategyLeaderboard = lb_mod.StrategyLeaderboard
StrategyStatus = lb_mod.StrategyStatus

# Opportunity ensembler — may import get_trading_config
config_mock = MagicMock()
config_mock.get_trading_config = MagicMock(return_value={})
sys.modules.setdefault("src.core.config", config_mock)
ens_mod = _load("src.engines.opportunity_ensembler", "src/engines/opportunity_ensembler.py")
OpportunityEnsembler = ens_mod.OpportunityEnsembler

# Insight engine (EdgeCalculator)
ie_mod = _load("src.engines.insight_engine", "src/engines/insight_engine.py")
EdgeCalculator = ie_mod.EdgeCalculator

# Context assembler
ca_mod = _load("src.engines.context_assembler", "src/engines/context_assembler.py")
ContextAssembler = ca_mod.ContextAssembler


# ═════════════════════════════════════════════════════════════════════
# 1. ERRORS.PY TESTS
# ═════════════════════════════════════════════════════════════════════
class TestErrors(unittest.TestCase):

    def test_01_trading_error_base(self):
        """TradingError stores message/code/detail."""
        err = TradingError("boom", code="T01", detail="extra")
        self.assertEqual(err.message, "boom")
        self.assertEqual(err.code, "T01")
        self.assertEqual(str(err), "boom")

    def test_02_to_dict_returns_correct_keys(self):
        """to_dict() returns error_type, message, code, detail."""
        err = TradingError("x")
        d = err.to_dict()
        self.assertIn("error_type", d)
        self.assertEqual(d["error_type"], "TradingError")
        self.assertIn("message", d)
        self.assertIn("code", d)
        self.assertIn("detail", d)

    def test_03_broker_error_attributes(self):
        """BrokerError has broker attribute and correct code."""
        err = BrokerError("conn fail", broker="alpaca")
        self.assertEqual(err.broker, "alpaca")
        self.assertEqual(err.code, "BROKER_ERR")
        self.assertIn("alpaca", err.detail)

    def test_04_data_error_attributes(self):
        """DataError has ticker attribute."""
        err = DataError("stale", ticker="AAPL")
        self.assertEqual(err.ticker, "AAPL")
        self.assertEqual(err.code, "DATA_ERR")

    def test_05_catch_subclass_by_base(self):
        """All typed errors are caught by `except TradingError`."""
        for cls, kwargs in [
            (BrokerError, {"broker": "ib"}),
            (DataError, {"ticker": "MSFT"}),
            (ValidationError_, {"field": "price"}),
            (RiskLimitError, {"limit_type": "daily_loss"}),
            (SignalError, {"strategy": "vcp"}),
            (ConfigError, {"param": "api_key"}),
        ]:
            with self.subTest(cls=cls.__name__):
                try:
                    raise cls("test", **kwargs)
                except TradingError as e:
                    d = e.to_dict()
                    self.assertEqual(d["error_type"], cls.__name__)

    def test_06_risk_limit_error(self):
        """RiskLimitError has limit_type and correct code."""
        err = RiskLimitError("max dd", limit_type="daily_loss")
        self.assertEqual(err.limit_type, "daily_loss")
        self.assertEqual(err.code, "RISK_LIMIT")


# ═════════════════════════════════════════════════════════════════════
# 2. OPPORTUNITY ENSEMBLER TESTS
# ═════════════════════════════════════════════════════════════════════
class TestOpportunityEnsembler(unittest.TestCase):

    def setUp(self):
        self.ens = OpportunityEnsembler()

    def test_07_default_weights_sum_to_one(self):
        """DEFAULT_WEIGHTS values sum to 1.0."""
        total = sum(self.ens.DEFAULT_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_08_rank_empty_signals(self):
        """rank_opportunities([]) returns empty list."""
        result = self.ens.rank_opportunities(
            signals=[],
            regime_state={"risk_on_uptrend": 0.5},
            portfolio_state={},
            strategy_scores={},
        )
        self.assertEqual(result, [])

    def test_09_rank_single_signal(self):
        """Single signal is scored and returned."""
        signal = {
            "ticker": "AAPL",
            "direction": "LONG",
            "strategy_name": "momentum_breakout",
            "confidence": 70,
            "expected_return_pct": 5.0,
            "risk_reward": 3.0,
        }
        result = self.ens.rank_opportunities(
            signals=[signal],
            regime_state={"risk_on_uptrend": 0.6, "neutral_range": 0.3, "risk_off_downtrend": 0.1},
            portfolio_state={},
            strategy_scores={"momentum_breakout": 0.7},
        )
        self.assertEqual(len(result), 1)
        self.assertIn("composite_score", result[0])
        self.assertIn("trade_decision", result[0])
        self.assertIsInstance(result[0]["composite_score"], float)

    def test_10_rank_sorting_order(self):
        """Multiple signals are sorted by composite_score descending."""
        signals = [
            {"ticker": "LOW", "direction": "LONG", "strategy_name": "mean_reversion",
             "confidence": 30, "expected_return_pct": 1.0, "risk_reward": 1.0},
            {"ticker": "HIGH", "direction": "LONG", "strategy_name": "momentum_breakout",
             "confidence": 90, "expected_return_pct": 8.0, "risk_reward": 4.0},
        ]
        result = self.ens.rank_opportunities(
            signals=signals,
            regime_state={"risk_on_uptrend": 0.5, "neutral_range": 0.3, "risk_off_downtrend": 0.2},
            portfolio_state={},
            strategy_scores={"momentum_breakout": 0.9, "mean_reversion": 0.4},
        )
        self.assertEqual(len(result), 2)
        self.assertGreaterEqual(result[0]["composite_score"], result[1]["composite_score"])

    def test_11_regime_fit_momentum(self):
        """_calc_regime_fit returns higher score in risk-on for momentum."""
        fit = self.ens._calc_regime_fit(
            {"strategy_name": "momentum_breakout", "direction": "LONG"},
            {"risk_on_uptrend": 0.7, "neutral_range": 0.2, "risk_off_downtrend": 0.1},
        )
        self.assertGreater(fit, 0.3)

    def test_12_correlation_penalty_same_ticker(self):
        """Holding same ticker yields penalty."""
        penalty = self.ens._correlation_penalty(
            {"ticker": "AAPL", "sector": "Tech"},
            {"tickers": ["AAPL", "MSFT"], "sectors": {"Tech": 0.3}},
        )
        self.assertGreater(penalty, 0.0)

    def test_13_correlation_penalty_no_overlap(self):
        """No overlap → zero penalty."""
        penalty = self.ens._correlation_penalty(
            {"ticker": "GOOG", "sector": "Comm"},
            {"tickers": ["AAPL"], "sectors": {"Tech": 0.1}},
        )
        self.assertEqual(penalty, 0.0)

    def test_14_suppression_regime_no_trade(self):
        """If regime says no trade, all decisions suppressed."""
        ranked = [
            {"composite_score": 0.8, "trade_decision": True},
            {"composite_score": 0.6, "trade_decision": True},
        ]
        result = self.ens._apply_suppression(ranked, {"should_trade": False})
        for r in result:
            self.assertFalse(r["trade_decision"])
            self.assertEqual(r.get("suppression_reason"), "regime_no_trade")


# ═════════════════════════════════════════════════════════════════════
# 3. STRATEGY LEADERBOARD TESTS
# ═════════════════════════════════════════════════════════════════════
class TestStrategyLeaderboard(unittest.TestCase):

    def setUp(self):
        self.lb = StrategyLeaderboard()

    def test_15_update_creates_entry(self):
        """update() creates a strategy entry with blended_score."""
        metrics = {
            "oos_sharpe": 1.5,
            "expectancy": 1.0,
            "calmar_ratio": 2.0,
            "win_rate": 0.55,
            "profit_factor": 2.0,
            "max_drawdown": 0.10,
            "consistency": 0.7,
            "trade_count": 5,
        }
        entry = self.lb.update("momentum", metrics)
        self.assertIn("blended_score", entry)
        self.assertGreater(entry["blended_score"], 0)
        self.assertEqual(entry["status"], StrategyStatus.ACTIVE)

    def test_16_get_rankings_sorted(self):
        """get_rankings() returns strategies sorted descending."""
        self.lb.update("good", {"oos_sharpe": 2.0, "win_rate": 0.7, "trade_count": 5})
        self.lb.update("bad", {"oos_sharpe": 0.1, "win_rate": 0.2, "trade_count": 5})
        rankings = self.lb.get_rankings()
        self.assertEqual(len(rankings), 2)
        self.assertGreaterEqual(
            rankings[0]["blended_score"],
            rankings[1]["blended_score"],
        )

    def test_17_sizing_multiplier_active(self):
        """ACTIVE strategy gets 1.0 multiplier."""
        self.lb.update("strat_a", {"oos_sharpe": 1.5, "win_rate": 0.6, "trade_count": 5})
        mult = self.lb.get_sizing_multiplier("strat_a")
        self.assertEqual(mult, 1.0)

    def test_18_sizing_multiplier_unknown(self):
        """Unknown strategy gets 0.5 (conservative)."""
        mult = self.lb.get_sizing_multiplier("never_seen")
        self.assertEqual(mult, 0.5)

    def test_19_record_outcome_updates(self):
        """record_outcome increments trades and wins."""
        self.lb.record_outcome("test_strat", is_win=True, pnl_pct=2.5)
        self.lb.record_outcome("test_strat", is_win=False, pnl_pct=-1.0)
        entry = self.lb._strategies["test_strat"]
        self.assertEqual(entry["trades"], 2)
        self.assertEqual(entry["wins"], 1)
        self.assertAlmostEqual(entry["total_pnl"], 1.5)
        # Sprint 20: record_outcome now calls update() → blended_score
        self.assertIn("blended_score", entry)

    def test_20_lifecycle_cooldown(self):
        """Very low score with enough trades → COOLDOWN."""
        metrics = {
            "oos_sharpe": 0.0,
            "expectancy": 0.0,
            "calmar_ratio": 0.0,
            "win_rate": 0.1,
            "profit_factor": 0.0,
            "max_drawdown": 0.25,
            "consistency": 0.0,
            "trade_count": 25,
        }
        entry = self.lb.update("failing", metrics)
        self.assertEqual(entry["status"], StrategyStatus.COOLDOWN)

    def test_21_lifecycle_reduced(self):
        """Mediocre score with enough trades → REDUCED."""
        metrics = {
            "oos_sharpe": 0.5,
            "expectancy": 0.3,
            "calmar_ratio": 0.5,
            "win_rate": 0.35,
            "profit_factor": 0.5,
            "max_drawdown": 0.12,
            "consistency": 0.3,
            "trade_count": 25,
        }
        entry = self.lb.update("mediocre", metrics)
        self.assertIn(entry["status"], [StrategyStatus.REDUCED, StrategyStatus.COOLDOWN])

    def test_22_get_strategy_scores(self):
        """get_strategy_scores returns name→score map."""
        self.lb.update("alpha", {"oos_sharpe": 1.0, "win_rate": 0.6, "trade_count": 5})
        scores = self.lb.get_strategy_scores()
        self.assertIn("alpha", scores)
        self.assertIsInstance(scores["alpha"], float)

    def test_23_score_weights_sum(self):
        """SCORE_WEIGHTS values should sum close to 1.0."""
        total = sum(self.lb.SCORE_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=2)


# ═════════════════════════════════════════════════════════════════════
# 4. EDGE CALCULATOR TESTS
# ═════════════════════════════════════════════════════════════════════
class TestEdgeCalculator(unittest.TestCase):

    def setUp(self):
        self.ec = EdgeCalculator()

    def _make_signal(self, strategy="momentum_breakout"):
        """Create a minimal Signal-like mock."""
        sig = MagicMock()
        sig.strategy_id = strategy
        return sig

    def _make_regime(self, risk="NEUTRAL", vol="NORMAL", trend="NEUTRAL"):
        """Create a minimal MarketRegime-like mock."""
        r = MagicMock()
        r.risk = models_mod.RiskRegime(risk)
        r.volatility = models_mod.VolatilityRegime(vol)
        r.trend = models_mod.TrendRegime(trend)
        return r

    def test_24_base_rate_fallback(self):
        """With no calibration, returns base-rate values."""
        sig = self._make_signal("vcp")
        regime = self._make_regime()
        result = self.ec.compute(sig, regime, {})
        self.assertAlmostEqual(result.p_t1, 0.58, places=2)
        self.assertEqual(result.sample_size, 0)

    def test_25_risk_on_uptrend_boosts(self):
        """RISK_ON + UPTREND should boost p_t1."""
        sig = self._make_signal("momentum_breakout")
        base_regime = self._make_regime()
        boosted_regime = self._make_regime(risk="RISK_ON", trend="UPTREND")
        base_result = self.ec.compute(sig, base_regime, {})
        boosted_result = self.ec.compute(sig, boosted_regime, {})
        self.assertGreater(boosted_result.p_t1, base_result.p_t1)

    def test_26_risk_off_penalises(self):
        """RISK_OFF should lower p_t1."""
        sig = self._make_signal("trend_following")
        neutral = self._make_regime()
        risk_off = self._make_regime(risk="RISK_OFF")
        n_result = self.ec.compute(sig, neutral, {})
        r_result = self.ec.compute(sig, risk_off, {})
        self.assertLess(r_result.p_t1, n_result.p_t1)

    def test_27_high_vol_extends_days(self):
        """HIGH_VOL adds +3 days to expected holding."""
        sig = self._make_signal("vcp")
        normal = self._make_regime()
        high_vol = self._make_regime(vol="HIGH_VOL")
        n_res = self.ec.compute(sig, normal, {})
        hv_res = self.ec.compute(sig, high_vol, {})
        self.assertGreater(hv_res.expected_holding_days, n_res.expected_holding_days)

    def test_28_high_rel_volume_boost(self):
        """relative_volume >= 2.0 boosts p_t1."""
        sig = self._make_signal("momentum_breakout")
        regime = self._make_regime()
        normal = self.ec.compute(sig, regime, {"relative_volume": 1.0})
        boosted = self.ec.compute(sig, regime, {"relative_volume": 2.5})
        self.assertGreater(boosted.p_t1, normal.p_t1)

    def test_29_mean_reversion_oversold(self):
        """Mean reversion with low RSI gets p_t1 boost."""
        sig = self._make_signal("mean_reversion")
        regime = self._make_regime()
        normal = self.ec.compute(sig, regime, {"rsi_14": 50})
        oversold = self.ec.compute(sig, regime, {"rsi_14": 25})
        self.assertGreater(oversold.p_t1, normal.p_t1)

    def test_30_calibration_override(self):
        """When calibration data has sample_size >= 30, use it."""
        self.ec.load_calibration([{
            "calibration_bucket": "vcp|NEUTRAL|NORMAL",
            "sample_size": 50,
            "p_t1": 0.70,
            "p_t2": 0.45,
            "p_stop": 0.25,
            "expected_return_pct": 3.5,
            "expected_mae_pct": -0.8,
            "expected_holding_days": 6,
        }])
        sig = self._make_signal("vcp")
        regime = self._make_regime()
        result = self.ec.compute(sig, regime, {})
        self.assertAlmostEqual(result.p_t1, 0.70)
        self.assertEqual(result.sample_size, 50)

    def test_31_unknown_strategy_uses_default(self):
        """Unknown strategy falls back to DEFAULT_RATE."""
        sig = self._make_signal("alien_strategy")
        regime = self._make_regime()
        result = self.ec.compute(sig, regime, {})
        self.assertAlmostEqual(result.p_t1, 0.50, places=2)

    def test_32_ev_positive_property(self):
        """EdgeModel.ev_positive is True when EV > 0."""
        sig = self._make_signal("vcp")
        regime = self._make_regime()
        result = self.ec.compute(sig, regime, {})
        self.assertTrue(result.ev_positive)  # vcp base ev=1.0


# ═════════════════════════════════════════════════════════════════════
# 5. CONTEXT ASSEMBLER TESTS
# ═════════════════════════════════════════════════════════════════════
class TestContextAssembler(unittest.TestCase):

    def test_33_instantiate_with_none_services(self):
        """ContextAssembler can be instantiated with None services."""
        ca = ContextAssembler(
            market_data_service=None,
            broker_manager=None,
            news_service=None,
        )
        self.assertIsNotNone(ca)
        self.assertTrue(hasattr(ca, "assemble"))

    def test_34_assemble_returns_required_keys(self):
        """assemble() returns dict with all required context keys."""
        import asyncio
        ca = ContextAssembler(
            market_data_service=None,
            broker_manager=None,
            news_service=None,
        )
        result = asyncio.run(ca.assemble(tickers=["AAPL"]))
        for key in ["market_state", "portfolio_state", "news_by_ticker",
                     "sentiment", "calendar_events", "timestamp"]:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_35_assemble_no_tickers(self):
        """assemble(None) still returns valid context."""
        import asyncio
        ca = ContextAssembler(
            market_data_service=None,
            broker_manager=None,
            news_service=None,
        )
        result = asyncio.run(ca.assemble(tickers=None))
        self.assertIn("timestamp", result)
        self.assertIsInstance(result["market_state"], dict)


# ═════════════════════════════════════════════════════════════════════
# 6. INTEGRATION / CROSS-MODULE TESTS
# ═════════════════════════════════════════════════════════════════════
class TestCrossModule(unittest.TestCase):

    def test_36_leaderboard_scores_feed_ensembler(self):
        """Leaderboard strategy_scores can be passed to ensembler."""
        lb = StrategyLeaderboard()
        lb.update("momentum_breakout", {"oos_sharpe": 1.5, "win_rate": 0.6, "trade_count": 5})
        lb.update("vcp", {"oos_sharpe": 1.0, "win_rate": 0.5, "trade_count": 5})
        scores = lb.get_strategy_scores()

        ens = OpportunityEnsembler()
        signals = [
            {"ticker": "AAPL", "direction": "LONG", "strategy_name": "momentum_breakout",
             "confidence": 75, "expected_return_pct": 5.0, "risk_reward": 3.0},
            {"ticker": "TSLA", "direction": "LONG", "strategy_name": "vcp",
             "confidence": 65, "expected_return_pct": 4.0, "risk_reward": 2.5},
        ]
        ranked = ens.rank_opportunities(
            signals=signals,
            regime_state={"risk_on_uptrend": 0.5, "neutral_range": 0.3, "risk_off_downtrend": 0.2},
            portfolio_state={},
            strategy_scores=scores,
        )
        self.assertEqual(len(ranked), 2)
        self.assertTrue(all("composite_score" in r for r in ranked))

    def test_37_sizing_multiplier_affects_decision(self):
        """Leaderboard sizing multiplier reflects status."""
        lb = StrategyLeaderboard()
        lb.update("strong", {
            "oos_sharpe": 2.0, "win_rate": 0.7, "calmar_ratio": 2.5,
            "profit_factor": 2.5, "max_drawdown": 0.05, "consistency": 0.8,
            "expectancy": 1.5, "trade_count": 25,
        })
        lb.update("weak", {
            "oos_sharpe": 0.0, "win_rate": 0.1, "calmar_ratio": 0.0,
            "profit_factor": 0.0, "max_drawdown": 0.25, "consistency": 0.0,
            "expectancy": 0.0, "trade_count": 25,
        })
        self.assertEqual(lb.get_sizing_multiplier("strong"), 1.0)
        self.assertEqual(lb.get_sizing_multiplier("weak"), 0.0)


if __name__ == "__main__":
    unittest.main()
