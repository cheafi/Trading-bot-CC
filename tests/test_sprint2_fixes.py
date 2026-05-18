"""Sprint 2 regression tests."""
import os
import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch


class TestRegimeWeights(unittest.TestCase):

    def test_returns_dict(self):
        from src.engines.signal_engine import RegimeDetector
        from src.core.models import VolatilityRegime, TrendRegime, RiskRegime
        det = RegimeDetector()
        w = det._get_active_strategies(
            VolatilityRegime.NORMAL, TrendRegime.UPTREND, RiskRegime.NEUTRAL)
        self.assertIsInstance(w, dict)
        self.assertGreater(len(w), 0)

    def test_risk_off_dampens(self):
        from src.engines.signal_engine import RegimeDetector
        from src.core.models import VolatilityRegime, TrendRegime, RiskRegime
        det = RegimeDetector()
        n = det._get_active_strategies(
            VolatilityRegime.NORMAL, TrendRegime.NEUTRAL, RiskRegime.NEUTRAL)
        r = det._get_active_strategies(
            VolatilityRegime.NORMAL, TrendRegime.NEUTRAL, RiskRegime.RISK_OFF)
        for k in set(n) & set(r):
            self.assertLess(r[k], n[k])

    def test_bridge_preserves_reduced_risk_strategies(self):
        from src.engines.signal_engine import RegimeDetector
        from src.engines.regime_router import RegimeState

        det = RegimeDetector()
        rs = RegimeState(
            risk_regime="neutral",
            trend_regime="sideways",
            volatility_regime="normal_vol",
            should_trade=False,
            size_scalar=0.6,
            confidence=0.38,
            no_trade_reason="low confidence",
        )

        regime = det._regime_state_to_market(rs, {})

        self.assertTrue(regime.active_strategies)
        self.assertTrue(regime.should_trade)
        self.assertLess(regime.strategy_weights["mean_reversion"], 0.85)

    def test_bridge_keeps_crisis_as_no_trade(self):
        from src.engines.signal_engine import RegimeDetector
        from src.engines.regime_router import RegimeState

        det = RegimeDetector()
        rs = RegimeState(
            risk_regime="risk_off",
            trend_regime="downtrend",
            volatility_regime="crisis_vol",
            should_trade=False,
            size_scalar=0.0,
            no_trade_reason="crisis",
        )

        regime = det._regime_state_to_market(rs, {})

        self.assertEqual(regime.active_strategies, [])
        self.assertFalse(regime.should_trade)


class TestFeaturePipelineV2(unittest.TestCase):

    def test_regime_features(self):
        from src.ml.feature_pipeline import FeaturePipeline as FeatureEngine
        fe = FeatureEngine()
        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        c = 100 + np.cumsum(np.random.randn(100) * 0.5)
        df = pd.DataFrame({"close": c, "high": c+1, "low": c-1,
            "volume": np.random.randint(1e6,1e7,100)}, index=dates)
        out = fe.generate_regime_features(df)
        for col in ["realized_vol_10d","realized_vol_20d","vol_regime_z","trend_strength"]:
            self.assertIn(col, out.columns)

    def test_earnings_proximity(self):
        from src.ml.feature_pipeline import FeaturePipeline as FeatureEngine
        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        c = 100 + np.cumsum(np.random.randn(100) * 0.5)
        df = pd.DataFrame({"close": c}, index=dates)
        out = FeatureEngine.generate_earnings_proximity(df, ["2024-02-15"])
        self.assertIn("days_to_earnings", out.columns)
        self.assertGreater(out.loc["2024-01-15","days_to_earnings"], 0)


class TestMarketDataNews(unittest.TestCase):
    def test_has_get_news(self):
        from src.services.market_data import MarketDataService
        self.assertTrue(hasattr(MarketDataService, "get_news"))


class TestTopCountFix(unittest.TestCase):
    def test_top_count_defined(self):
        src = open("src/notifications/discord_bot.py").read()
        self.assertGreaterEqual(src.count("top_count = min("), 3)


class TestConfigUrlOverrides(unittest.TestCase):

    @patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://u:p@dbhost:5439/appdb",
            "REDIS_URL": "redis://:pw@redisbox:6390/0",
        },
        clear=False,
    )
    def test_legacy_url_overrides_are_honored(self):
        from src.core.config import Settings

        settings = Settings()

        self.assertEqual(settings.database_url, "postgresql://u:p@dbhost:5439/appdb")
        self.assertEqual(
            settings.async_database_url,
            "postgresql+asyncpg://u:p@dbhost:5439/appdb",
        )
        self.assertEqual(settings.redis_url, "redis://:pw@redisbox:6390/0")
        self.assertEqual(settings.postgres_host, "dbhost")
        self.assertEqual(settings.postgres_port, 5439)
        self.assertEqual(settings.postgres_db, "appdb")
        self.assertEqual(settings.redis_host, "redisbox")
        self.assertEqual(settings.redis_port, 6390)


if __name__ == "__main__":
    unittest.main()
