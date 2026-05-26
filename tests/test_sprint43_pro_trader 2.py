"""
Sprint 43 — final pro-trader hardening (2026).

  • PortfolioRiskBudget.check_budget(vix=...) caps gross overnight book
    when VIX is elevated.
  • RegimeRouter.classify() consumes move_index and tilts risk-off score
    when rates vol is stressed.
  • PurgedWalkForward emits non-overlapping train/test windows with
    purge + embargo gaps.
  • src.core.slippage shared estimator returns identical results for
    backtest and live execution paths.
"""
import unittest
from datetime import date, timedelta

import pandas as pd
import numpy as np

from src.engines.portfolio_risk_budget import (
    PortfolioRiskBudget, ExposureSnapshot,
)
from src.engines.regime_router import RegimeRouter
from src.backtest.walk_forward import (
    PurgedWalkForward, assert_no_overlap,
)
from src.core.slippage import (
    SlippageConfig, estimate_slippage_bps, slippage_bps_to_fraction,
)


class TestOvernightVixGrossCap(unittest.TestCase):
    def setUp(self):
        self.budget = PortfolioRiskBudget()
        # Book already at 55% gross
        self.exposure = ExposureSnapshot(gross_exposure=0.55)

    def test_normal_vix_allows_new_position(self):
        r = self.budget.check_budget(
            ticker="AAPL", sector="tech", position_weight=0.03,
            exposure=self.exposure, vix=15.0,
        )
        self.assertTrue(r["allowed"])
        self.assertEqual(r["size_scalar"], 1.0)

    def test_high_vix_trims_to_60pct_cap(self):
        # 0.55 gross + 0.10 candidate = 0.65 > 0.60 cap @ VIX=28
        r = self.budget.check_budget(
            ticker="AAPL", sector="tech", position_weight=0.10,
            exposure=self.exposure, vix=28.0,
        )
        # Headroom 0.05; scaled to 0.05/0.10 = 0.5
        self.assertLessEqual(r["size_scalar"], 0.5 + 1e-6)
        self.assertTrue(any("VIX" in v for v in r["violations"]))

    def test_high_vix_at_cap_blocks(self):
        full = ExposureSnapshot(gross_exposure=0.60)
        r = self.budget.check_budget(
            ticker="AAPL", sector="tech", position_weight=0.03,
            exposure=full, vix=28.0,
        )
        self.assertFalse(r["allowed"])


class TestRegimeMoveIndex(unittest.TestCase):
    def test_high_move_pushes_risk_off(self):
        router = RegimeRouter()
        base = {
            "vix": 18.0, "spy_return_20d": 0.0,
            "breadth_pct": 0.5, "hy_spread": 0.0,
        }
        calm = router.classify({**base, "move_index": 70.0})
        stressed = router.classify({**base, "move_index": 150.0})
        # Stressed MOVE should raise risk-off probability
        self.assertGreater(
            stressed.risk_off_downtrend,
            calm.risk_off_downtrend,
        )
        self.assertEqual(stressed.move_index, 150.0)


class TestPurgedWalkForward(unittest.TestCase):
    def test_basic_split_count(self):
        wf = PurgedWalkForward(
            train_days=200, test_days=50, step_days=50,
            purge_days=10, embargo_days=5,
        )
        splits = wf.split_list(date(2020, 1, 1), date(2024, 1, 1))
        # Should produce multiple non-empty windows
        self.assertGreater(len(splits), 5)
        # Each window respects the requested gap
        for s in splits:
            gap = (s.test_start - s.train_end).days
            self.assertGreaterEqual(gap, 11)  # purge+1

    def test_no_train_test_overlap(self):
        wf = PurgedWalkForward(
            train_days=180, test_days=30, step_days=30,
            purge_days=7, embargo_days=3,
        )
        splits = wf.split_list(date(2020, 1, 1), date(2023, 1, 1))
        # No train fold should overlap any other test fold
        assert_no_overlap(splits)

    def test_too_short_range_yields_nothing(self):
        wf = PurgedWalkForward(
            train_days=200, test_days=50, purge_days=10,
        )
        splits = wf.split_list(date(2024, 1, 1), date(2024, 3, 1))
        self.assertEqual(splits, [])

    def test_invalid_args_raise(self):
        with self.assertRaises(ValueError):
            PurgedWalkForward(train_days=0)
        with self.assertRaises(ValueError):
            PurgedWalkForward(purge_days=-1)


class TestSharedSlippageEstimator(unittest.TestCase):
    def _bars(self, n=30, vol_mult=1.0):
        rng = np.random.default_rng(0)
        c = pd.Series(100 + rng.normal(0, 1, n).cumsum())
        return pd.DataFrame({
            "high": c + 0.5,
            "low": c - 0.5,
            "close": c,
            "volume": pd.Series([1_000_000] * (n - 1) + [int(1_000_000 * vol_mult)]),
        })

    def test_no_bars_returns_base(self):
        bps = estimate_slippage_bps(price=100.0, bars=None)
        self.assertEqual(bps, SlippageConfig().base_bps)

    def test_low_volume_increases_slippage(self):
        normal = estimate_slippage_bps(price=100.0, bars=self._bars(vol_mult=1.0))
        thin = estimate_slippage_bps(price=100.0, bars=self._bars(vol_mult=0.2))
        self.assertGreater(thin, normal)

    def test_earnings_adds_premium(self):
        b = self._bars()
        normal = estimate_slippage_bps(price=100.0, bars=b, near_earnings=False)
        ern = estimate_slippage_bps(price=100.0, bars=b, near_earnings=True)
        self.assertAlmostEqual(
            ern - normal, SlippageConfig().earnings_gap_extra_bps, places=6,
        )

    def test_capped(self):
        cfg = SlippageConfig(cap_bps=10.0, base_bps=8.0, k_volume=999.0)
        bps = estimate_slippage_bps(
            price=100.0, bars=self._bars(vol_mult=0.001), config=cfg,
        )
        self.assertEqual(bps, 10.0)

    def test_bps_to_fraction(self):
        self.assertAlmostEqual(slippage_bps_to_fraction(10.0), 0.0010)


if __name__ == "__main__":
    unittest.main()
