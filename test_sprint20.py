"""
Sprint 20 — Deep Integration Fixes

Tests:
  1.  Position dataclass has `direction` field + `side`/`qty` aliases
  2.  MarketRegime has `strategy_weights` field
  3.  auto_trading_engine uses `place_order` (no `submit_order`)
  4.  auto_trading_engine uses `quantity` with `qty` fallback (no bare qty)
  5.  ContextAssembler._get_portfolio_state returns positions_by_ticker
  6.  RiskModel.filter_and_size handles list-of-Position portfolio
  7.  _execute_signal returns strategy_name + entry_snapshot
  8.  record_outcome produces blended_score (calls update())
  9.  StandardScaler not fit before CV split in trade_learner
  10. _record_learning_outcome does NOT hardcode direction="LONG"
  11. Circuit breaker update called with trade_pnl in _monitor_positions
  12. ContextAssembler constructed with service injection
  13. strategy_id → strategy_name fallback in signal dict
  14. graceful_shutdown uses place_order + quantity fallback
"""
import sys
import os
import re
import ast
import unittest
import importlib.util
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

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
    """Return full path for a file relative to ROOT."""
    return os.path.join(ROOT, path)


def _read(path):
    """Read file content from ROOT-relative path."""
    with open(_src(path)) as f:
        return f.read()


# ═════════════════════════════════════════════════════════════════════
# 1. POSITION DTO — direction field + side/qty aliases
# ═════════════════════════════════════════════════════════════════════
class TestPositionDTO(unittest.TestCase):
    """Verify Position dataclass has direction, side, qty."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("src.brokers.base", "src/brokers/base.py")

    def test_01_position_has_direction_field(self):
        """Position must have a 'direction' field defaulting to 'long'."""
        pos = self.mod.Position(
            ticker="AAPL", quantity=100, avg_price=150.0,
        )
        self.assertEqual(pos.direction, "long")

    def test_02_position_direction_short(self):
        """Position direction can be set to 'short'."""
        pos = self.mod.Position(
            ticker="TSLA", quantity=-50, avg_price=200.0,
            direction="short",
        )
        self.assertEqual(pos.direction, "short")

    def test_03_side_property_alias(self):
        """pos.side should equal pos.direction."""
        pos = self.mod.Position(
            ticker="AAPL", quantity=100, avg_price=150.0,
            direction="long",
        )
        self.assertEqual(pos.side, "long")

    def test_04_qty_property_alias(self):
        """pos.qty should equal pos.quantity."""
        pos = self.mod.Position(
            ticker="AAPL", quantity=42, avg_price=150.0,
        )
        self.assertEqual(pos.qty, 42)

    def test_05_backward_compat_update_price(self):
        """update_price still works after adding direction."""
        pos = self.mod.Position(
            ticker="AAPL", quantity=10, avg_price=100.0,
        )
        pos.update_price(110.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 100.0)


# ═════════════════════════════════════════════════════════════════════
# 2. MARKET REGIME — strategy_weights field
# ═════════════════════════════════════════════════════════════════════
class TestMarketRegimeWeights(unittest.TestCase):
    """Verify MarketRegime carries strategy_weights."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("src.core.models", "src/core/models.py")

    def test_06_strategy_weights_field_exists(self):
        """MarketRegime must have strategy_weights field."""
        from datetime import datetime, timezone
        regime = self.mod.MarketRegime(
            timestamp=datetime.now(timezone.utc),
            volatility="NORMAL",
            trend="NEUTRAL",
            risk="NEUTRAL",
            active_strategies=["momentum"],
        )
        self.assertIsInstance(regime.strategy_weights, dict)

    def test_07_strategy_weights_round_trip(self):
        """strategy_weights should persist values."""
        from datetime import datetime, timezone
        weights = {"momentum": 0.8, "mean_reversion": 0.3}
        regime = self.mod.MarketRegime(
            timestamp=datetime.now(timezone.utc),
            volatility="HIGH_VOL",
            trend="DOWNTREND",
            risk="RISK_OFF",
            active_strategies=["momentum", "mean_reversion"],
            strategy_weights=weights,
        )
        self.assertEqual(regime.strategy_weights["momentum"], 0.8)
        self.assertEqual(regime.strategy_weights["mean_reversion"], 0.3)


