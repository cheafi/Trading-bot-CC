"""
Sprint 27 — Short Selling Pipeline + Performance Tracker DB

Tests:
 1-4   OrderSide enum has SELL_SHORT / BUY_TO_COVER
 5-9   Position (base.py) direction-aware P&L
 10-14 PaperBroker handles short positions
 15-20 PositionManager direction-aware exits & P&L
 21-24 Engine maps direction → correct order side
 25-28 PerformanceTracker DB stubs implemented
"""
import importlib
import importlib.util
import pathlib
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

ROOT = pathlib.Path(__file__).resolve().parent

# ── Stubs ──────────────────────────────────────────────────────
_DB_STUB = MagicMock()
_DB_STUB.check_database_health = AsyncMock(return_value=True)
for _m in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio", "sqlalchemy.dialects",
    "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "tenacity",
]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()
if "src.core.database" not in sys.modules:
    sys.modules["src.core.database"] = _DB_STUB


def _load(name, rel_path):
    p = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(rel):
    return (ROOT / rel).read_text()


# ── 1-4: OrderSide enum ───────────────────────────────────────

class TestOrderSideEnum(unittest.TestCase):
    """Tests 1-4: OrderSide has short-selling members."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("src.brokers.base", "src/brokers/base.py")

    def test_01_sell_short_exists(self):
        """OrderSide.SELL_SHORT is defined."""
        self.assertTrue(hasattr(self.mod.OrderSide, "SELL_SHORT"))
        self.assertEqual(self.mod.OrderSide.SELL_SHORT.value, "sell_short")

    def test_02_buy_to_cover_exists(self):
        """OrderSide.BUY_TO_COVER is defined."""
        self.assertTrue(hasattr(self.mod.OrderSide, "BUY_TO_COVER"))
        self.assertEqual(
            self.mod.OrderSide.BUY_TO_COVER.value, "buy_to_cover",
        )

    def test_03_original_sides_intact(self):
        """BUY and SELL still work."""
        self.assertEqual(self.mod.OrderSide.BUY.value, "buy")
        self.assertEqual(self.mod.OrderSide.SELL.value, "sell")

    def test_04_four_members(self):
        """OrderSide has exactly 4 members."""
        self.assertEqual(len(self.mod.OrderSide), 4)


# ── 5-9: Position direction-aware P&L (base.py) ──────────────

class TestPositionDirectionPnL(unittest.TestCase):
    """Tests 5-9: Position.update_price handles direction."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("src.brokers.base", "src/brokers/base.py")

    def _make_pos(self, direction, qty, avg_price, current_price=0):
        return self.mod.Position(
            ticker="TEST",
            quantity=qty,
            avg_price=avg_price,
            current_price=current_price or avg_price,
            direction=direction,
        )

    def test_05_long_pnl_positive(self):
        """Long position: price up → positive P&L."""
        pos = self._make_pos("long", 100, 50.0)
        pos.update_price(55.0)
        self.assertGreater(pos.unrealized_pnl, 0)
        self.assertAlmostEqual(pos.unrealized_pnl, 500.0, places=1)

    def test_06_long_pnl_negative(self):
        """Long position: price down → negative P&L."""
        pos = self._make_pos("long", 100, 50.0)
        pos.update_price(45.0)
        self.assertLess(pos.unrealized_pnl, 0)

    def test_07_short_pnl_positive(self):
        """Short position: price down → positive P&L."""
        pos = self._make_pos("short", -100, 50.0)
        pos.update_price(45.0)
        self.assertGreater(pos.unrealized_pnl, 0)
        self.assertAlmostEqual(pos.unrealized_pnl, 500.0, places=1)

    def test_08_short_pnl_negative(self):
        """Short position: price up → negative P&L."""
        pos = self._make_pos("short", -100, 50.0)
        pos.update_price(55.0)
        self.assertLess(pos.unrealized_pnl, 0)

    def test_09_short_pnl_pct(self):
        """Short position P&L percentage is correct."""
        pos = self._make_pos("short", -50, 100.0)
        pos.update_price(90.0)
        # 10% gain for short sold at 100, now at 90
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 10.0, places=0)


