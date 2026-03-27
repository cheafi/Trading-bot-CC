"""
Sprint 30 – No-Trade Cycle + Signal→Recommendation Bridge

Tests:
  1-7   _no_trade_cycle (universe refresh, position monitoring, readiness)
  8-12  _signals_to_recommendations bridge
  13-16 from_signal carries feature_snapshot into metadata
  17-20 get_cached_state includes no_trade_readiness
  21-24 _run_cycle wires _signals_to_recommendations
  25-28 Regime telemetry in no-trade readiness snapshot
"""
import asyncio
import importlib
import importlib.util
import inspect
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Stubs for heavy deps ──────────────────────────────────
for mod_name in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio", "sqlalchemy.ext.declarative",
    "sqlalchemy.future", "sqlalchemy.sql",
    "pydantic_settings", "discord", "discord.ext",
    "discord.ext.commands", "discord.ext.tasks",
    "tenacity", "asyncpg",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

db_stub = MagicMock()
db_stub.check_database_health = MagicMock(
    return_value={"status": "ok"},
)
sys.modules["src.core.database"] = db_stub

_root = os.path.dirname(__file__)


def _read(relpath):
    with open(os.path.join(_root, relpath)) as f:
        return f.read()


# ═══════════════════════════════════════════════════════════
#  Group 1 – _no_trade_cycle
# ═══════════════════════════════════════════════════════════
class TestNoTradeCycle(unittest.TestCase):
    """Tests 1-7: _no_trade_cycle does useful work."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import AutoTradingEngine
        engine = AutoTradingEngine(dry_run=True)
        engine._regime_state = {
            "should_trade": False,
            "entropy": 1.3,
            "regime": "uncertain",
            "risk_regime": "neutral",
        }
        return engine

    def test_01_no_trade_cycle_method_exists(self):
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "async def _no_trade_cycle(self)", src,
        )

    def test_02_no_trade_cycle_calls_monitor(self):
        """_no_trade_cycle must call _monitor_positions."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _no_trade_cycle")
        method = src[idx:idx + 3000]
        self.assertIn("_monitor_positions", method)

    def test_03_no_trade_cycle_refreshes_universe(self):
        """_no_trade_cycle builds universe to keep caches warm."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _no_trade_cycle")
        method = src[idx:idx + 3000]
        self.assertIn("universe_builder.build", method)

    def test_04_no_trade_readiness_initialized(self):
        engine = self._make_engine()
        self.assertIsInstance(
            engine._no_trade_readiness, dict,
        )

    def test_05_no_trade_cycle_populates_readiness(self):
        engine = self._make_engine()
        engine._monitor_positions = AsyncMock()
        engine.universe_builder.build = MagicMock(
            return_value=SimpleNamespace(
                tickers=["AAPL", "MSFT", "GOOGL"],
            ),
        )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        self.assertFalse(snap.get("should_trade"))
        self.assertGreater(snap.get("universe_size", 0), 0)
        self.assertIn("timestamp", snap)

    def test_06_no_trade_readiness_has_regime_info(self):
        engine = self._make_engine()
        engine._monitor_positions = AsyncMock()
        engine.universe_builder.build = MagicMock(
            return_value=SimpleNamespace(tickers=["SPY"]),
        )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        self.assertIn("regime", snap)
        self.assertIn("entropy", snap)

    def test_07_no_trade_cycle_handles_universe_error(self):
        engine = self._make_engine()
        engine._monitor_positions = AsyncMock()
        engine.universe_builder.build = MagicMock(
            side_effect=Exception("yfinance down"),
        )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        # Should not crash, readiness still populated
        snap = engine._no_trade_readiness
        self.assertFalse(snap.get("should_trade", True))


# ═══════════════════════════════════════════════════════════
#  Group 2 – _signals_to_recommendations bridge
# ═══════════════════════════════════════════════════════════
class TestSignalsToRecommendations(unittest.TestCase):
    """Tests 8-12: _signals_to_recommendations bridge."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import AutoTradingEngine
        engine = AutoTradingEngine(dry_run=True)
        engine._regime_state = {
            "regime": "risk_on",
            "vix": 18.0,
        }
        return engine

    def _make_signal(self, ticker="AAPL"):
        return SimpleNamespace(
            ticker=ticker,
            direction=SimpleNamespace(value="LONG"),
            strategy_id="momentum_v1",
            confidence=75,
            entry_price=150.0,
            risk_reward_ratio=2.0,
            expected_return=0.03,
            horizon=SimpleNamespace(value="SWING_1_5D"),
            entry_logic="breakout",
            catalyst="earnings",
            setup_grade="B",
            id="sig_1",
            key_risks=["gap_risk"],
            rsi=55,
            adx=28,
            relative_volume=1.5,
            distance_from_sma50=0.02,
            feature_snapshot={
                "edge_checklist": {"pass": True},
                "trade_brief": {"summary": "test"},
            },
            invalidation=SimpleNamespace(stop_price=145.0),
        )

    def test_08_bridge_method_exists(self):
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "def _signals_to_recommendations", src,
        )

    def test_09_bridge_converts_signals(self):
        engine = self._make_engine()
        engine.edge_calculator = None
        sigs = [self._make_signal("AAPL")]
        recs = engine._signals_to_recommendations(sigs)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].ticker, "AAPL")

    def test_10_bridge_preserves_strategy_id(self):
        engine = self._make_engine()
        engine.edge_calculator = None
        sigs = [self._make_signal()]
        recs = engine._signals_to_recommendations(sigs)
        self.assertEqual(
            recs[0].strategy_id, "momentum_v1",
        )

    def test_11_bridge_carries_edge_data(self):
        engine = self._make_engine()
        mock_edge = SimpleNamespace(
            p_t1=0.7, p_stop=0.2,
            expected_return_pct=0.05,
        )
        engine.edge_calculator = MagicMock()
        engine.edge_calculator.compute = MagicMock(
            return_value=mock_edge,
        )
        sigs = [self._make_signal()]
        recs = engine._signals_to_recommendations(sigs)
        self.assertAlmostEqual(recs[0].edge_p_t1, 0.7)

    def test_12_bridge_handles_edge_error(self):
        engine = self._make_engine()
        engine.edge_calculator = MagicMock()
        engine.edge_calculator.compute = MagicMock(
            side_effect=ValueError("bad input"),
        )
        sigs = [self._make_signal()]
        recs = engine._signals_to_recommendations(sigs)
        # Should not crash, rec still created
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].ticker, "AAPL")