# ═════════════════════════════════════════════════════════════════════
# 3. NO submit_order IN AUTO_TRADING_ENGINE
# ═════════════════════════════════════════════════════════════════════
class TestNoSubmitOrder(unittest.TestCase):
    """All broker calls must use place_order, not submit_order."""

    def test_08_no_submit_order(self):
        """auto_trading_engine.py must not call submit_order."""
        src = _read("src/engines/auto_trading_engine.py")
        matches = re.findall(r'\.submit_order\s*\(', src)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} submit_order() calls — should be 0",
        )

    def test_09_uses_place_order(self):
        """auto_trading_engine.py must use place_order."""
        src = _read("src/engines/auto_trading_engine.py")
        matches = re.findall(r'\.place_order\s*\(', src)
        self.assertGreaterEqual(
            len(matches), 3,
            "Expected >= 3 place_order() calls "
            "(_execute_signal, _monitor_positions, graceful_shutdown)",
        )


# ═════════════════════════════════════════════════════════════════════
# 4. QUANTITY WITH QTY FALLBACK (no bare qty)
# ═════════════════════════════════════════════════════════════════════
class TestQuantityFallback(unittest.TestCase):
    """Engine must use getattr(pos, 'quantity', getattr(pos, 'qty', ...))."""

    def test_10_monitor_uses_quantity_first(self):
        """_monitor_positions must read quantity before qty."""
        src = _read("src/engines/auto_trading_engine.py")
        # Find getattr chains in the _monitor_positions area
        # The pattern should be getattr(pos, "quantity", getattr(pos, "qty"
        pattern = r'getattr\([^,]+,\s*["\']quantity["\']'
        matches = re.findall(pattern, src)
        self.assertGreaterEqual(
            len(matches), 2,
            "Expected >=2 getattr(*, 'quantity', ...) patterns",
        )

    def test_11_graceful_shutdown_uses_quantity_first(self):
        """graceful_shutdown must read quantity before qty."""
        src = _read("src/engines/auto_trading_engine.py")
        # Check shutdown section specifically
        shutdown_idx = src.index("async def graceful_shutdown")
        shutdown_src = src[shutdown_idx:]
        self.assertIn(
            '"quantity"', shutdown_src,
            "graceful_shutdown should reference 'quantity'",
        )