# ── 10-14: PaperBroker short orders ──────────────────────────

class TestPaperBrokerShorts(unittest.TestCase):
    """Tests 10-14: PaperBroker handles SELL_SHORT / BUY_TO_COVER."""

    @classmethod
    def setUpClass(cls):
        # Stub market data so get_quote returns a simple Quote
        for m in [
            "src.ingestors", "src.ingestors.base",
            "src.ingestors.market_data",
        ]:
            if m not in sys.modules:
                sys.modules[m] = MagicMock()

        # Force-reload broker modules to pick up SELL_SHORT/BUY_TO_COVER
        for m in ["src.brokers.base", "src.brokers.paper_broker"]:
            sys.modules.pop(m, None)

        cls.base_mod = _load("src.brokers.base", "src/brokers/base.py")
        cls.mod = _load(
            "src.brokers.paper_broker", "src/brokers/paper_broker.py",
        )

    def _run(self, coro):
        """Run async code safely across Python 3.10-3.13."""
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_broker(self, cash=100_000):
        from src.brokers.paper_broker import PaperBroker, SlippageModel
        broker = PaperBroker(
            initial_cash=cash,
            slippage=SlippageModel(base_bps=0, max_bps=0),
            latency_ms=0,
        )
        # Patch get_quote to return a simple price
        async def fake_quote(ticker, market=None):
            return self.base_mod.Quote(
                ticker=ticker, price=50.0, bid=49.95, ask=50.05,
            )
        broker.get_quote = fake_quote
        return broker

    def test_10_sell_short_opens_position(self):
        """SELL_SHORT creates a short position with negative qty."""
        broker = self._make_broker()
        req = self.base_mod.OrderRequest(
            ticker="AAPL",
            side=self.base_mod.OrderSide.SELL_SHORT,
            quantity=100,
            order_type=self.base_mod.OrderType.MARKET,
        )
        result = self._run(
            broker.place_order(req),
        )
        self.assertTrue(result.success)
        self.assertIn("AAPL", broker._positions)
        pos = broker._positions["AAPL"]
        self.assertEqual(pos.direction, "short")
        self.assertLess(pos.quantity, 0)

    def test_11_buy_to_cover_closes_short(self):
        """BUY_TO_COVER closes a short position and calculates P&L."""
        broker = self._make_broker()

        # Open short at ~50
        short_req = self.base_mod.OrderRequest(
            ticker="TSLA",
            side=self.base_mod.OrderSide.SELL_SHORT,
            quantity=50,
            order_type=self.base_mod.OrderType.MARKET,
        )
        self._run(
            broker.place_order(short_req),
        )
        self.assertIn("TSLA", broker._positions)

        # Cover at same price → ~zero P&L
        cover_req = self.base_mod.OrderRequest(
            ticker="TSLA",
            side=self.base_mod.OrderSide.BUY_TO_COVER,
            quantity=50,
            order_type=self.base_mod.OrderType.MARKET,
        )
        result = self._run(
            broker.place_order(cover_req),
        )
        self.assertTrue(result.success)
        self.assertNotIn("TSLA", broker._positions)

    def test_12_short_pnl_recorded(self):
        """Short trade P&L appears in trade history."""
        broker = self._make_broker()

        short_req = self.base_mod.OrderRequest(
            ticker="META",
            side=self.base_mod.OrderSide.SELL_SHORT,
            quantity=10,
            order_type=self.base_mod.OrderType.MARKET,
        )
        self._run(
            broker.place_order(short_req),
        )

        cover_req = self.base_mod.OrderRequest(
            ticker="META",
            side=self.base_mod.OrderSide.BUY_TO_COVER,
            quantity=10,
            order_type=self.base_mod.OrderType.MARKET,
        )
        self._run(
            broker.place_order(cover_req),
        )

        trades = broker.get_trade_history()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], "buy_to_cover")

    def test_13_sell_short_rejects_when_long(self):
        """Can't short a ticker that is already held long."""
        broker = self._make_broker()

        # Buy long first
        buy_req = self.base_mod.OrderRequest(
            ticker="GOOG",
            side=self.base_mod.OrderSide.BUY,
            quantity=10,
            order_type=self.base_mod.OrderType.MARKET,
        )
        self._run(
            broker.place_order(buy_req),
        )

        # Now try to short — should fail
        short_req = self.base_mod.OrderRequest(
            ticker="GOOG",
            side=self.base_mod.OrderSide.SELL_SHORT,
            quantity=10,
            order_type=self.base_mod.OrderType.MARKET,
        )
        result = self._run(
            broker.place_order(short_req),
        )
        self.assertFalse(result.success)

    def test_14_cover_rejects_when_no_short(self):
        """BUY_TO_COVER fails when there's no short position."""
        broker = self._make_broker()

        cover_req = self.base_mod.OrderRequest(
            ticker="NVDA",
            side=self.base_mod.OrderSide.BUY_TO_COVER,
            quantity=10,
            order_type=self.base_mod.OrderType.MARKET,
        )
        result = self._run(
            broker.place_order(cover_req),
        )
        self.assertFalse(result.success)
        self.assertIn("No short position", result.message)


