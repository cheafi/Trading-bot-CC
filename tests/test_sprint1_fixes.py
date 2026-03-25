"""
Deterministic regression tests for Sprint 1 critical fixes.

Tests:
  1. Strategy routing: unified registry has all IDs, regime returns both sets
  2. OOS selection: full_analysis uses dev/val/holdout split
  3. ML leakage: cross-sectional ranks are per-date, no post-trade features
  4. Risk breakers: daily PnL updates, weekly enforced, partial exits work
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStrategyRouting(unittest.TestCase):
    """Fix 1: Unified strategy registry and regime routing."""

    def test_registry_has_all_strategies(self):
        from src.strategies import STRATEGY_REGISTRY
        # Must have both legacy (_v1) and algo IDs
        self.assertIn("momentum_v1", STRATEGY_REGISTRY)
        self.assertIn("mean_reversion_v1", STRATEGY_REGISTRY)
        self.assertIn("breakout_v1", STRATEGY_REGISTRY)
        # Algo strategies
        self.assertIn("vcp", STRATEGY_REGISTRY)
        self.assertIn("momentum_breakout", STRATEGY_REGISTRY)
        self.assertIn("trend_following", STRATEGY_REGISTRY)
        self.assertIn("classic_swing", STRATEGY_REGISTRY)
        self.assertIn("short_term_mean_reversion", STRATEGY_REGISTRY)
        self.assertIn("pre_earnings_momentum", STRATEGY_REGISTRY)
        # Total: 3 native + 8 algo = 11+
        self.assertGreaterEqual(len(STRATEGY_REGISTRY), 11)

    def test_get_strategy_native(self):
        from src.strategies import get_strategy
        s = get_strategy("momentum_v1")
        self.assertEqual(s.STRATEGY_ID, "momentum_v1")

    def test_get_strategy_algo_adapter(self):
        from src.strategies import get_strategy
        s = get_strategy("classic_swing")
        self.assertEqual(s.STRATEGY_ID, "classic_swing")
        # Must have generate_signals method (BaseStrategy interface)
        self.assertTrue(hasattr(s, "generate_signals"))

    def test_get_all_strategies_loads_all(self):
        from src.strategies import get_all_strategies
        strats = get_all_strategies()
        ids = [s.STRATEGY_ID for s in strats]
        self.assertIn("momentum_v1", ids)
        self.assertIn("vcp", ids)
        self.assertIn("classic_swing", ids)
        self.assertGreaterEqual(len(strats), 11)

    def test_regime_returns_both_id_sets(self):
        from src.engines.signal_engine import RegimeDetector
        from src.core.models import (
            VolatilityRegime, TrendRegime, RiskRegime,
        )
        det = RegimeDetector()
        # Normal uptrend = should include both _v1 and algo IDs
        active = det._get_active_strategies(
            VolatilityRegime.NORMAL,
            TrendRegime.UPTREND,
            RiskRegime.RISK_ON,
        )
        # Legacy IDs present
        self.assertIn("momentum_v1", active)
        self.assertIn("breakout_v1", active)
        self.assertIn("mean_reversion_v1", active)
        # Algo IDs present
        self.assertIn("momentum_breakout", active)
        self.assertIn("trend_following", active)
        self.assertIn("classic_swing", active)
        # Earnings always present
        self.assertIn("pre_earnings_momentum", active)

    def test_crisis_returns_empty(self):
        from src.engines.signal_engine import RegimeDetector
        from src.core.models import (
            VolatilityRegime, TrendRegime, RiskRegime,
        )
        det = RegimeDetector()
        active = det._get_active_strategies(
            VolatilityRegime.CRISIS,
            TrendRegime.DOWNTREND,
            RiskRegime.RISK_OFF,
        )
        self.assertEqual(active, [])


class TestOOSSelection(unittest.TestCase):
    """Fix 2: Optimizer uses OOS-driven selection."""

    def test_full_analysis_has_holdout(self):
        import pandas as pd
        import numpy as np
        from src.engines.strategy_optimizer import StrategyOptimizer

        # Create synthetic price data (250 bars ~ 1 year)
        np.random.seed(42)
        n = 250
        close = 100 * np.cumprod(
            1 + np.random.normal(0.0005, 0.015, n)
        )
        hist = pd.DataFrame({
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.random.randint(1_000_000, 5_000_000, n),
        })

        opt = StrategyOptimizer()
        result = opt.full_analysis("TEST", hist, "1y")

        # Must have new OOS fields
        self.assertIn("validation", result)
        self.assertIn("holdout", result)
        self.assertIn("selection_method", result)
        self.assertEqual(result["selection_method"], "OOS_walk_forward")


class TestMLLeakage(unittest.TestCase):
    """Fix 3 & 4: No cross-sectional or post-trade leakage."""

    def test_no_post_trade_features(self):
        from src.ml.trade_learner import TradeOutcomePredictor
        pred = TradeOutcomePredictor()
        # These are post-trade and must NOT be in feature cols
        self.assertNotIn("hold_hours", pred.FEATURE_COLS)
        self.assertNotIn("max_adverse_excursion", pred.FEATURE_COLS)
        # Pre-trade features should remain
        self.assertIn("confidence", pred.FEATURE_COLS)
        self.assertIn("rsi_at_entry", pred.FEATURE_COLS)

    def test_cross_sectional_ranks_vary_by_date(self):
        import pandas as pd
        import numpy as np
        from src.ml.feature_pipeline import FeaturePipeline

        np.random.seed(42)
        n = 60
        dates = pd.date_range("2024-01-01", periods=n, freq="B")

        all_data = {}
        for ticker in ["AAPL", "MSFT", "GOOG"]:
            close = 100 + np.cumsum(np.random.randn(n))
            df = pd.DataFrame({
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": np.random.randint(
                    1_000_000, 5_000_000, n
                ),
            }, index=dates)
            all_data[ticker] = df

        pipeline = FeaturePipeline()
        result = pipeline.generate_cross_sectional_features(all_data)

        # Ranks should NOT be a single constant per ticker
        for ticker, df in result.items():
            if "return_rank" in df.columns:
                ranks = df["return_rank"].dropna()
                if len(ranks) > 10:
                    # Must have variation (not a single value)
                    self.assertGreater(
                        ranks.nunique(), 1,
                        f"{ticker} return_rank is constant "
                        f"(leakage!): {ranks.unique()}"
                    )


class TestRiskBreakers(unittest.TestCase):
    """Fix 5: Daily PnL, weekly loss, partial exits."""

    def test_close_position_updates_daily_pnl(self):
        from src.algo.position_manager import (
            PositionManager, RiskParameters,
        )
        pm = PositionManager(RiskParameters(account_size=100000))
        pm.open_position(
            ticker="AAPL", strategy_id="test",
            entry_price=150.0, shares=100,
            stop_loss_price=145.0, sector="Tech",
        )
        pm.close_position("AAPL", 155.0, "take_profit")

        today = datetime.now().strftime('%Y-%m-%d')
        # daily_pnl must be updated (not zero)
        self.assertNotEqual(pm.daily_pnl.get(today, 0.0), 0.0)

    def test_weekly_pnl_enforced(self):
        from src.algo.position_manager import (
            PositionManager, RiskParameters,
        )
        pm = PositionManager(RiskParameters(
            account_size=100000, max_weekly_loss_pct=7.0
        ))
        # Simulate a bad week
        if not hasattr(pm, 'weekly_pnl'):
            pm.weekly_pnl = {}
        try:
            week_key = datetime.now().strftime('%Y-W%W')
        except Exception:
            week_key = "2024-W01"
        pm.weekly_pnl[week_key] = -8.0  # exceeds 7% limit

        can, reason = pm.can_open_position("MSFT")
        self.assertFalse(can)
        self.assertIn("Weekly", reason)

    def test_reduce_position_partial_exit(self):
        from src.algo.position_manager import (
            PositionManager, RiskParameters,
        )
        pm = PositionManager(RiskParameters(account_size=100000))
        pm.open_position(
            ticker="AAPL", strategy_id="test",
            entry_price=150.0, shares=90,
            stop_loss_price=145.0, sector="Tech",
        )
        # Partial exit: sell 30 of 90 shares
        pnl = pm.reduce_position("AAPL", 30, 155.0, "partial_1r")
        self.assertIsNotNone(pnl)
        self.assertGreater(pnl, 0)
        # Position should still exist with 60 shares
        self.assertIn("AAPL", pm.positions)
        self.assertEqual(pm.positions["AAPL"].shares, 60)


if __name__ == "__main__":
    unittest.main()