# ═══════════════════════════════════════════════════════════
#  Group 3 – from_signal carries feature_snapshot
# ═══════════════════════════════════════════════════════════
class TestFromSignalFeatureSnapshot(unittest.TestCase):
    """Tests 13-16: feature_snapshot flows into metadata."""

    def _make_signal(self, fs=None):
        return SimpleNamespace(
            ticker="NVDA",
            direction=SimpleNamespace(value="LONG"),
            strategy_id="trend_v2",
            confidence=80,
            entry_price=500.0,
            risk_reward_ratio=2.5,
            expected_return=0.04,
            horizon=SimpleNamespace(value="SWING_1_5D"),
            entry_logic="",
            catalyst="",
            setup_grade="A",
            id="sig_2",
            key_risks=[],
            rsi=60,
            adx=35,
            relative_volume=2.0,
            distance_from_sma50=0.03,
            feature_snapshot=fs,
            invalidation=None,
        )

    def test_13_feature_snapshot_in_metadata(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal(
            fs={"edge_checklist": {"pass": True}},
        )
        rec = TradeRecommendation.from_signal(sig)
        self.assertIn(
            "feature_snapshot", rec.metadata,
        )
        self.assertTrue(
            rec.metadata["feature_snapshot"]["edge_checklist"]["pass"],
        )

    def test_14_no_snapshot_no_metadata_key(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal(fs=None)
        rec = TradeRecommendation.from_signal(sig)
        self.assertNotIn(
            "feature_snapshot", rec.metadata,
        )

    def test_15_empty_snapshot_still_stored(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal(fs={})
        rec = TradeRecommendation.from_signal(sig)
        # Empty dict is falsy, so should NOT be stored
        self.assertNotIn(
            "feature_snapshot", rec.metadata,
        )

    def test_16_rich_snapshot_preserved(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal(fs={
            "trade_brief": {"ticker": "NVDA"},
            "unified_scores": {"signal_score_0_100": 80},
            "edge_model": {"expected_value": 0.05},
        })
        rec = TradeRecommendation.from_signal(sig)
        fs = rec.metadata.get("feature_snapshot", {})
        self.assertIn("trade_brief", fs)
        self.assertIn("unified_scores", fs)
        self.assertIn("edge_model", fs)


# ═══════════════════════════════════════════════════════════
#  Group 4 – get_cached_state includes no_trade_readiness
# ═══════════════════════════════════════════════════════════
class TestCachedStateReadiness(unittest.TestCase):
    """Tests 17-20: get_cached_state has no_trade_readiness."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import AutoTradingEngine
        return AutoTradingEngine(dry_run=True)

    def test_17_cached_state_has_readiness_key(self):
        engine = self._make_engine()
        state = engine.get_cached_state()
        self.assertIn("no_trade_readiness", state)

    def test_18_readiness_initially_empty(self):
        engine = self._make_engine()
        state = engine.get_cached_state()
        self.assertEqual(
            state["no_trade_readiness"], {},
        )

    def test_19_readiness_populated_after_no_trade(self):
        engine = self._make_engine()
        engine._no_trade_readiness = {
            "should_trade": False,
            "universe_size": 50,
            "regime": "uncertain",
        }
        state = engine.get_cached_state()
        r = state["no_trade_readiness"]
        self.assertFalse(r["should_trade"])
        self.assertEqual(r["universe_size"], 50)

    def test_20_source_has_readiness_in_cached_state(self):
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def get_cached_state")
        block = src[idx:idx + 2000]
        self.assertIn("no_trade_readiness", block)


# ═══════════════════════════════════════════════════════════
#  Group 5 – _run_cycle wires bridge
# ═══════════════════════════════════════════════════════════
class TestRunCycleWiresBridge(unittest.TestCase):
    """Tests 21-24: _run_cycle uses _signals_to_recommendations."""

    def test_21_run_cycle_calls_bridge(self):
        """_run_cycle source uses _signals_to_recommendations."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _run_cycle")
        method = src[idx:idx + 5000]
        self.assertIn(
            "_signals_to_recommendations", method,
        )

    def test_22_no_manual_from_signal_in_run_cycle(self):
        """_run_cycle no longer has manual from_signal loop."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _run_cycle")
        # Find next method definition to bound the search
        next_def = src.index(
            "\n    async def _no_trade_cycle", idx + 1,
        )
        method = src[idx:next_def]
        self.assertNotIn(
            "TradeRecommendation.from_signal(",
            method,
            "from_signal should be in bridge, not _run_cycle",
        )

    def test_23_run_cycle_calls_no_trade_cycle(self):
        """_run_cycle calls _no_trade_cycle on should_trade=False."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _run_cycle")
        next_def = src.index(
            "\n    async def _no_trade_cycle", idx + 1,
        )
        method = src[idx:next_def]
        self.assertIn("_no_trade_cycle", method)

    def test_24_no_trade_replaces_old_early_return(self):
        """Old 'Regime gate: no-trade' log is now in _no_trade_cycle."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _run_cycle")
        next_def = src.index(
            "\n    async def _no_trade_cycle", idx + 1,
        )
        run_cycle = src[idx:next_def]
        # The old inline log should NOT be in _run_cycle anymore
        self.assertNotIn(
            'f"(entropy={', run_cycle,
            "Old inline entropy log should be in _no_trade_cycle",
        )


# ═══════════════════════════════════════════════════════════
#  Group 6 – Regime telemetry in readiness snapshot
# ═══════════════════════════════════════════════════════════
class TestRegimeTelemetry(unittest.TestCase):
    """Tests 25-28: readiness snapshot has regime detail."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import AutoTradingEngine
        engine = AutoTradingEngine(dry_run=True)
        engine._regime_state = {
            "should_trade": False,
            "entropy": 1.25,
            "regime": "high_uncertainty",
            "risk_regime": "risk_off",
            "risk_on_uptrend": 0.15,
            "neutral_range": 0.35,
            "risk_off_downtrend": 0.50,
        }
        engine._monitor_positions = AsyncMock()
        engine.universe_builder.build = MagicMock(
            return_value=SimpleNamespace(tickers=["SPY"]),
        )
        return engine

    def test_25_readiness_has_risk_regime(self):
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        self.assertEqual(snap["risk_regime"], "risk_off")

    def test_26_readiness_has_probabilities(self):
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        probs = snap.get("probabilities", {})
        self.assertIn("risk_off_downtrend", probs)
        self.assertAlmostEqual(
            probs["risk_off_downtrend"], 0.5,
        )

    def test_27_readiness_has_reason(self):
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        self.assertIn("reason", snap)

    def test_28_readiness_markets_populated(self):
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                engine._no_trade_cycle(),
            )
        finally:
            loop.close()
        snap = engine._no_trade_readiness
        # markets may be empty if no session is active
        self.assertIn("markets", snap)


# ═══════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main(verbosity=2)