# ── 15-20: PositionManager direction-aware ────────────────────

class TestPositionManagerShorts(unittest.TestCase):
    """Tests 15-20: PositionManager handles short direction."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load(
            "src.algo.position_manager",
            "src/algo/position_manager.py",
        )

    def _make_mgr(self):
        return self.mod.PositionManager()

    def test_15_open_short_position(self):
        """open_position with direction='short' sets direction."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="AAPL", strategy_id="test",
            entry_price=150.0, shares=100,
            stop_loss_price=155.0,  # stop ABOVE entry for short
            direction="short",
        )
        self.assertEqual(pos.direction, "short")

    def test_16_short_r_targets_below_entry(self):
        """Short R-targets are below entry price."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="TSLA", strategy_id="test",
            entry_price=200.0, shares=50,
            stop_loss_price=210.0,
            direction="short",
        )
        # Risk per share = 10. Targets should be below.
        self.assertLess(pos.target_1r_price, 200.0)
        self.assertAlmostEqual(pos.target_1r_price, 190.0)
        self.assertAlmostEqual(pos.target_2r_price, 180.0)
        self.assertAlmostEqual(pos.target_3r_price, 170.0)

    def test_17_long_r_targets_above_entry(self):
        """Long R-targets are still above entry price."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="GOOG", strategy_id="test",
            entry_price=100.0, shares=50,
            stop_loss_price=95.0,
            direction="long",
        )
        self.assertGreater(pos.target_1r_price, 100.0)
        self.assertAlmostEqual(pos.target_1r_price, 105.0)

    def test_18_short_stop_triggers_above(self):
        """Short position stop triggers when price rises."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="SPY", strategy_id="test",
            entry_price=500.0, shares=10,
            stop_loss_price=510.0,
            direction="short",
        )
        # Price rises to 515 — above stop
        should_exit, reason = pos.check_exit_conditions(
            515.0, datetime.now(),
        )
        self.assertTrue(should_exit)
        self.assertEqual(reason, "stop_loss")

    def test_19_short_target_triggers_below(self):
        """Short position target triggers when price drops."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="QQQ", strategy_id="test",
            entry_price=400.0, shares=10,
            stop_loss_price=410.0,
            direction="short",
        )
        # Target 1R = 390. Price drops to 389.
        should_exit, reason = pos.check_exit_conditions(
            389.0, datetime.now(),
        )
        self.assertTrue(should_exit)
        self.assertEqual(reason, "partial_1r")

    def test_20_short_close_pnl_correct(self):
        """Short position realized P&L is positive on price drop."""
        mgr = self._make_mgr()
        pos = mgr.open_position(
            ticker="AMD", strategy_id="test",
            entry_price=100.0, shares=100,
            stop_loss_price=105.0,
            direction="short",
        )
        pos.close_position(90.0, datetime.now(), "take_profit")
        # Entry 100, exit 90, short → profit
        self.assertAlmostEqual(pos.realized_pnl, 1000.0)
        self.assertAlmostEqual(pos.realized_pnl_pct, 10.0)


