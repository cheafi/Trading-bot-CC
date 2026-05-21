"""
Sprint 41 — Pro trader/investor improvements (2026).

Covers three changes:
  1. RiskCircuitBreaker.daily_pnl unit-correctness (dollars vs %).
  2. PositionManager VIX-aware risk scaling.
  3. UniverseFilter macro-event blackout (FOMC/CPI/NFP).
"""
import unittest
from datetime import date, datetime, timezone

import pandas as pd

from src.engines.auto_trading_engine import RiskCircuitBreaker
from src.algo.position_manager import PositionManager, RiskParameters
from src.engines.signal_engine import UniverseFilter


class TestCircuitBreakerDailyLossUnits(unittest.TestCase):
    def test_small_dollar_loss_does_not_trip_percent_limit(self):
        cb = RiskCircuitBreaker(
            max_daily_loss_pct=3.0,
            max_drawdown_pct=10.0,
            max_consecutive_losses=5,
        )
        # Prime SOD equity at $100k
        self.assertTrue(cb.update(equity=100_000.0))
        # A $5 loss is 0.005% of equity — must NOT trip 3% daily-loss limit
        ok = cb.update(equity=99_995.0, trade_pnl=-5.0)
        self.assertTrue(ok, f"CB falsely tripped on tiny $ loss: {cb.trigger_reason}")
        self.assertFalse(cb.triggered)

    def test_real_three_percent_loss_does_trip(self):
        cb = RiskCircuitBreaker(max_daily_loss_pct=3.0)
        cb.update(equity=100_000.0)
        ok = cb.update(equity=96_500.0, trade_pnl=-3_500.0)
        self.assertFalse(ok)
        self.assertTrue(cb.triggered)
        self.assertIn("Daily loss", cb.trigger_reason)


class TestVixAwarePositionSizing(unittest.TestCase):
    def setUp(self):
        self.pm = PositionManager(RiskParameters(
            account_size=100_000.0,
            risk_per_trade_pct=1.0,
            max_position_size_pct=100.0,
            max_total_exposure_pct=100.0,
        ))

    def test_normal_vix_baseline(self):
        r = self.pm.calculate_position_size("AAPL", 100.0, 95.0, vix=15.0)
        # 1% risk, $5 per-share risk -> $1000 risk -> 200 shares
        self.assertEqual(r["shares"], 200)

    def test_panic_vix_quarter_size(self):
        r = self.pm.calculate_position_size("AAPL", 100.0, 95.0, vix=40.0)
        # 1% * 0.25 = 0.25% -> $250 risk -> 50 shares
        self.assertEqual(r["shares"], 50)

    def test_calm_vix_scales_up_within_hard_cap(self):
        r = self.pm.calculate_position_size("AAPL", 100.0, 95.0, vix=11.0)
        # 1% * 1.20 = 1.20% -> $1200 -> 240 shares
        self.assertEqual(r["shares"], 240)

    def test_vix_scalar_never_exceeds_max_risk_cap(self):
        pm = PositionManager(RiskParameters(
            account_size=100_000.0,
            risk_per_trade_pct=2.0,
            max_risk_per_trade_pct=2.0,
            max_position_size_pct=100.0,
            max_total_exposure_pct=100.0,
        ))
        r = pm.calculate_position_size("AAPL", 100.0, 95.0, vix=10.0)
        # 2% * 1.20 = 2.4% but capped at 2.0% -> $2000 -> 400 shares
        self.assertEqual(r["shares"], 400)


class TestMacroEventBlackout(unittest.TestCase):
    def setUp(self):
        self.uf = UniverseFilter()
        self.universe = ["AAPL", "MSFT", "NVDA"]
        # Minimal feature frame so loop runs (won't be reached on macro day)
        self.features = pd.DataFrame(
            {
                "close": [200.0, 400.0, 800.0],
                "volume_sma_20": [10_000_000] * 3,
                "market_cap": [3e12, 3e12, 3e12],
                "history_days": [500] * 3,
            },
            index=["AAPL", "MSFT", "NVDA"],
        )

    def test_fomc_day_blocks_entire_universe(self):
        macro = [{"event_type": "fomc", "event_date": date.today()}]
        clean, rej = self.uf.filter(self.universe, self.features, macro_events=macro)
        self.assertEqual(clean, [])
        for t in self.universe:
            self.assertIn("macro_blackout", rej[t])

    def test_non_event_day_allows_normal_filtering(self):
        macro = [{"event_type": "fomc", "event_date": date(2020, 1, 1)}]
        clean, _ = self.uf.filter(self.universe, self.features, macro_events=macro)
        # Should not blackout; remainder depends on per-ticker gates
        self.assertIsInstance(clean, list)

    def test_low_impact_event_does_not_blackout(self):
        macro = [{"event_type": "consumer_confidence", "event_date": date.today()}]
        clean, rej = self.uf.filter(self.universe, self.features, macro_events=macro)
        # No tickers should be rejected for macro_blackout reason
        self.assertFalse(any("macro_blackout" in v for v in rej.values()))


if __name__ == "__main__":
    unittest.main()
