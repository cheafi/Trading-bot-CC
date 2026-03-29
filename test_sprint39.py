"""
Sprint 39 — Comprehensive Tests
================================
  1. US Universe expanded to 2,751 unique tickers
  2. International markets: HK (78), JP (60), KR (15), TW (11), AU (15), IN (10), Crypto (63)
  3. Universe builder wired to new ticker lists (8 markets, 3,100 cap)
  4. Telegram completely removed (all files, config, endpoints, docker, tests)
  5. Web dashboard improved (3,000+ universe stats, KR/AU/IN sections, title v3)
  6. MODEL_VERSION bumped to v6.39
"""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# ── Stub heavy third-party modules ──────────────────────────────
for mod_name in [
    "pydantic_settings",
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "asyncpg", "aiohttp", "redis", "apscheduler",
    "discord", "discord.ext", "discord.ext.commands",
    "tenacity", "yfinance",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Stub src.core.database
if "src.core.database" not in sys.modules:
    _db_stub = types.ModuleType("src.core.database")
    _db_stub.check_database_health = AsyncMock(return_value=True)
    _db_stub.get_session = MagicMock()
    _db_stub.get_async_session = MagicMock()
    _db_stub.async_engine = MagicMock()
    sys.modules["src.core.database"] = _db_stub

# Stub notification sub-modules to avoid circular imports
for _nmod in [
    "src.notifications",
    "src.notifications.discord",
    "src.notifications.discord_bot",
    "src.notifications.whatsapp",
    "src.notifications.formatter",
    "src.notifications.report_generator",
    "src.notifications.multi_channel",
]:
    if _nmod not in sys.modules:
        _stub = types.ModuleType(_nmod)
        if _nmod == "src.notifications.discord":
            class _DN:
                is_configured = False
                async def send_message(self, msg): return False
            _stub.DiscordNotifier = _DN
        elif _nmod == "src.notifications.discord_bot":
            _stub.DiscordInteractiveBot = MagicMock()
        elif _nmod == "src.notifications.whatsapp":
            class _WN:
                is_configured = False
                async def send_message(self, msg): return False
            _stub.WhatsAppNotifier = _WN
        sys.modules[_nmod] = _stub

# Re-import real numpy after MagicMock
import importlib
import numpy
importlib.reload(numpy)

# ── Project root ────────────────────────────────────────────────
BASE = str(Path(__file__).resolve().parent)
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def _load(name, rel_path):
    """Load a module by file path."""
    full = os.path.join(BASE, rel_path)
    spec = importlib.util.spec_from_file_location(name, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════
# 1. US Universe Tests
# ═══════════════════════════════════════════════════════════════

class TestUSUniverse(unittest.TestCase):
    """Verify US universe has 2,700+ unique tickers."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("us_universe", "src/scanners/us_universe.py")

    def test_01_us_universe_exists(self):
        self.assertTrue(hasattr(self.mod, "US_UNIVERSE"))

    def test_02_us_universe_count(self):
        count = len(self.mod.US_UNIVERSE)
        self.assertGreaterEqual(count, 2700, f"US_UNIVERSE has {count}, expected >= 2700")

    def test_03_us_universe_is_list(self):
        self.assertIsInstance(self.mod.US_UNIVERSE, list)

    def test_04_us_universe_unique(self):
        universe = self.mod.US_UNIVERSE
        self.assertEqual(len(universe), len(set(universe)), "US_UNIVERSE has duplicates")

    def test_05_sp500_sectors_exist(self):
        for sector in [
            "SP500_TECH", "SP500_HEALTHCARE", "SP500_FINANCIALS",
            "SP500_CONSUMER_DISC", "SP500_INDUSTRIALS", "SP500_COMM_SERVICES",
            "SP500_ENERGY", "SP500_STAPLES", "SP500_MATERIALS",
            "SP500_UTILITIES", "SP500_REITS",
        ]:
            self.assertTrue(hasattr(self.mod, sector), f"Missing {sector}")

    def test_06_sp500_combined_count(self):
        sp500 = self.mod.SP500
        self.assertGreaterEqual(len(sp500), 420, f"SP500 has {len(sp500)}")

    def test_07_ndx_extra_exists(self):
        self.assertTrue(hasattr(self.mod, "NDX_EXTRA"))
        self.assertGreater(len(self.mod.NDX_EXTRA), 30)

    def test_08_sp400_midcap_exists(self):
        self.assertTrue(hasattr(self.mod, "SP400_MIDCAP"))
        self.assertGreater(len(self.mod.SP400_MIDCAP), 200)

    def test_09_russell_smallcap_exists(self):
        self.assertTrue(hasattr(self.mod, "RUSSELL_SMALLCAP"))
        self.assertGreater(len(self.mod.RUSSELL_SMALLCAP), 400)

    def test_10_sector_map_exists(self):
        self.assertTrue(hasattr(self.mod, "US_SECTOR_MAP"))
        self.assertIsInstance(self.mod.US_SECTOR_MAP, dict)
        self.assertGreater(len(self.mod.US_SECTOR_MAP), 400)

    def test_11_key_tickers_present(self):
        universe = self.mod.US_UNIVERSE
        for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                        "JPM", "BAC", "GS", "JNJ", "LLY", "AMD", "AVGO"]:
            self.assertIn(ticker, universe, f"Missing key ticker {ticker}")


# ═══════════════════════════════════════════════════════════════
# 2. International Universe Tests
# ═══════════════════════════════════════════════════════════════

class TestIntlUniverse(unittest.TestCase):
    """Verify international universe covers 8 markets."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("intl_universe", "src/scanners/intl_universe.py")

    def test_20_hk_tickers(self):
        self.assertGreaterEqual(len(self.mod.HK_TICKERS), 70)

    def test_21_jp_tickers(self):
        self.assertGreaterEqual(len(self.mod.JP_TICKERS), 50)

    def test_22_kr_tickers(self):
        self.assertGreaterEqual(len(self.mod.KR_TICKERS), 10)

    def test_23_tw_tickers(self):
        self.assertGreaterEqual(len(self.mod.TW_TICKERS), 10)

    def test_24_au_tickers(self):
        self.assertGreaterEqual(len(self.mod.AU_TICKERS), 10)

    def test_25_in_tickers(self):
        self.assertGreaterEqual(len(self.mod.IN_TICKERS), 10)

    def test_26_crypto_tickers(self):
        self.assertGreaterEqual(len(self.mod.CRYPTO_TICKERS), 50)

    def test_27_market_region_enum(self):
        self.assertTrue(hasattr(self.mod, "MarketRegion"))
        for region in ["US", "HK", "JP", "KR", "TW", "AU", "IN", "CRYPTO"]:
            self.assertTrue(hasattr(self.mod.MarketRegion, region), f"Missing region {region}")

    def test_28_total_intl_count(self):
        total = (
            len(self.mod.HK_TICKERS) + len(self.mod.JP_TICKERS)
            + len(self.mod.KR_TICKERS) + len(self.mod.TW_TICKERS)
            + len(self.mod.AU_TICKERS) + len(self.mod.IN_TICKERS)
            + len(self.mod.CRYPTO_TICKERS)
        )
        self.assertGreaterEqual(total, 240, f"Total intl is {total}")

    def test_29_get_universe_stats(self):
        self.assertTrue(hasattr(self.mod, "get_universe_stats"))
        stats = self.mod.get_universe_stats()
        self.assertIsInstance(stats, dict)


# ═══════════════════════════════════════════════════════════════
# 3. Universe Builder Wiring Tests
# ═══════════════════════════════════════════════════════════════

class TestUniverseBuilderWiring(unittest.TestCase):
    """Verify universe_builder.py uses new ticker lists."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(BASE, "src", "scanners", "universe_builder.py")
        with open(path) as f:
            cls.code = f.read()

    def test_30_imports_us_universe(self):
        self.assertIn("from src.scanners.us_universe import", self.code)

    def test_31_imports_intl_universe(self):
        self.assertIn("from src.scanners.intl_universe import", self.code)

    def test_32_total_cap_3100(self):
        self.assertIn("3100", self.code)

    def test_33_eight_markets_default(self):
        for market in ["us", "hk", "jp", "kr", "tw", "au", "in", "crypto"]:
            self.assertIn(f'"{market}"', self.code)

    def test_34_us_2800_cap(self):
        self.assertIn('"us": 2800', self.code)


# ═══════════════════════════════════════════════════════════════
# 4. Telegram Removal Tests
# ═══════════════════════════════════════════════════════════════

class TestTelegramRemoval(unittest.TestCase):
    """Verify Telegram is completely removed from codebase."""

    def test_40_telegram_bot_file_deleted(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE, "src", "notifications", "telegram_bot.py")),
            "telegram_bot.py should be deleted",
        )

    def test_41_telegram_notifier_file_deleted(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE, "src", "notifications", "telegram.py")),
            "telegram.py should be deleted",
        )

    def test_42_run_telegram_deleted(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE, "run_telegram_bot.py")),
            "run_telegram_bot.py should be deleted",
        )

    def test_43_dockerfile_telegram_deleted(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE, "docker", "Dockerfile.telegram")),
            "Dockerfile.telegram should be deleted",
        )

    def test_44_config_no_telegram_fields(self):
        path = os.path.join(BASE, "src", "core", "config.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("telegram_bot_token", code)
        self.assertNotIn("telegram_chat_id", code)
        self.assertNotIn("has_telegram", code)

    def test_45_api_no_telegram_endpoints(self):
        path = os.path.join(BASE, "src", "api", "main.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("/telegram/start", code)
        self.assertNotIn("/telegram/send", code)

    def test_46_docker_compose_no_telegram_service(self):
        path = os.path.join(BASE, "docker-compose.yml")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("telegram_bot:", code)
        self.assertNotIn("Dockerfile.telegram", code)
        self.assertNotIn("TELEGRAM_BOT_TOKEN:?", code)

    def test_47_notifications_init_no_telegram(self):
        path = os.path.join(BASE, "src", "notifications", "__init__.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("TelegramNotifier", code)
        self.assertNotIn("TelegramBot", code)
        self.assertNotIn("start_telegram_bot", code)

    def test_48_multi_channel_no_telegram(self):
        path = os.path.join(BASE, "src", "notifications", "multi_channel.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("TelegramNotifier", code)
        self.assertNotIn("from src.notifications.telegram", code)

    def test_49_scheduler_no_telegram(self):
        path = os.path.join(BASE, "src", "scheduler", "main.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("from src.notifications.telegram", code)
        self.assertNotIn("self.telegram", code)

    def test_50_engines_main_no_telegram(self):
        path = os.path.join(BASE, "src", "engines", "main.py")
        with open(path) as f:
            code = f.read()
        self.assertNotIn("TELEGRAM_BOT_TOKEN", code)


# ═══════════════════════════════════════════════════════════════
# 5. Web Dashboard Tests
# ═══════════════════════════════════════════════════════════════

class TestWebDashboard(unittest.TestCase):
    """Verify web dashboard improvements."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(BASE, "src", "api", "templates", "index.html")
        with open(path) as f:
            cls.html = f.read()

    def test_60_title_v3(self):
        self.assertIn("TradingAI Pro v3", self.html)

    def test_61_meta_description_updated(self):
        self.assertIn("3,000+", self.html)
        self.assertIn("64 Slash Commands", self.html)

    def test_62_universe_stats_section(self):
        self.assertIn("Universe Coverage", self.html)
        self.assertIn("universeStats", self.html)

    def test_63_korea_stocks_section(self):
        self.assertIn("Korea Stocks", self.html)
        self.assertIn("koreaStocks", self.html)

    def test_64_australia_stocks_section(self):
        self.assertIn("Australia Stocks", self.html)
        self.assertIn("ausStocks", self.html)

    def test_65_india_stocks_section(self):
        self.assertIn("India Stocks", self.html)
        self.assertIn("indiaStocks", self.html)

    def test_66_asia_markets_expanded(self):
        self.assertIn("ASX 200", self.html)
        self.assertIn("Nifty 50", self.html)

    def test_67_no_182_commands(self):
        self.assertNotIn("182 Commands", self.html)


# ═══════════════════════════════════════════════════════════════
# 6. Version & README Tests
# ═══════════════════════════════════════════════════════════════

class TestVersionAndDocs(unittest.TestCase):
    """Verify version bump and README updates."""

    def test_70_model_version_v639(self):
        path = os.path.join(BASE, "src", "core", "trust_metadata.py")
        with open(path) as f:
            code = f.read()
        self.assertIn('MODEL_VERSION = "v6.39"', code)

    def test_71_readme_no_telegram(self):
        path = os.path.join(BASE, "README.md")
        with open(path) as f:
            readme = f.read()
        # Should not have Telegram in interface line
        self.assertNotIn("Telegram", readme.split("\n")[2])

    def test_72_readme_3000_universe(self):
        path = os.path.join(BASE, "README.md")
        with open(path) as f:
            readme = f.read()
        self.assertIn("3,000+", readme)

    def test_73_readme_11_services(self):
        path = os.path.join(BASE, "README.md")
        with open(path) as f:
            readme = f.read()
        self.assertIn("11 services", readme)

    def test_74_readme_64_commands(self):
        path = os.path.join(BASE, "README.md")
        with open(path) as f:
            readme = f.read()
        self.assertIn("64 slash commands", readme)

    def test_75_count_universe_helper_deleted(self):
        self.assertFalse(
            os.path.exists(os.path.join(BASE, "_count_universe.py")),
            "_count_universe.py helper should be deleted",
        )


# ═══════════════════════════════════════════════════════════════
# 7. Grand Total Universe Test
# ═══════════════════════════════════════════════════════════════

class TestGrandTotal(unittest.TestCase):
    """Verify total universe is 3,000+."""

    def test_80_grand_total_3000_plus(self):
        us_mod = _load("us_u_total", "src/scanners/us_universe.py")
        intl_mod = _load("intl_u_total", "src/scanners/intl_universe.py")
        us_count = len(us_mod.US_UNIVERSE)
        intl_count = (
            len(intl_mod.HK_TICKERS) + len(intl_mod.JP_TICKERS)
            + len(intl_mod.KR_TICKERS) + len(intl_mod.TW_TICKERS)
            + len(intl_mod.AU_TICKERS) + len(intl_mod.IN_TICKERS)
            + len(intl_mod.CRYPTO_TICKERS)
        )
        grand = us_count + intl_count
        self.assertGreaterEqual(grand, 3000, f"Grand total is {grand}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