# ═════════════════════════════════════════════════════════════════════
# 5. CONTEXT ASSEMBLER — portfolio has positions_by_ticker
# ═════════════════════════════════════════════════════════════════════
class TestContextAssemblerPortfolio(unittest.TestCase):
    """_get_portfolio_state must return positions_by_ticker dict."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.context_assembler",
            "src/engines/context_assembler.py",
        )

    def test_12_no_broker_returns_empty_dict(self):
        """With no broker, positions_by_ticker should be empty dict."""
        ca = self.mod.ContextAssembler()
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(ca._get_portfolio_state())
        loop.close()
        self.assertIn("positions_by_ticker", state)
        self.assertIsInstance(state["positions_by_ticker"], dict)
        self.assertEqual(len(state["positions_by_ticker"]), 0)

    def test_13_with_broker_positions(self):
        """positions_by_ticker keyed by ticker from Position objects."""
        @dataclass
        class FakePos:
            ticker: str
            quantity: int
            current_price: float

        broker = MagicMock()
        broker.get_positions = MagicMock(return_value=[
            FakePos("AAPL", 100, 150.0),
            FakePos("MSFT", 50, 300.0),
        ])
        broker.get_account = MagicMock(return_value=None)

        ca = self.mod.ContextAssembler(broker_manager=broker)
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(ca._get_portfolio_state())
        loop.close()

        self.assertIn("AAPL", state["positions_by_ticker"])
        self.assertIn("MSFT", state["positions_by_ticker"])
        self.assertEqual(len(state["tickers"]), 2)

    def test_14_portfolio_has_equity_key(self):
        """Portfolio state must have equity key."""
        ca = self.mod.ContextAssembler()
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(ca._get_portfolio_state())
        loop.close()
        self.assertIn("equity", state)

    def test_15_context_assembler_accepts_services(self):
        """ContextAssembler __init__ accepts market_data_service, broker_manager, news_service."""
        import inspect
        sig = inspect.signature(self.mod.ContextAssembler.__init__)
        params = list(sig.parameters.keys())
        self.assertIn("market_data_service", params)
        self.assertIn("broker_manager", params)
        self.assertIn("news_service", params)


# ═════════════════════════════════════════════════════════════════════
# 6. RISK MODEL — handles list portfolio positions
# ═════════════════════════════════════════════════════════════════════
class TestRiskModelPortfolio(unittest.TestCase):
    """RiskModel.filter_and_size must handle both list and dict positions."""

    def test_16_signal_engine_has_positions_by_ticker(self):
        """signal_engine.py uses positions_by_ticker with fallback."""
        src = _read("src/engines/signal_engine.py")
        self.assertIn("positions_by_ticker", src)

    def test_17_handles_list_positions(self):
        """RiskModel code handles isinstance(pos_raw, list)."""
        src = _read("src/engines/signal_engine.py")
        self.assertIn("isinstance(pos_raw, list)", src)

    def test_18_handles_dict_positions(self):
        """RiskModel code handles isinstance(pos_raw, dict)."""
        src = _read("src/engines/signal_engine.py")
        self.assertIn("isinstance(pos_raw, dict)", src)


# ═════════════════════════════════════════════════════════════════════
# 7. _execute_signal RETURNS strategy_name + entry_snapshot
# ═════════════════════════════════════════════════════════════════════
class TestExecuteSignalReturn(unittest.TestCase):
    """_execute_signal return dict must include new fields."""

    def test_19_return_has_strategy_name(self):
        """Execution path must return strategy_name in dict."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _execute_recommendation")
        method_src = src[idx:idx + 2000]
        self.assertIn('"strategy_name"', method_src)

    def test_20_return_has_entry_snapshot(self):
        """Execution path must return entry_snapshot with market features."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _execute_recommendation")
        method_src = src[idx:idx + 4000]
        self.assertIn('"entry_snapshot"', method_src)
        # Snapshot fields live in TradeRecommendation / engine
        self.assertIn("vix_at_entry", src)
        self.assertIn("rsi_at_entry", src)
        self.assertIn("adx_at_entry", src)

    def test_21_return_has_confidence(self):
        """Execution path must return confidence."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _execute_recommendation")
        method_src = src[idx:idx + 4000]
        self.assertIn('"confidence"', method_src)


