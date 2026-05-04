"""Sprint 2 regression tests."""
import unittest
import numpy as np
import pandas as pd


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


if __name__ == "__main__":
    unittest.main()
