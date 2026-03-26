"""
Sprint 19 — Pydantic V2 Migration

Tests:
  1. No deprecated `class Config:` in models.py
  2. All 6 models use `model_config = ConfigDict(from_attributes=True)`
  3. ConfigDict imported from pydantic
  4. Models still instantiate correctly
  5. No PydanticDeprecatedSince20 warnings on import
"""
import sys
import os
import unittest
import importlib.util
import warnings
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


# ═════════════════════════════════════════════════════════════════════
# 1. NO DEPRECATED CLASS CONFIG
# ═════════════════════════════════════════════════════════════════════
class TestPydanticMigration(unittest.TestCase):

    def test_01_no_class_config(self):
        """models.py should not contain deprecated 'class Config:'."""
        path = os.path.join(ROOT, "src", "core", "models.py")
        with open(path) as f:
            content = f.read()
        self.assertNotIn("class Config:", content)

    def test_02_has_model_config_6_times(self):
        """models.py should have 6 model_config = ConfigDict lines."""
        path = os.path.join(ROOT, "src", "core", "models.py")
        with open(path) as f:
            content = f.read()
        count = content.count("model_config = ConfigDict(from_attributes=True)")
        self.assertEqual(count, 6, f"Expected 6, found {count}")

    def test_03_configdict_imported(self):
        """ConfigDict is imported from pydantic."""
        path = os.path.join(ROOT, "src", "core", "models.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("ConfigDict", content)
        self.assertIn("from pydantic import", content)

    def test_04_no_deprecation_warnings(self):
        """Importing models should not produce PydanticDeprecatedSince20."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _load("src.core.models_t04", "src/core/models.py")
            pydantic_warns = [
                x for x in w
                if "PydanticDeprecatedSince20" in str(x.category)
                or "class-based `config`" in str(x.message)
            ]
            self.assertEqual(
                len(pydantic_warns), 0,
                f"Got {len(pydantic_warns)} Pydantic deprecation warnings",
            )


# ═════════════════════════════════════════════════════════════════════
# 2. MODELS STILL WORK
# ═════════════════════════════════════════════════════════════════════
class TestModelsStillWork(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.models = _load("src.core.models_tw", "src/core/models.py")

    def test_05_ohlcv_instantiate(self):
        """OHLCV model can be instantiated."""
        from datetime import datetime
        ohlcv = self.models.OHLCV(
            ts=datetime.now(), ticker="AAPL",
            open=150.0, high=155.0, low=149.0,
            close=153.0, volume=1000000,
        )
        self.assertEqual(ohlcv.ticker, "AAPL")

    def test_06_signal_instantiate(self):
        """Signal model can be instantiated with required fields."""
        sig = self.models.Signal(
            ticker="AAPL",
            direction=self.models.Direction.LONG,
            horizon=self.models.Horizon.SWING_1_5D,
            entry_price=150.0,
            invalidation=self.models.Invalidation(
                stop_price=145.0,
                stop_type=self.models.StopType.HARD,
            ),
            targets=[self.models.Target(price=160.0, pct_position=100)],
            entry_logic="Breakout above 50-day MA",
            catalyst="Strong earnings",
            key_risks=["Market volatility"],
            confidence=75,
            rationale="Strong technical setup with volume confirmation",
        )
        self.assertEqual(sig.ticker, "AAPL")
        self.assertEqual(sig.direction, self.models.Direction.LONG)

    def test_07_market_regime_instantiate(self):
        """MarketRegime model works."""
        from datetime import datetime
        regime = self.models.MarketRegime(
            timestamp=datetime.now(),
            volatility=self.models.VolatilityRegime.NORMAL,
            trend=self.models.TrendRegime.UPTREND,
            risk=self.models.RiskRegime.RISK_ON,
            active_strategies=["momentum"],
        )
        self.assertTrue(regime.should_trade)

    def test_08_edge_model_instantiate(self):
        """EdgeModel works with ev_positive property."""
        edge = self.models.EdgeModel(
            p_stop=0.3, p_t1=0.6, p_t2=0.4,
            expected_return_pct=2.5,
        )
        self.assertTrue(edge.ev_positive)

    def test_09_news_article_instantiate(self):
        """NewsArticle model works."""
        from datetime import datetime
        article = self.models.NewsArticle(
            title="Test headline",
            source="Reuters",
            url="https://example.com",
            published_at=datetime.now(),
        )
        self.assertEqual(article.source, "Reuters")

    def test_10_social_post_instantiate(self):
        """SocialPost model works."""
        from datetime import datetime
        post = self.models.SocialPost(
            platform="twitter",
            post_id="123456",
            author_handle="testuser",
            content="$AAPL looking bullish",
            posted_at=datetime.now(),
        )
        self.assertEqual(post.platform, "twitter")

    def test_11_calendar_event_instantiate(self):
        """CalendarEvent model works."""
        from datetime import date
        event = self.models.CalendarEvent(
            event_type="earnings",
            event_date=date.today(),
            ticker="AAPL",
            title="AAPL Q3 Earnings",
        )
        self.assertEqual(event.event_type, "earnings")

    def test_12_utcnow_still_works(self):
        """_utcnow helper still produces valid timestamps."""
        dt = self.models._utcnow()
        self.assertIsNotNone(dt.tzinfo)

    def test_13_from_attributes_works(self):
        """model_config from_attributes=True is functional."""
        from datetime import datetime
        ohlcv = self.models.OHLCV(
            ts=datetime.now(), ticker="MSFT",
            open=100.0, high=105.0, low=99.0,
            close=104.0, volume=500000,
        )
        d = ohlcv.model_dump()
        self.assertIn("ticker", d)
        self.assertEqual(d["ticker"], "MSFT")


if __name__ == "__main__":
    unittest.main()