# ── 21-24: Engine order side mapping ──────────────────────────

class TestEngineShortMapping(unittest.TestCase):
    """Tests 21-24: Engine maps direction to correct OrderSide."""

    @classmethod
    def setUpClass(cls):
        cls.src = _read("src/engines/auto_trading_engine.py")

    def test_21_short_maps_to_sell_short(self):
        """_execute_recommendation maps SHORT → SELL_SHORT."""
        self.assertIn("OrderSide.SELL_SHORT", self.src)
        # Find the mapping in _execute_recommendation
        idx = self.src.find("async def _execute_recommendation")
        block = self.src[idx:idx + 600]
        self.assertIn("SELL_SHORT", block)
        # Must NOT use plain SELL for shorts
        self.assertNotIn(
            "else OrderSide.SELL\n", block,
            "Engine still maps SHORT → SELL (not SELL_SHORT)",
        )

    def test_22_monitor_uses_buy_to_cover(self):
        """_monitor_positions closes shorts via BUY_TO_COVER."""
        self.assertIn("OrderSide.BUY_TO_COVER", self.src)

    def test_23_open_position_passes_direction(self):
        """Engine passes direction= to PositionManager.open_position."""
        self.assertIn('direction=', self.src)
        idx = self.src.find("self.position_mgr.open_position")
        block = self.src[idx:idx + 500]
        self.assertIn("direction=", block)

    def test_24_short_stop_above_entry(self):
        """Engine calculates stop above entry for shorts."""
        idx = self.src.find("_is_short")
        self.assertGreater(idx, 0)
        block = self.src[idx:idx + 800]
        self.assertIn("1 + trading_config.stop_loss_pct", block)


# ── 25-28: PerformanceTracker DB stubs ────────────────────────

class TestPerformanceTrackerDB(unittest.TestCase):
    """Tests 25-28: PerformanceTracker DB methods implemented."""

    @classmethod
    def setUpClass(cls):
        cls.src = _read("src/performance/performance_tracker.py")
        cls.mod = _load(
            "src.performance.performance_tracker",
            "src/performance/performance_tracker.py",
        )

    def test_25_save_signal_not_pass(self):
        """_save_signal is implemented (not a bare pass)."""
        idx = self.src.find("async def _save_signal")
        block = self.src[idx:idx + 200]
        # Should NOT be just 'pass'
        lines = [
            l.strip() for l in block.split("\n")
            if l.strip() and not l.strip().startswith("#")
            and not l.strip().startswith('"""')
        ]
        # Must have more than 2 lines (def + pass/docstring)
        self.assertGreater(len(lines), 3)

    def test_26_update_signal_not_pass(self):
        """_update_signal is implemented (not a bare pass)."""
        idx = self.src.find("async def _update_signal")
        block = self.src[idx:idx + 200]
        lines = [
            l.strip() for l in block.split("\n")
            if l.strip() and not l.strip().startswith("#")
            and not l.strip().startswith('"""')
        ]
        self.assertGreater(len(lines), 3)

    def test_27_load_from_db_not_pass(self):
        """load_from_db is implemented (not a bare pass)."""
        idx = self.src.find("async def load_from_db")
        block = self.src[idx:idx + 300]
        lines = [
            l.strip() for l in block.split("\n")
            if l.strip() and not l.strip().startswith("#")
            and not l.strip().startswith('"""')
        ]
        self.assertGreater(len(lines), 5)

    def test_28_save_uses_db_handle(self):
        """_save_signal calls self.db methods."""
        idx = self.src.find("async def _save_signal")
        block = self.src[idx:idx + 800]
        self.assertIn("self.db", block)
        self.assertIn("save_outcome", block)


if __name__ == "__main__":
    unittest.main()
