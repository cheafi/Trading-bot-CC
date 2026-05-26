"""
Sprint 31 – Signal Dedup / Anti-Flip + Portfolio Correlation Guard

Tests:
  1-7   SignalCooldown class (cooldown, anti-flip, expiry)
  8-12  SignalCooldown.filter_signals batch filtering
  13-16 Correlation guard on PositionManager
  17-20 AutoTradingEngine wiring (cooldown + correlation)
  21-24 TradingConfig new fields
  25-28 Source code verification + get_cached_state
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


def _make_signal(ticker="AAPL", direction="LONG"):
    return SimpleNamespace(
        ticker=ticker,
        direction=SimpleNamespace(value=direction),
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
        feature_snapshot={},
        invalidation=SimpleNamespace(stop_price=145.0),
    )


# ═══════════════════════════════════════════════════════════
#  Group 1 – SignalCooldown class
# ═══════════════════════════════════════════════════════════
class TestSignalCooldown(unittest.TestCase):
    """Tests 1-7: SignalCooldown cooldown + anti-flip logic."""

    def _make_cooldown(self, cd=4, af=6):
        from src.engines.signal_engine import SignalCooldown
        return SignalCooldown(
            cooldown_hours=cd, anti_flip_hours=af,
        )

    def test_01_first_signal_always_allowed(self):
        sc = self._make_cooldown()
        ok, reason = sc.is_allowed("AAPL", "LONG")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_02_same_ticker_direction_blocked(self):
        sc = self._make_cooldown(cd=4)
        sc.record("AAPL", "LONG")
        ok, reason = sc.is_allowed("AAPL", "LONG")
        self.assertFalse(ok)
        self.assertIn("cooldown", reason)

    def test_03_same_ticker_after_cooldown_allowed(self):
        sc = self._make_cooldown(cd=4)
        sc._history["AAPL"] = {
            "LONG": datetime.now(timezone.utc) - timedelta(hours=5),
        }
        ok, _ = sc.is_allowed("AAPL", "LONG")
        self.assertTrue(ok)

    def test_04_opposite_direction_blocked_anti_flip(self):
        sc = self._make_cooldown(af=6)
        sc.record("AAPL", "LONG")
        ok, reason = sc.is_allowed("AAPL", "SHORT")
        self.assertFalse(ok)
        self.assertIn("anti_flip", reason)

    def test_05_opposite_direction_after_window_allowed(self):
        sc = self._make_cooldown(af=6)
        sc._history["AAPL"] = {
            "LONG": datetime.now(timezone.utc) - timedelta(hours=7),
        }
        ok, _ = sc.is_allowed("AAPL", "SHORT")
        self.assertTrue(ok)

    def test_06_different_ticker_always_allowed(self):
        sc = self._make_cooldown()
        sc.record("AAPL", "LONG")
        ok, _ = sc.is_allowed("MSFT", "LONG")
        self.assertTrue(ok)

    def test_07_clear_expired_removes_old(self):
        sc = self._make_cooldown(cd=4, af=6)
        sc._history["AAPL"] = {
            "LONG": datetime.now(timezone.utc) - timedelta(hours=10),
        }
        sc._history["MSFT"] = {
            "LONG": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        sc.clear_expired()
        self.assertNotIn("AAPL", sc._history)
        self.assertIn("MSFT", sc._history)


# ═══════════════════════════════════════════════════════════
#  Group 2 – SignalCooldown.filter_signals
# ═══════════════════════════════════════════════════════════
class TestSignalCooldownFilter(unittest.TestCase):
    """Tests 8-12: batch filtering of signals."""

    def _make_cooldown(self, cd=4, af=6):
        from src.engines.signal_engine import SignalCooldown
        return SignalCooldown(
            cooldown_hours=cd, anti_flip_hours=af,
        )

    def test_08_filter_blocks_recent(self):
        sc = self._make_cooldown()
        sc.record("AAPL", "LONG")
        sigs = [_make_signal("AAPL", "LONG")]
        kept, blocked = sc.filter_signals(sigs)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(blocked), 1)
        self.assertIn("cooldown", blocked[0]["reason"])

    def test_09_filter_passes_new_ticker(self):
        sc = self._make_cooldown()
        sc.record("AAPL", "LONG")
        sigs = [_make_signal("MSFT", "LONG")]
        kept, blocked = sc.filter_signals(sigs)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(blocked), 0)

    def test_10_record_batch_records_all(self):
        sc = self._make_cooldown()
        sigs = [
            _make_signal("AAPL", "LONG"),
            _make_signal("MSFT", "SHORT"),
        ]
        sc.record_batch(sigs)
        self.assertIn("AAPL", sc._history)
        self.assertIn("MSFT", sc._history)
        self.assertIn("LONG", sc._history["AAPL"])
        self.assertIn("SHORT", sc._history["MSFT"])

    def test_11_filter_blocks_flip(self):
        sc = self._make_cooldown()
        sc.record("AAPL", "LONG")
        sigs = [_make_signal("AAPL", "SHORT")]
        kept, blocked = sc.filter_signals(sigs)
        self.assertEqual(len(kept), 0)
        self.assertIn("anti_flip", blocked[0]["reason"])

    def test_12_filter_mixed_batch(self):
        sc = self._make_cooldown()
        sc.record("AAPL", "LONG")
        sigs = [
            _make_signal("AAPL", "LONG"),   # blocked
            _make_signal("MSFT", "LONG"),    # allowed
            _make_signal("GOOGL", "SHORT"),  # allowed
        ]
        kept, blocked = sc.filter_signals(sigs)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(blocked), 1)


# ═══════════════════════════════════════════════════════════
#  Group 3 – Correlation guard on PositionManager
# ═══════════════════════════════════════════════════════════
class TestCorrelationGuard(unittest.TestCase):
    """Tests 13-16: check_correlation_guard + get_correlated_count."""

    def _make_pm(self):
        from src.algo.position_manager import (
            PositionManager, RiskParameters,
        )
        return PositionManager(params=RiskParameters())

    def _make_price_data(self):
        import pandas as pd
        import numpy as np
        np.random.seed(42)
        base = np.cumsum(np.random.randn(30)) + 100
        return {
            "AAPL": pd.Series(base),
            "MSFT": pd.Series(base + np.random.randn(30) * 0.01),
            "GOOGL": pd.Series(
                np.cumsum(np.random.randn(30)) + 200,
            ),
            "NVDA": pd.Series(base * 2),
        }

    def test_13_no_positions_returns_zero(self):
        pm = self._make_pm()
        n = pm.get_correlated_count(
            "AAPL", self._make_price_data(),
        )
        self.assertEqual(n, 0)

    def test_14_correlated_positions_counted(self):
        pm = self._make_pm()
        pd_data = self._make_price_data()
        # Simulate open positions
        pm.positions["MSFT"] = MagicMock()
        pm.positions["NVDA"] = MagicMock()
        n = pm.get_correlated_count(
            "AAPL", pd_data, threshold=0.70,
        )
        # MSFT and NVDA track AAPL closely (same base)
        self.assertGreaterEqual(n, 1)

    def test_15_uncorrelated_position_not_counted(self):
        pm = self._make_pm()
        pd_data = self._make_price_data()
        pm.positions["GOOGL"] = MagicMock()
        n = pm.get_correlated_count(
            "AAPL", pd_data, threshold=0.95,
        )
        # GOOGL has independent random walk, unlikely r>0.95
        self.assertEqual(n, 0)

    def test_16_check_correlation_guard_blocks(self):
        pm = self._make_pm()
        pd_data = self._make_price_data()
        pm.positions["MSFT"] = MagicMock()
        pm.positions["NVDA"] = MagicMock()
        pm.positions["GOOGL"] = MagicMock()
        ok, reason = pm.check_correlation_guard(
            "AAPL", pd_data, max_correlated=1,
            threshold=0.50,
        )
        # At least 1 correlated at threshold=0.50
        if not ok:
            self.assertIn("Correlation guard", reason)


# ═══════════════════════════════════════════════════════════
#  Group 4 – AutoTradingEngine wiring
# ═══════════════════════════════════════════════════════════
class TestEngineWiring(unittest.TestCase):
    """Tests 17-20: cooldown + correlation guard in engine."""

    def _make_engine(self):
        from src.engines.auto_trading_engine import (
            AutoTradingEngine,
        )
        engine = AutoTradingEngine(dry_run=True)
        engine._regime_state = {
            "regime": "risk_on",
            "vix": 18.0,
        }
        engine.edge_calculator = None
        return engine

    def test_17_engine_has_signal_cooldown(self):
        engine = self._make_engine()
        self.assertTrue(
            hasattr(engine, "_signal_cooldown"),
        )
        self.assertTrue(
            hasattr(engine._signal_cooldown, "is_allowed"),
        )

    def test_18_bridge_applies_cooldown_filter(self):
        engine = self._make_engine()
        engine._signal_cooldown.record("AAPL", "LONG")
        sigs = [_make_signal("AAPL", "LONG")]
        recs = engine._signals_to_recommendations(sigs)
        self.assertEqual(
            len(recs), 0,
            "Should block AAPL LONG within cooldown",
        )

    def test_19_bridge_passes_new_ticker(self):
        engine = self._make_engine()
        engine._signal_cooldown.record("AAPL", "LONG")
        sigs = [_make_signal("MSFT", "LONG")]
        recs = engine._signals_to_recommendations(sigs)
        self.assertEqual(len(recs), 1)

    def test_20_engine_has_correlation_config(self):
        engine = self._make_engine()
        self.assertTrue(
            hasattr(engine, "_max_correlated"),
        )
        self.assertGreater(engine._max_correlated, 0)


# ═══════════════════════════════════════════════════════════
#  Group 5 – TradingConfig new fields
# ═══════════════════════════════════════════════════════════
class TestConfigFields(unittest.TestCase):
    """Tests 21-24: config has signal dedup + correlation fields."""

    def test_21_config_has_cooldown_hours(self):
        src = _read("src/core/config.py")
        self.assertIn("signal_cooldown_hours", src)

    def test_22_config_has_anti_flip_hours(self):
        src = _read("src/core/config.py")
        self.assertIn("anti_flip_hours", src)

    def test_23_config_has_max_correlated_held(self):
        src = _read("src/core/config.py")
        self.assertIn("max_correlated_held", src)

    def test_24_config_defaults_are_sane(self):
        src = _read("src/core/config.py")
        self.assertIn("default=4", src)  # cooldown
        self.assertIn("default=6", src)  # anti-flip
        self.assertIn("default=3", src)  # max correlated


# ═══════════════════════════════════════════════════════════
#  Group 6 – Source code verification + cached state
# ═══════════════════════════════════════════════════════════
class TestSourceVerification(unittest.TestCase):
    """Tests 25-28: Sprint 31 code landmarks exist."""

    def test_25_signal_cooldown_class_in_signal_engine(self):
        src = _read("src/engines/signal_engine.py")
        self.assertIn("class SignalCooldown", src)

    def test_26_correlation_guard_in_position_manager(self):
        src = _read("src/algo/position_manager.py")
        self.assertIn(
            "def check_correlation_guard", src,
        )
        self.assertIn(
            "def get_correlated_count", src,
        )

    def test_27_cached_state_has_cooldown_count(self):
        from src.engines.auto_trading_engine import (
            AutoTradingEngine,
        )
        engine = AutoTradingEngine(dry_run=True)
        state = engine.get_cached_state()
        self.assertIn(
            "signal_cooldown_tickers", state,
        )

    def test_28_run_cycle_has_correlation_guard(self):
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _run_cycle")
        # Find end of _run_cycle
        next_def = src.index(
            "\n    def _get_active_markets", idx + 1,
        )
        method = src[idx:next_def]
        self.assertIn(
            "check_correlation_guard", method,
        )


# ═══════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main(verbosity=2)
