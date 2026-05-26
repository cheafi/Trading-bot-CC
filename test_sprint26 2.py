"""
Sprint 26 Tests — Live Dashboard, Engine Cleanup

Covers:
  A) PositionMonitor removed           (4 tests)
  B) Boot sanity check fixed           (3 tests)
  C) Yfinance dedup                    (4 tests)
  D) get_cached_state enriched         (5 tests)
  E) Dashboard API wired to real data  (7 tests)
  F) Regression guards                 (3 tests)

Total: 26 tests
"""

import ast
import asyncio
import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ── Stub heavy dependencies ────────────────────────────────

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
    "fastapi", "fastapi.middleware", "fastapi.middleware.cors",
    "fastapi.responses", "fastapi.exceptions",
    "fastapi.staticfiles", "fastapi.templating",
    "starlette", "starlette.middleware",
    "starlette.middleware.base",
    "uvicorn",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

if "src.core.database" not in sys.modules:
    _db_stub = types.ModuleType("src.core.database")
    _db_stub.check_database_health = AsyncMock(return_value=True)
    _db_stub.get_async_session = MagicMock()
    _db_stub.async_engine = MagicMock()
    sys.modules["src.core.database"] = _db_stub

for _nmod in [
    "src.notifications", "src.notifications.telegram",
    "src.notifications.telegram_bot", "src.notifications.discord",
    "src.notifications.discord_bot", "src.notifications.whatsapp",
    "src.notifications.formatter", "src.notifications.report_generator",
    "src.notifications.multi_channel",
]:
    if _nmod not in sys.modules:
        _stub = types.ModuleType(_nmod)
        if _nmod == "src.notifications.telegram":
            class _TN:
                is_configured = False
                async def send_message(self, msg): return False
                def _format_alert_message(self, **kw): return str(kw)
                def _format_daily_report_message(self, r): return str(r)
            _stub.TelegramNotifier = _TN
        elif _nmod == "src.notifications.discord":
            class _DN:
                is_configured = False
                async def send_message(self, msg): return False
            _stub.DiscordNotifier = _DN
        elif _nmod == "src.notifications.whatsapp":
            class _WN:
                is_configured = False
                async def send_message(self, msg): return False
            _stub.WhatsAppNotifier = _WN
        elif _nmod == "src.notifications.multi_channel":
            class _MCN:
                async def send_trade_alert(self, info): return {}
                async def send_exit_alert(self, info): return {}
                async def send_message(self, msg): return {}
            _stub.MultiChannelNotifier = _MCN
        elif _nmod == "src.notifications.discord_bot":
            _stub.DiscordInteractiveBot = MagicMock()
        elif _nmod == "src.notifications.telegram_bot":
            _stub.TelegramBot = MagicMock()
            _stub.start_telegram_bot = MagicMock()
        elif _nmod == "src.notifications.report_generator":
            _stub.build_signal_card = MagicMock()
            _stub.build_regime_snapshot = MagicMock()
            _stub.build_morning_memo = MagicMock()
            _stub.build_eod_scorecard = MagicMock()
            _stub.embeds_to_markdown = MagicMock()
        sys.modules[_nmod] = _stub

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENGINE_PATH = ROOT / "src" / "engines" / "auto_trading_engine.py"
API_PATH = ROOT / "src" / "api" / "main.py"


def _read_source():
    return ENGINE_PATH.read_text()