# ═════════════════════════════════════════════════════════════════════
# 8. LEADERBOARD — record_outcome calls update()
# ═════════════════════════════════════════════════════════════════════
class TestLeaderboardRecordOutcome(unittest.TestCase):
    """record_outcome must call update() to keep blended_score consistent."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.engines.strategy_leaderboard",
            "src/engines/strategy_leaderboard.py",
        )

    def test_22_record_outcome_updates_blended_score(self):
        """After record_outcome, strategy must have blended_score."""
        lb = self.mod.StrategyLeaderboard()
        lb.record_outcome("momentum_v1", True, 2.5)
        scores = lb.get_strategy_scores()
        self.assertIn("momentum_v1", scores)
        self.assertGreater(scores["momentum_v1"], 0)

    def test_23_record_outcome_calls_update(self):
        """record_outcome source must call self.update()."""
        src = _read("src/engines/strategy_leaderboard.py")
        idx = src.index("def record_outcome")
        method_src = src[idx:idx + 5000]
        self.assertIn("self.update(", method_src)

    def test_24_sizing_multiplier_after_record(self):
        """get_sizing_multiplier must work after record_outcome."""
        lb = self.mod.StrategyLeaderboard()
        lb.record_outcome("trend_v2", True, 1.0)
        mult = lb.get_sizing_multiplier("trend_v2")
        # Should be active (1.0) since only 1 trade < MIN_TRADES_FOR_EVAL
        self.assertEqual(mult, 1.0)

    def test_25_record_outcome_maintains_pnl_history(self):
        """record_outcome must track pnl_history list."""
        lb = self.mod.StrategyLeaderboard()
        lb.record_outcome("test_strat", True, 3.0)
        lb.record_outcome("test_strat", False, -1.0)
        lb.record_outcome("test_strat", True, 2.0)
        entry = lb._strategies["test_strat"]
        self.assertIn("pnl_history", entry)
        self.assertEqual(len(entry["pnl_history"]), 3)
        self.assertEqual(entry["trades"], 3)
        self.assertEqual(entry["wins"], 2)


# ═════════════════════════════════════════════════════════════════════
# 9. SCALER DATA LEAKAGE FIX
# ═════════════════════════════════════════════════════════════════════
class TestScalerLeakageFix(unittest.TestCase):
    """StandardScaler must be fit inside each CV fold, not before."""

    def test_26_fold_scaler_in_cv_loop(self):
        """trade_learner.py must create fold_scaler inside CV loop."""
        src = _read("src/ml/trade_learner.py")
        self.assertIn("fold_scaler", src)

    def test_27_no_scaler_fit_before_split(self):
        """No self.scaler.fit_transform(X) before the tscv.split loop."""
        src = _read("src/ml/trade_learner.py")
        # Find the train() method
        idx = src.index("def train(")
        method_src = src[idx:idx + 3000]
        # Find the tscv.split call position
        split_idx = method_src.index("tscv.split")
        before_split = method_src[:split_idx]
        # There should be no scaler.fit_transform before the split
        self.assertNotIn(
            "self.scaler.fit_transform(X)",
            before_split,
            "Scaler must not fit before CV split (data leakage)",
        )

    def test_28_no_unused_pipeline_import(self):
        """Pipeline import should be removed (unused)."""
        src = _read("src/ml/trade_learner.py")
        self.assertNotIn(
            "from sklearn.pipeline import Pipeline",
            src,
        )


# ═════════════════════════════════════════════════════════════════════
# 10. _record_learning_outcome — no hardcoded direction
# ═════════════════════════════════════════════════════════════════════
class TestLearningOutcome(unittest.TestCase):
    """_record_learning_outcome must derive direction from position."""

    def test_29_no_hardcoded_direction_long(self):
        """Must not hardcode direction='LONG' in record construction."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _record_learning_outcome")
        method_src = src[idx:idx + 2000]
        # The TradeOutcomeRecord construction should use _dir, not "LONG"
        # Find the TradeOutcomeRecord(...) block
        rec_idx = method_src.index("TradeOutcomeRecord(")
        rec_block = method_src[rec_idx:rec_idx + 500]
        self.assertIn(
            "direction=_dir",
            rec_block,
            "TradeOutcomeRecord should use _dir, not hardcode 'LONG'",
        )

    def test_30_uses_entry_snapshot(self):
        """_record_learning_outcome must look up entry_snapshot from _trades_today."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _record_learning_outcome")
        method_src = src[idx:idx + 2000]
        self.assertIn("entry_snapshot", method_src)
        self.assertIn("_trades_today", method_src)

    def test_31_confidence_from_snapshot(self):
        """confidence must come from snapshot, not hardcoded 50."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _record_learning_outcome")
        method_src = src[idx:idx + 3000]
        rec_idx = method_src.index("TradeOutcomeRecord(")
        rec_block = method_src[rec_idx:rec_idx + 1500]
        self.assertIn(
            "confidence=_conf",
            rec_block,
            "confidence should use _conf from snapshot lookup",
        )


