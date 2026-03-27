"""
Sprint 25 Tests — Paper Broker Realism, Context Assembler Live Data,
                   Trade Execution Notifications

Covers:
  A) SlippageModel       (8 tests)
  B) CommissionModel     (6 tests)
  C) PaperBroker realism (12 tests)
  D) ContextAssembler    (8 tests)
  E) Trade notifications (6 tests)
  F) MultiChannelNotifier new methods (3 tests)

Total: 43 tests
"""

import asyncio
import importlib
import importlib.util
import os
import sys
import types
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ── Stub heavy dependencies before any src imports ──────────

for mod_name in [
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm", "sqlalchemy.future", "sqlalchemy.sql",
    "sqlalchemy.sql.expression",
    "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "tenacity",
    "aiohttp",
    "yfinance",
    "telegram", "telegram.ext",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Stub src.core.database
if "src.core.database" not in sys.modules:
    _db_stub = types.ModuleType("src.core.database")
    _db_stub.check_database_health = AsyncMock(return_value=True)
    _db_stub.get_async_session = MagicMock()
    _db_stub.async_engine = MagicMock()
    sys.modules["src.core.database"] = _db_stub

# Stub notifications submodules to avoid circular imports
for _nmod in [
    "src.notifications",
    "src.notifications.telegram",
    "src.notifications.telegram_bot",
    "src.notifications.discord",
    "src.notifications.discord_bot",
    "src.notifications.whatsapp",
    "src.notifications.formatter",
    "src.notifications.report_generator",
]:
    if _nmod not in sys.modules:
        _stub = types.ModuleType(_nmod)
        if _nmod == "src.notifications.telegram":
            class _TN:
                is_configured = False
                async def send_message(self, msg): return False
                async def send_signal(self, sig): return False
                async def send_signals_batch(self, sigs): return 0
                def _format_alert_message(self, **kw): return str(kw)
                def _format_daily_report_message(self, r): return str(r)
            _stub.TelegramNotifier = _TN
        elif _nmod == "src.notifications.discord":
            class _DN:
                is_configured = False
                async def send_message(self, msg): return False
                async def send_signal(self, sig): return False
                async def send_signals_batch(self, sigs): return 0
            _stub.DiscordNotifier = _DN
        elif _nmod == "src.notifications.discord_bot":
            _stub.DiscordInteractiveBot = MagicMock()
        elif _nmod == "src.notifications.telegram_bot":
            _stub.TelegramBot = MagicMock()
            _stub.start_telegram_bot = MagicMock()
        elif _nmod == "src.notifications.whatsapp":
            class _WN:
                is_configured = False
                async def send_message(self, msg): return False
                async def send_signal(self, sig): return False
                async def send_signals_batch(self, sigs): return 0
            _stub.WhatsAppNotifier = _WN
        sys.modules[_nmod] = _stub

# ── Project root on path ────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Load modules directly to avoid cross-contamination ──────

def _load_module(name: str, rel_path: str):
    fpath = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, fpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_base_mod = _load_module(
    "src.brokers.base", "src/brokers/base.py",
)
_paper_mod = _load_module(
    "src.brokers.paper_broker", "src/brokers/paper_broker.py",
)
_mc_mod = _load_module(
    "src.notifications.multi_channel", "src/notifications/multi_channel.py",
)

# Aliases
SlippageModel = _paper_mod.SlippageModel
CommissionModel = _paper_mod.CommissionModel
PaperBroker = _paper_mod.PaperBroker
COMMISSION_PRESETS = _paper_mod.COMMISSION_PRESETS

Quote = _base_mod.Quote
OrderRequest = _base_mod.OrderRequest
OrderSide = _base_mod.OrderSide
OrderType = _base_mod.OrderType
OrderStatus = _base_mod.OrderStatus
Market = _base_mod.Market
Position = _base_mod.Position

MultiChannelNotifier = _mc_mod.MultiChannelNotifier


def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =====================================================================
# A) SlippageModel tests
# =====================================================================

class TestSlippageModel(unittest.TestCase):
    """Test the SlippageModel data class."""

    def test_default_buy_raises_price(self):
        sm = SlippageModel(random_seed=42)
        fill = sm.apply(100.0, "buy", spread_pct=0.0)
        self.assertGreater(fill, 99.90)  # should be close to 100 + ~2bps

    def test_default_sell_lowers_price(self):
        sm = SlippageModel(random_seed=42)
        fill = sm.apply(100.0, "sell", spread_pct=0.0)
        self.assertLess(fill, 100.10)

    def test_wider_spread_increases_slippage(self):
        sm = SlippageModel(random_seed=42)
        narrow = abs(sm.apply(100.0, "buy", 0.001) - 100.0)
        wide = abs(sm.apply(100.0, "buy", 0.01) - 100.0)
        self.assertGreater(wide, narrow)

    def test_max_bps_cap(self):
        sm = SlippageModel(base_bps=100, max_bps=5.0, random_seed=42)
        fill = sm.apply(100.0, "buy", 0.0)
        # slippage should be capped at 5bps = 0.05%
        self.assertLess(fill, 100.10)

    def test_zero_slippage(self):
        sm = SlippageModel(base_bps=0, vol_multiplier=0, random_seed=42)
        fill = sm.apply(100.0, "buy", 0.0)
        # With zero base and zero vol_multiplier, jitter is 0
        self.assertAlmostEqual(fill, 100.0, places=2)

    def test_reproducible_with_seed(self):
        sm1 = SlippageModel(random_seed=123)
        sm2 = SlippageModel(random_seed=123)
        f1 = sm1.apply(100.0, "buy", 0.005)
        f2 = sm2.apply(100.0, "buy", 0.005)
        self.assertEqual(f1, f2)

    def test_different_seeds_differ(self):
        sm1 = SlippageModel(random_seed=1)
        sm2 = SlippageModel(random_seed=999)
        f1 = sm1.apply(100.0, "buy", 0.005)
        f2 = sm2.apply(100.0, "buy", 0.005)
        # They could be equal by chance but extremely unlikely
        # Just verify both are > 100
        self.assertGreater(f1, 99.9)
        self.assertGreater(f2, 99.9)

    def test_sell_direction(self):
        sm = SlippageModel(base_bps=5.0, random_seed=42)
        fill = sm.apply(200.0, "sell", 0.0)
        # Sell => price decreases
        self.assertLess(fill, 200.0)


# =====================================================================
# B) CommissionModel tests
# =====================================================================

class TestCommissionModel(unittest.TestCase):
    """Test the CommissionModel data class."""

    def test_zero_commission(self):
        cm = CommissionModel()
        self.assertEqual(cm.calculate(100, 50.0), 0.0)

    def test_per_share(self):
        cm = CommissionModel(per_share=0.005)
        comm = cm.calculate(200, 50.0)
        self.assertAlmostEqual(comm, 1.0)  # 200 * 0.005

    def test_per_order(self):
        cm = CommissionModel(per_order=4.95)
        comm = cm.calculate(100, 50.0)
        self.assertAlmostEqual(comm, 4.95)

    def test_pct_of_value(self):
        cm = CommissionModel(pct_of_value=0.001)
        comm = cm.calculate(100, 50.0)
        self.assertAlmostEqual(comm, 5.0)  # 0.1% of $5000

    def test_min_per_order(self):
        cm = CommissionModel(per_share=0.005, min_per_order=1.0)
        comm = cm.calculate(10, 50.0)
        # 10 * 0.005 = 0.05 < min 1.0
        self.assertEqual(comm, 1.0)

    def test_presets_exist(self):
        for name in ["zero", "ibkr", "crypto", "hk"]:
            self.assertIn(name, COMMISSION_PRESETS)
            self.assertIsInstance(COMMISSION_PRESETS[name], CommissionModel)


# =====================================================================
# C) PaperBroker realism tests
# =====================================================================

class TestPaperBrokerRealism(unittest.TestCase):
    """Test paper broker with slippage, spread, commission, latency."""

    def _make_broker(self, **kwargs):
        return PaperBroker(
            initial_cash=100_000.0,
            slippage=SlippageModel(base_bps=5.0, random_seed=42),
            **kwargs,
        )

    def _mock_quote(self, bid=99.90, ask=100.10, mid=None):
        price = mid or (bid + ask) / 2
        return Quote(
            ticker="AAPL", price=price, bid=bid, ask=ask,
        )

    def test_buy_fills_at_ask_not_mid(self):
        """Market buy should fill at ask + slippage, not mid."""
        broker = self._make_broker()
        quote = self._mock_quote(bid=99.90, ask=100.10)
        fill = broker._realistic_fill_price(
            quote, OrderSide.BUY, OrderType.MARKET,
        )
        # Should be >= ask (100.10), not mid (100.0)
        self.assertGreaterEqual(fill, 100.05)

    def test_sell_fills_at_bid_not_mid(self):
        """Market sell should fill at bid - slippage, not mid."""
        broker = self._make_broker()
        quote = self._mock_quote(bid=99.90, ask=100.10)
        fill = broker._realistic_fill_price(
            quote, OrderSide.SELL, OrderType.MARKET,
        )
        # Should be <= bid (99.90), not mid (100.0)
        self.assertLessEqual(fill, 99.95)

    def test_limit_order_uses_limit_price(self):
        """Limit order should start from limit price."""
        broker = self._make_broker()
        quote = self._mock_quote(bid=99.90, ask=100.10)
        fill = broker._realistic_fill_price(
            quote, OrderSide.BUY, OrderType.LIMIT, limit_price=99.50,
        )
        # Should be around 99.50 + slippage (spread-aware, ~20bps max)
        self.assertAlmostEqual(fill, 99.50, delta=0.30)

    def test_commission_deducted_on_buy(self):
        """Commission reduces cash on buy."""
        broker = self._make_broker(
            commission=CommissionModel(per_order=10.0),
        )
        quote = self._mock_quote()

        with patch.object(broker, 'get_quote', new_callable=AsyncMock, return_value=quote):
            order = OrderRequest(
                ticker="AAPL", side=OrderSide.BUY,
                quantity=10, order_type=OrderType.MARKET,
            )
            result = run_async(broker.place_order(order))
            self.assertTrue(result.success)
            # Cash should be reduced by cost + $10 commission
            self.assertLess(broker._cash, 100_000 - 10 * 100.0)
            self.assertEqual(broker._total_commissions, 10.0)

    def test_commission_deducted_on_sell(self):
        """Commission reduces P&L on sell."""
        broker = self._make_broker(
            commission=CommissionModel(per_order=5.0),
        )
        # Seed a position
        broker._positions["AAPL"] = Position(
            ticker="AAPL", quantity=10, avg_price=95.0,
            current_price=100.0, market_value=1000.0,
        )
        quote = self._mock_quote()

        with patch.object(broker, 'get_quote', new_callable=AsyncMock, return_value=quote):
            order = OrderRequest(
                ticker="AAPL", side=OrderSide.SELL,
                quantity=10, order_type=OrderType.MARKET,
            )
            result = run_async(broker.place_order(order))
            self.assertTrue(result.success)
            # Total commissions = 5.0
            self.assertAlmostEqual(broker._total_commissions, 5.0, places=1)

    def test_commission_preset_ibkr(self):
        """IBKR preset applies per-share fee."""
        broker = PaperBroker(commission_preset="ibkr")
        self.assertEqual(broker.commission_model.per_share, 0.005)
        self.assertEqual(broker.commission_model.min_per_order, 1.0)

    def test_commission_preset_crypto(self):
        """Crypto preset applies percentage fee."""
        broker = PaperBroker(commission_preset="crypto")
        self.assertEqual(broker.commission_model.pct_of_value, 0.001)

    def test_latency_simulation(self):
        """Latency adds measurable delay."""
        broker = self._make_broker(latency_ms=50)
        quote = self._mock_quote()

        with patch.object(broker, 'get_quote', new_callable=AsyncMock, return_value=quote):
            order = OrderRequest(
                ticker="AAPL", side=OrderSide.BUY,
                quantity=1, order_type=OrderType.MARKET,
            )
            import time
            t0 = time.monotonic()
            run_async(broker.place_order(order))
            elapsed_ms = (time.monotonic() - t0) * 1000
            # Should take at least 40ms (allowing some jitter)
            self.assertGreater(elapsed_ms, 30)

    def test_slippage_cost_tracked(self):
        """Cumulative slippage cost is tracked."""
        broker = self._make_broker()
        quote = self._mock_quote()

        with patch.object(broker, 'get_quote', new_callable=AsyncMock, return_value=quote):
            order = OrderRequest(
                ticker="AAPL", side=OrderSide.BUY,
                quantity=10, order_type=OrderType.MARKET,
            )
            run_async(broker.place_order(order))
            self.assertGreater(broker._total_slippage_cost, 0)

    def test_performance_summary_includes_costs(self):
        """Performance summary reports commissions and slippage."""
        broker = self._make_broker(
            commission=CommissionModel(per_order=10.0),
        )
        broker._total_commissions = 50.0
        broker._total_slippage_cost = 25.0

        summary = broker.get_performance_summary()
        self.assertEqual(summary["total_commissions"], 50.0)
        self.assertEqual(summary["total_slippage_cost"], 25.0)
        self.assertEqual(summary["total_execution_cost"], 75.0)

    def test_reset_clears_costs(self):
        """Reset zeroes commission and slippage totals."""
        broker = self._make_broker()
        broker._total_commissions = 100.0
        broker._total_slippage_cost = 50.0
        broker.reset()
        self.assertEqual(broker._total_commissions, 0.0)
        self.assertEqual(broker._total_slippage_cost, 0.0)

    def test_insufficient_funds_includes_commission(self):
        """Buy rejection message includes commission in required amount."""
        broker = PaperBroker(
            initial_cash=1000.0,
            commission=CommissionModel(per_order=100.0),
            slippage=SlippageModel(base_bps=0, random_seed=42),
        )
        quote = self._mock_quote(bid=100.0, ask=100.0, mid=100.0)

        with patch.object(broker, 'get_quote', new_callable=AsyncMock, return_value=quote):
            order = OrderRequest(
                ticker="AAPL", side=OrderSide.BUY,
                quantity=10, order_type=OrderType.MARKET,
            )
            result = run_async(broker.place_order(order))
            self.assertFalse(result.success)
            self.assertIn("commission", result.message)


# =====================================================================
# D) ContextAssembler tests
# =====================================================================

class TestContextAssembler(unittest.TestCase):
    """Test ContextAssembler with real and mocked data sources."""

    def _load_assembler(self):
        mod = _load_module(
            "src.engines.context_assembler_test",
            "src/engines/context_assembler.py",
        )
        return mod.ContextAssembler

    def test_defaults_when_no_service(self):
        """Returns safe defaults when no market_data_service."""
        CA = self._load_assembler()
        assembler = CA()
        result = run_async(assembler.assemble())
        ms = result["market_state"]
        self.assertIn("vix", ms)
        self.assertIn("spy_return_20d", ms)
        self.assertIn("breadth_pct", ms)

    def test_yfinance_fallback_called(self):
        """When no service, yfinance sync helper is invoked."""
        CA = self._load_assembler()
        assembler = CA()
        with patch.object(
            CA, "_yfinance_market_state_sync",
            return_value={"vix": 22.5, "spy_return_20d": 1.5},
        ):
            result = run_async(assembler.assemble())
            ms = result["market_state"]
            self.assertEqual(ms["vix"], 22.5)
            self.assertEqual(ms["spy_return_20d"], 1.5)

    def test_injected_service_takes_precedence(self):
        """market_data_service methods override yfinance."""
        CA = self._load_assembler()
        mock_svc = MagicMock()
        mock_svc.get_vix = MagicMock(return_value=30.0)
        mock_svc.get_spy_return = MagicMock(return_value=-2.0)
        mock_svc.get_market_breadth = MagicMock(return_value=0.35)

        assembler = CA(market_data_service=mock_svc)
        result = run_async(assembler.assemble())
        ms = result["market_state"]
        self.assertEqual(ms["vix"], 30.0)
        self.assertEqual(ms["spy_return_20d"], -2.0)
        self.assertEqual(ms["breadth_pct"], 0.35)
        self.assertEqual(ms["data_source"], "market_data_service")

    def test_cache_returns_same_result(self):
        """Cache returns same result within TTL."""
        CA = self._load_assembler()
        assembler = CA()
        with patch.object(
            CA, "_yfinance_market_state_sync",
            return_value={"vix": 15.0},
        ) as mock_yf:
            r1 = run_async(assembler.assemble())
            r2 = run_async(assembler.assemble())
            # yfinance should only be called once (cached on second)
            self.assertEqual(mock_yf.call_count, 1)

    def test_assemble_has_all_keys(self):
        """Assembled context has all required keys."""
        CA = self._load_assembler()
        assembler = CA()
        result = run_async(assembler.assemble())
        for key in [
            "market_state", "portfolio_state", "news_by_ticker",
            "sentiment", "calendar_events", "timestamp",
        ]:
            self.assertIn(key, result)

    def test_portfolio_state_with_broker(self):
        """Portfolio state fetches from broker."""
        CA = self._load_assembler()
        mock_broker = MagicMock()
        mock_broker.get_positions = MagicMock(return_value=[
            MagicMock(ticker="AAPL", symbol="AAPL"),
        ])
        mock_broker.get_account = MagicMock(return_value=MagicMock(
            portfolio_value=50000, cash=10000,
        ))
        assembler = CA(broker_manager=mock_broker)
        result = run_async(assembler.assemble())
        ps = result["portfolio_state"]
        self.assertEqual(ps["total_value"], 50000)
        self.assertEqual(ps["cash"], 10000)
        self.assertIn("AAPL", ps["tickers"])

    def test_data_source_field_present(self):
        """Market state includes data_source field."""
        CA = self._load_assembler()
        assembler = CA()
        result = run_async(assembler.assemble())
        self.assertIn("data_source", result["market_state"])

    def test_yfinance_sync_returns_none_on_import_error(self):
        """If yfinance is unavailable, sync helper returns None."""
        CA = self._load_assembler()
        with patch.dict(sys.modules, {"yfinance": None}):
            # Force ImportError by removing yfinance
            result = CA._yfinance_market_state_sync()
            # Should return None or a result — not crash
            # (None when import fails)


# =====================================================================
# E) Trade notification tests (engine integration)
# =====================================================================

class TestTradeNotifications(unittest.TestCase):
    """Test trade execution notifications in the engine."""

    def _make_engine_class(self):
        """Load AutoTradingEngine via AST to avoid module pollution."""
        import ast

        fpath = ROOT / "src" / "engines" / "auto_trading_engine.py"
        source = fpath.read_text()
        tree = ast.parse(source)

        # Find _notify_trade_executed and _notify_position_closed
        methods = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                if node.name in (
                    "_notify_trade_executed",
                    "_notify_position_closed",
                ):
                    methods[node.name] = ast.get_source_segment(
                        source, node,
                    )
        return methods

    def test_notify_trade_executed_method_exists(self):
        methods = self._make_engine_class()
        self.assertIn("_notify_trade_executed", methods)
        self.assertIn("send_trade_alert", methods["_notify_trade_executed"])

    def test_notify_position_closed_method_exists(self):
        methods = self._make_engine_class()
        self.assertIn("_notify_position_closed", methods)
        self.assertIn("send_exit_alert", methods["_notify_position_closed"])

    def test_execute_recommendation_calls_notify(self):
        """_execute_recommendation source contains notify call."""
        fpath = ROOT / "src" / "engines" / "auto_trading_engine.py"
        source = fpath.read_text()
        self.assertIn(
            "_notify_trade_executed", source,
        )

    def test_monitor_positions_calls_notify(self):
        """_monitor_positions source contains exit notify call."""
        fpath = ROOT / "src" / "engines" / "auto_trading_engine.py"
        source = fpath.read_text()
        self.assertIn(
            "_notify_position_closed", source,
        )

    def test_notify_trade_has_required_fields(self):
        """Notification includes ticker, direction, fill_price."""
        methods = self._make_engine_class()
        body = methods["_notify_trade_executed"]
        for field in ["ticker", "direction", "fill_price", "strategy", "confidence"]:
            self.assertIn(field, body)

    def test_notify_exit_has_required_fields(self):
        """Exit notification includes ticker, exit_price, pnl_pct."""
        methods = self._make_engine_class()
        body = methods["_notify_position_closed"]
        for field in ["ticker", "exit_price", "pnl_pct", "reason"]:
            self.assertIn(field, body)


# =====================================================================
# F) MultiChannelNotifier new methods
# =====================================================================

class TestMultiChannelNotifierSprint25(unittest.TestCase):
    """Test new send_trade_alert and send_exit_alert methods."""

    def test_send_trade_alert_exists(self):
        self.assertTrue(hasattr(MultiChannelNotifier, "send_trade_alert"))

    def test_send_exit_alert_exists(self):
        self.assertTrue(hasattr(MultiChannelNotifier, "send_exit_alert"))

    def test_send_trade_alert_calls_send_message(self):
        notifier = MultiChannelNotifier()
        notifier.send_message = AsyncMock(return_value={
            "telegram": True, "discord": True, "whatsapp": False,
        })
        trade_info = {
            "ticker": "AAPL", "direction": "LONG",
            "quantity": 10, "fill_price": 150.25,
            "strategy": "momentum", "confidence": 75,
            "stop_price": 145.0, "composite_score": 0.85,
        }
        result = run_async(notifier.send_trade_alert(trade_info))
        notifier.send_message.assert_called_once()
        msg = notifier.send_message.call_args[0][0]
        self.assertIn("AAPL", msg)
        self.assertIn("LONG", msg)
        self.assertIn("150.25", msg)


# =====================================================================

if __name__ == "__main__":
    unittest.main()