def _extract_method(source: str, method_name: str) -> str:
    """Extract a method body from the AST."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == method_name:
                return ast.get_source_segment(source, node)
    return ""


# =====================================================================
# A) PositionMonitor removed
# =====================================================================

class TestPositionMonitorRemoved(unittest.TestCase):
    """Verify PositionMonitor class and all references are gone."""

    def setUp(self):
        self.source = _read_source()

    def test_class_removed(self):
        """PositionMonitor class definition should not exist."""
        self.assertNotIn(
            "class PositionMonitor",
            self.source,
        )

    def test_no_instantiation(self):
        """No PositionMonitor() constructor call."""
        # Exclude comments and docstrings by checking only code
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                self.assertNotEqual(
                    name, "PositionMonitor",
                    "PositionMonitor should not be instantiated",
                )

    def test_no_track_entry_call(self):
        """position_monitor.track_entry should not be called."""
        self.assertNotIn(
            "position_monitor.track_entry",
            self.source,
        )

    def test_not_in_health_check(self):
        """position_monitor should not be in health_check components."""
        method = _extract_method(self.source, "health_check")
        self.assertNotIn("position_monitor", method)


# =====================================================================
# B) Boot sanity check fixed
# =====================================================================

class TestBootSanityCheck(unittest.TestCase):
    """Boot check should use correct field name."""

    def setUp(self):
        self.source = _read_source()
        self.boot_method = _extract_method(self.source, "_boot")

    def test_uses_risk_per_trade_pct(self):
        """Should reference risk_per_trade_pct, not risk_per_trade."""
        self.assertIn(
            "risk_per_trade_pct",
            self.boot_method,
        )

    def test_no_old_field_name(self):
        """Should not reference the non-existent risk_per_trade."""
        # risk_per_trade_pct is fine; we're checking for bare
        # risk_per_trade followed by space or > (not _pct)
        import re
        matches = re.findall(
            r"risk_per_trade(?!_pct)",
            self.boot_method,
        )
        self.assertEqual(
            len(matches), 0,
            f"Found old field reference(s): {matches}",
        )

    def test_threshold_is_percentage(self):
        """Threshold should be > 10 (percentage), not > 0.10."""
        self.assertIn("10.0", self.boot_method)
        self.assertNotIn("0.10", self.boot_method)


# =====================================================================
# C) Yfinance dedup
# =====================================================================

class TestYfinanceDedup(unittest.TestCase):
    """_generate_signals should not import yfinance for VIX/SPY."""

    def setUp(self):
        self.source = _read_source()
        self.method = _extract_method(self.source, "_generate_signals")

    def test_no_inline_vix_fetch(self):
        """No Ticker('^VIX').history call in _generate_signals."""
        self.assertNotIn(
            'Ticker("^VIX")',
            self.method,
        )
        self.assertNotIn(
            "Ticker('^VIX')",
            self.method,
        )

    def test_no_inline_spy_fetch(self):
        """No Ticker('SPY').history call in _generate_signals."""
        self.assertNotIn(
            'Ticker("SPY").history',
            self.method,
        )

    def test_uses_context_market_state(self):
        """Should read from self._context market_state."""
        self.assertIn(
            "market_state",
            self.method,
        )

    def test_no_yfinance_import(self):
        """No 'import yfinance' inside _generate_signals."""
        self.assertNotIn(
            "import yfinance as _yf_ate",
            self.method,
        )


# =====================================================================
# D) get_cached_state enriched
# =====================================================================

class TestGetCachedStateEnriched(unittest.TestCase):
    """get_cached_state should expose dashboard-useful data."""

    def setUp(self):
        self.source = _read_source()
        self.method = _extract_method(
            self.source, "get_cached_state",
        )

    def test_has_market_state(self):
        self.assertIn("market_state", self.method)

    def test_has_equity(self):
        self.assertIn("equity", self.method)

    def test_has_circuit_breaker(self):
        self.assertIn("circuit_breaker", self.method)

    def test_has_open_positions(self):
        self.assertIn("open_positions", self.method)

    def test_has_win_rate(self):
        self.assertIn("win_rate", self.method)


# =====================================================================
# E) Dashboard API wired to real data
# =====================================================================

class TestDashboardAPI(unittest.TestCase):
    """API dashboard endpoint should use engine state."""

    def setUp(self):
        self.api_source = API_PATH.read_text()

    def test_no_hardcoded_pnl(self):
        """Should not contain hardcoded 24567.89."""
        self.assertNotIn("24567.89", self.api_source)

    def test_no_hardcoded_win_rate(self):
        """Should not contain hardcoded 'winRate': 68."""
        self.assertNotIn('"winRate": 68', self.api_source)

    def test_no_hardcoded_portfolio_value(self):
        """Should not contain hardcoded 100000 portfolio."""
        # Check it's not in the dashboard endpoint
        tree = ast.parse(self.api_source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_dashboard_data":
                    body = ast.get_source_segment(
                        self.api_source, node,
                    )
                    self.assertNotIn(
                        '"portfolioValue": 100000',
                        body,
                    )
                    break

    def test_no_fake_ticker_data(self):
        """Should not contain fake NVDA/MARA/COIN static signals."""
        tree = ast.parse(self.api_source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_dashboard_data":
                    body = ast.get_source_segment(
                        self.api_source, node,
                    )
                    self.assertNotIn('"NVDA"', body)
                    self.assertNotIn('"MARA"', body)
                    break

    def test_reads_engine_state(self):
        """Dashboard should try to read engine cached state."""
        tree = ast.parse(self.api_source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_dashboard_data":
                    body = ast.get_source_segment(
                        self.api_source, node,
                    )
                    self.assertIn("get_cached_state", body)
                    break

    def test_has_regime_key(self):
        """Response should include regime."""
        tree = ast.parse(self.api_source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_dashboard_data":
                    body = ast.get_source_segment(
                        self.api_source, node,
                    )
                    self.assertIn('"regime"', body)
                    break

    def test_has_circuit_breaker_key(self):
        """Response should include circuitBreaker."""
        tree = ast.parse(self.api_source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_dashboard_data":
                    body = ast.get_source_segment(
                        self.api_source, node,
                    )
                    self.assertIn("circuitBreaker", body)
                    break


# =====================================================================
# F) Regression guards
# =====================================================================

class TestRegressionGuards(unittest.TestCase):
    """Ensure Sprint 22-25 features are still intact."""

    def setUp(self):
        self.source = _read_source()

    def test_trade_recommendation_import(self):
        """TradeRecommendation should still be imported (Sprint 22)."""
        self.assertIn("TradeRecommendation", self.source)

    def test_universe_builder_import(self):
        """UniverseBuilder should still be imported (Sprint 23)."""
        self.assertIn("UniverseBuilder", self.source)

    def test_notify_trade_executed(self):
        """Sprint 25 trade notification should remain."""
        self.assertIn(
            "_notify_trade_executed",
            self.source,
        )


# =====================================================================

if __name__ == "__main__":
    unittest.main()