# ═════════════════════════════════════════════════════════════════════
# 11. CIRCUIT BREAKER — trade_pnl in _monitor_positions
# ═════════════════════════════════════════════════════════════════════
class TestCircuitBreakerUpdate(unittest.TestCase):
    """circuit_breaker.update must be called with trade_pnl= on close."""

    def test_32_circuit_breaker_trade_pnl_in_monitor(self):
        """_monitor_positions must pass trade_pnl to circuit_breaker.update."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _monitor_positions")
        method_src = src[idx:idx + 5000]
        self.assertIn("trade_pnl=", method_src)
        self.assertIn("circuit_breaker.update(", method_src)


# ═════════════════════════════════════════════════════════════════════
# 12. CONTEXT ASSEMBLER INJECTION
# ═════════════════════════════════════════════════════════════════════
class TestContextAssemblerInjection(unittest.TestCase):
    """ContextAssembler constructed with service injection in engine."""

    def test_33_engine_injects_services(self):
        """Engine must pass market_data, broker, news to ContextAssembler."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("context_assembler = ContextAssembler(")
        block = src[idx:idx + 300]
        self.assertIn("market_data_service=", block)
        self.assertIn("broker_manager=", block)
        self.assertIn("news_service=", block)


# ═════════════════════════════════════════════════════════════════════
# 13. STRATEGY_ID → STRATEGY_NAME FALLBACK
# ═════════════════════════════════════════════════════════════════════
class TestStrategyIdFallback(unittest.TestCase):
    """Signal dict must resolve strategy_id → strategy_name → 'unknown'."""

    def test_34_strategy_id_in_signal_dict(self):
        """auto_trading_engine must reference strategy_id in signal dict."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn("strategy_id", src)

    def test_35_fallback_chain_exists(self):
        """Execution path must reference strategy_id and strategy_name."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _execute_recommendation")
        method_src = src[idx:idx + 2000]
        # Should reference strategy_id in the return dict
        self.assertIn("strategy_id", method_src)
        self.assertIn("strategy_name", method_src)
        # "unknown" fallback lives in from_signal / _calculate_position_size
        self.assertIn('"unknown"', src)


# ═════════════════════════════════════════════════════════════════════
# 14. GRACEFUL SHUTDOWN — place_order + quantity fallback
# ═════════════════════════════════════════════════════════════════════
class TestGracefulShutdown(unittest.TestCase):
    """graceful_shutdown must use place_order and direction fallback."""

    def test_36_shutdown_uses_place_order(self):
        """graceful_shutdown must call manager.place_order."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def graceful_shutdown")
        method_src = src[idx:]
        self.assertIn("place_order(", method_src)
        self.assertNotIn("submit_order(", method_src)

    def test_37_shutdown_uses_direction(self):
        """graceful_shutdown must read direction with side fallback."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def graceful_shutdown")
        method_src = src[idx:]
        self.assertIn('"direction"', method_src)

    def test_38_shutdown_uses_ordersideordertype(self):
        """graceful_shutdown must use OrderSide and OrderType enums."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def graceful_shutdown")
        method_src = src[idx:]
        self.assertIn("OrderSide.", method_src)
        self.assertIn("OrderType.MARKET", method_src)


# ═════════════════════════════════════════════════════════════════════
# 15. SIGNAL ENGINE — strategy_weights preserved
# ═════════════════════════════════════════════════════════════════════
class TestSignalEngineWeights(unittest.TestCase):
    """RegimeDetector must pass strategy_weights to MarketRegime."""

    def test_39_strategy_weights_in_regime_constructor(self):
        """signal_engine.py must pass strategy_weights= to MarketRegime."""
        src = _read("src/engines/signal_engine.py")
        self.assertIn("strategy_weights=strategy_weights", src)

    def test_40_strategy_weights_computed(self):
        """strategy_weights must be computed from _get_active_strategies."""
        src = _read("src/engines/signal_engine.py")
        self.assertIn(
            "strategy_weights = self._get_active_strategies",
            src,
        )


if __name__ == "__main__":
    unittest.main()
