"""
Sprint 42 — P1/P3 pro-trader hardening (2026).

  • Breakout requires a true close above the prior 20-day high.
  • Mean reversion uses per-ticker rolling z-score (with documented fallback).
  • BrokerManager auto-generates client_order_id and dedupes retries.
  • RiskCircuitBreaker persists state to Redis (round-trip via fake client).
"""

import asyncio
import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from src.strategies.breakout import BreakoutStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.brokers.broker_manager import BrokerManager, BrokerType
from src.brokers.base import OrderResult, OrderStatus, OrderSide, OrderType, Market
from src.engines.auto_trading_engine import RiskCircuitBreaker


# ─────────────────────────────────────────────────────────────────────────
# Breakout strictness
# ─────────────────────────────────────────────────────────────────────────
class TestBreakoutStrictness(unittest.TestCase):
    def _features(self, close: float, high_20d: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [close],
                "high_20d": [high_20d],
                "low_20d": [high_20d * 0.9],
                "relative_volume": [2.0],
                "atr_14": [close * 0.02],
                "bb_width": [0.025],
            },
            index=["AAPL"],
        )

    def test_near_miss_does_not_trigger_strict_breakout(self):
        strat = BreakoutStrategy()
        feats = self._features(close=99.5, high_20d=100.0)  # 0.5% below high
        sigs = strat.generate_signals(["AAPL"], feats, market_data={"vix": 15})
        self.assertEqual(len(sigs), 0, "Near-miss must not produce a breakout signal")

    def test_true_breakout_does_trigger(self):
        strat = BreakoutStrategy()
        feats = self._features(close=101.0, high_20d=100.0)  # genuine break
        sigs = strat.generate_signals(["AAPL"], feats, market_data={"vix": 15})
        self.assertEqual(len(sigs), 1)

    def test_legacy_buffer_mode_still_works(self):
        strat = BreakoutStrategy(config={"require_true_breakout": False})
        feats = self._features(close=99.5, high_20d=100.0)
        sigs = strat.generate_signals(["AAPL"], feats, market_data={"vix": 15})
        self.assertEqual(len(sigs), 1, "Back-compat near-miss path must still fire")


# ─────────────────────────────────────────────────────────────────────────
# Mean reversion: per-ticker z-score (snapshot fallback path)
# ─────────────────────────────────────────────────────────────────────────
class TestMeanReversionZScore(unittest.TestCase):
    def test_uses_supplied_per_ticker_zscore_when_available(self):
        strat = MeanReversionStrategy()
        # Snapshot frame with explicit per-ticker rolling z-score feature
        feats = pd.DataFrame(
            {
                "close": [100.0, 200.0],
                "sma_200": [90.0, 180.0],
                "sma_20": [105.0, 210.0],
                "rsi_14": [25.0, 28.0],
                "bb_lower": [95.0, 195.0],
                "return_21d": [-0.10, -0.12],
                "atr_14": [2.0, 4.0],
                "low_20d": [98.0, 195.0],
                "return_zscore_63d": [-2.5, -2.8],
            },
            index=["AAA", "BBB"],
        )
        sigs = strat.generate_signals(["AAA", "BBB"], feats, market_data={"vix": 18})
        # Both should be oversold under the per-ticker rolling z-score
        self.assertEqual(len(sigs), 2)


# ─────────────────────────────────────────────────────────────────────────
# Broker idempotency
# ─────────────────────────────────────────────────────────────────────────
class TestBrokerIdempotency(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mgr = BrokerManager()
        # Inject a fake broker that records calls
        fake = MagicMock()
        fake.place_order = AsyncMock(
            return_value=OrderResult(
                success=True,
                order_id="srv-1",
                status=OrderStatus.FILLED,
                filled_qty=10,
                avg_fill_price=100.0,
            )
        )
        self.fake = fake
        self.mgr._brokers[BrokerType.PAPER] = fake
        self.mgr._active_broker = BrokerType.PAPER

    async def test_explicit_client_order_id_dedupes_retries(self):
        coid = "test-coid-12345"
        r1 = await self.mgr.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            client_order_id=coid,
        )
        r2 = await self.mgr.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            client_order_id=coid,
        )
        # Broker must have been called exactly once
        self.assertEqual(self.fake.place_order.await_count, 1)
        self.assertEqual(r1.order_id, r2.order_id)

    async def test_auto_generated_ids_are_unique(self):
        await self.mgr.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=10,
        )
        await self.mgr.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=10,
        )
        # Distinct auto-generated client_order_ids -> two broker calls
        self.assertEqual(self.fake.place_order.await_count, 2)


# ─────────────────────────────────────────────────────────────────────────
# CB persistence round-trip
# ─────────────────────────────────────────────────────────────────────────
class TestCircuitBreakerPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_persist_and_restore_same_day(self):
        store = {}

        class FakeRedis:
            async def setex(self, key, ttl, val):
                store[key] = val

            async def get(self, key):
                return store.get(key)

        cb = RiskCircuitBreaker(max_daily_loss_pct=3.0)
        cb.update(equity=100_000.0)
        cb.update(equity=99_000.0, trade_pnl=-1_000.0)
        await cb.persist(FakeRedis())

        cb2 = RiskCircuitBreaker(max_daily_loss_pct=3.0)
        restored = await cb2.restore(FakeRedis())
        self.assertTrue(restored)
        self.assertEqual(cb2.daily_pnl, -1_000.0)
        self.assertEqual(cb2._sod_equity, 100_000.0)


# ─────────────────────────────────────────────────────────────────────────
# Correlation guard: returns-based, not price-based
# ─────────────────────────────────────────────────────────────────────────
class TestCorrelationGuardUsesReturns(unittest.TestCase):
    def test_two_drifting_uncorrelated_walks_are_not_flagged(self):
        import numpy as np
        from src.algo.position_manager import (
            PositionManager, Position, RiskParameters,
        )
        from datetime import datetime as _dt

        pm = PositionManager(RiskParameters(account_size=100_000))
        pm.positions["MSFT"] = Position(
            ticker="MSFT", strategy_id="x", entry_date=_dt.now()
        )
        # Two trending price series with independent shocks. Price-level
        # correlation will look high because both drift up; return-level
        # correlation will correctly read near zero.
        n = 200
        rng = np.random.default_rng(42)
        # Strong shared upward drift + independent daily noise
        drift = 0.003  # ~0.3% per day shared
        r1 = drift + rng.normal(0, 0.01, n)
        r2 = drift + rng.normal(0, 0.01, n)
        p1 = pd.Series(100 * np.exp(np.cumsum(r1)))
        p2 = pd.Series(100 * np.exp(np.cumsum(r2)))
        # Sanity: prices look highly correlated (both drift up), returns do not
        self.assertGreater(p1.corr(p2), 0.7)
        self.assertLess(abs(p1.pct_change().corr(p2.pct_change())), 0.3)
        # Therefore the guard (which now uses returns) must NOT flag them
        n_corr = pm.get_correlated_count(
            "AAPL", {"AAPL": p1, "MSFT": p2}, threshold=0.70
        )
        self.assertEqual(n_corr, 0)


if __name__ == "__main__":
    unittest.main()
