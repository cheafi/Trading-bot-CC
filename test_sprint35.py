"""
Sprint 35 tests — Portfolio Risk Budget + Professional KPI Surface.

New modules:
  src/engines/portfolio_risk_budget.py  – PortfolioRiskBudget, ExposureSnapshot
  src/engines/professional_kpi.py      – ProfessionalKPI, CoverageFunnel, KPISnapshot

Wiring changes:
  src/engines/auto_trading_engine.py   – risk budget multiplier (7th),
                                          KPI record_trade/record_cycle

29 new tests.
"""
import importlib
import importlib.util
import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# ── Stub heavy deps before any src.* imports ─────────────
for _mod in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.exc",
    "sqlalchemy.pool", "sqlalchemy.engine",
    "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "discord.ext.tasks", "discord.ui",
    "tenacity",
    "fastapi", "uvicorn",
    "apscheduler", "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "aiohttp", "aiohttp.web",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Stub database module
_db_stub = MagicMock()
_db_stub.check_database_health = MagicMock(return_value={})
_db_stub.get_session = MagicMock()
sys.modules.setdefault("src.core.database", _db_stub)

# Ensure real numpy is available
import numpy as _real_np
sys.modules["numpy"] = _real_np

# ── Load modules under test ──────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(BASE, path),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_prb_mod = _load(
    "src.engines.portfolio_risk_budget",
    "src/engines/portfolio_risk_budget.py",
)
_kpi_mod = _load(
    "src.engines.professional_kpi",
    "src/engines/professional_kpi.py",
)

PortfolioRiskBudget = _prb_mod.PortfolioRiskBudget
ExposureSnapshot = _prb_mod.ExposureSnapshot
ProfessionalKPI = _kpi_mod.ProfessionalKPI
CoverageFunnel = _kpi_mod.CoverageFunnel
KPISnapshot = _kpi_mod.KPISnapshot


# ═════════════════════════════════════════════════════════
#  A. Portfolio Risk Budget — check_budget()
# ═════════════════════════════════════════════════════════

class TestCheckBudgetSinglePosition(unittest.TestCase):
    """A1: Single-name position cap."""

    def test_under_cap_allowed(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        result = rb.check_budget(
            "AAPL", "Tech", 0.03, exp,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["size_scalar"], 1.0)
        self.assertEqual(len(result["violations"]), 0)

    def test_over_cap_scaled(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        result = rb.check_budget(
            "AAPL", "Tech", 0.10, exp,
        )
        # 5% cap / 10% weight = 0.5 scalar
        self.assertTrue(result["allowed"])
        self.assertAlmostEqual(result["size_scalar"], 0.5, places=2)
        self.assertGreater(len(result["violations"]), 0)


class TestCheckBudgetSectorConcentration(unittest.TestCase):
    """A2: Sector concentration limit."""

    def test_sector_within_limit(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.sector_weights = {"Tech": 0.20}
        result = rb.check_budget(
            "MSFT", "Tech", 0.05, exp,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["size_scalar"], 1.0)

    def test_sector_exceeds_limit(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.sector_weights = {"Tech": 0.28}
        result = rb.check_budget(
            "MSFT", "Tech", 0.05, exp,
        )
        # headroom = 30% - 28% = 2%, weight = 5% → scalar = 0.4
        self.assertTrue(result["allowed"])
        self.assertLess(result["size_scalar"], 1.0)
        self.assertGreater(result["size_scalar"], 0.0)

    def test_sector_full_blocked(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.sector_weights = {"Tech": 0.30}
        result = rb.check_budget(
            "MSFT", "Tech", 0.05, exp,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["size_scalar"], 0.0)


class TestCheckBudgetHighBeta(unittest.TestCase):
    """A3: High-beta cluster limit."""

    def test_low_beta_no_check(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.high_beta_weight = 0.24
        result = rb.check_budget(
            "KO", "Consumer", 0.05, exp, beta=0.8,
        )
        # beta < 1.3, so high-beta check not triggered
        self.assertTrue(result["allowed"])

    def test_high_beta_exceeds(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.high_beta_weight = 0.20
        result = rb.check_budget(
            "TSLA", "Auto", 0.04, exp, beta=2.0,
        )
        # Still within: 0.20 + 0.04 = 0.24 < 0.25
        self.assertTrue(result["allowed"])

    def test_high_beta_breach(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.high_beta_weight = 0.24
        result = rb.check_budget(
            "TSLA", "Auto", 0.05, exp, beta=2.0,
        )
        # 0.24 + 0.05 = 0.29 > 0.25 → scaled
        self.assertLess(result["size_scalar"], 1.0)


class TestCheckBudgetEarnings48h(unittest.TestCase):
    """A4: Earnings-within-48h exposure limit."""

    def test_no_earnings_no_check(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        result = rb.check_budget(
            "AAPL", "Tech", 0.05, exp,
            days_to_earnings=30,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["size_scalar"], 1.0)

    def test_earnings_breach(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.earnings_48h_weight = 0.09
        result = rb.check_budget(
            "AAPL", "Tech", 0.05, exp,
            days_to_earnings=1,
        )
        # 0.09 + 0.05 = 0.14 > 0.10 cap → scalar reduced
        self.assertLess(result["size_scalar"], 1.0)


class TestCheckBudgetRiskOff(unittest.TestCase):
    """A5: Gross exposure in risk-off regime."""

    def test_risk_on_no_gross_check(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.gross_exposure = 0.80
        result = rb.check_budget(
            "AAPL", "Tech", 0.05, exp,
            regime_risk="risk_on",
        )
        self.assertTrue(result["allowed"])

    def test_risk_off_gross_breach(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.gross_exposure = 0.48
        result = rb.check_budget(
            "AAPL", "Tech", 0.05, exp,
            regime_risk="risk_off",
        )
        # 0.48 + 0.05 = 0.53 > 0.50
        self.assertLess(result["size_scalar"], 1.0)


class TestCheckBudgetMaxPositions(unittest.TestCase):
    """A6: Max open positions limit."""

    def test_under_limit(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.open_positions = 10
        result = rb.check_budget(
            "AAPL", "Tech", 0.03, exp,
        )
        self.assertTrue(result["allowed"])

    def test_at_max(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.open_positions = 15
        result = rb.check_budget(
            "AAPL", "Tech", 0.03, exp,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["size_scalar"], 0.0)


class TestCheckBudgetCombined(unittest.TestCase):
    """A7: Combined violations → most restrictive scalar."""

    def test_two_violations_picks_min(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.sector_weights = {"Tech": 0.28}
        # Over single-name AND sector near limit
        result = rb.check_budget(
            "AAPL", "Tech", 0.10, exp,
        )
        # single-name scalar = 0.05/0.10 = 0.5
        # sector scalar = (0.30-0.28)/0.10 = 0.2
        # final = min(0.5, 0.2) = 0.2
        self.assertAlmostEqual(result["size_scalar"], 0.2, places=1)
        self.assertGreaterEqual(len(result["violations"]), 2)


class TestCheckBudgetPortfolioBeta(unittest.TestCase):
    """A8: Portfolio beta limit."""

    def test_beta_over_limit(self):
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.portfolio_beta = 1.8
        result = rb.check_budget(
            "NVDA", "Tech", 0.03, exp,
        )
        # scalar = 1.5 / 1.8 ≈ 0.833
        self.assertLess(result["size_scalar"], 1.0)
        self.assertGreater(result["size_scalar"], 0.0)


class TestCheckBudgetCustomLimits(unittest.TestCase):
    """A9: Custom limits override defaults."""

    def test_custom_max_positions(self):
        rb = PortfolioRiskBudget(
            limits={"max_positions": 5},
        )
        exp = ExposureSnapshot()
        exp.open_positions = 5
        result = rb.check_budget(
            "AAPL", "Tech", 0.03, exp,
        )
        self.assertFalse(result["allowed"])


# ═════════════════════════════════════════════════════════
#  B. ExposureSnapshot — build_exposure()
# ═════════════════════════════════════════════════════════

class TestBuildExposure(unittest.TestCase):
    """B1-B5: Build ExposureSnapshot from position list."""

    def _positions(self):
        return [
            {
                "ticker": "AAPL", "sector": "Tech",
                "market_value": 10000, "direction": "LONG",
                "beta": 1.2,
                "days_to_earnings": 30,
            },
            {
                "ticker": "TSLA", "sector": "Auto",
                "market_value": 8000, "direction": "LONG",
                "beta": 1.8,
                "days_to_earnings": 1,
            },
            {
                "ticker": "KO", "sector": "Consumer",
                "market_value": 5000, "direction": "LONG",
                "beta": 0.6,
                "days_to_earnings": 90,
            },
        ]

    def test_sector_weights(self):
        rb = PortfolioRiskBudget()
        snap = rb.build_exposure(self._positions(), equity=100000)
        self.assertAlmostEqual(snap.sector_weights["Tech"], 0.10, places=2)
        self.assertAlmostEqual(snap.sector_weights["Auto"], 0.08, places=2)
        self.assertAlmostEqual(snap.sector_weights["Consumer"], 0.05, places=2)

    def test_open_positions_count(self):
        rb = PortfolioRiskBudget()
        snap = rb.build_exposure(self._positions(), equity=100000)
        self.assertEqual(snap.open_positions, 3)

    def test_high_beta(self):
        rb = PortfolioRiskBudget()
        snap = rb.build_exposure(self._positions(), equity=100000)
        # Only TSLA beta=1.8 > 1.3 → weight = 8000/100000 = 0.08
        self.assertAlmostEqual(snap.high_beta_weight, 0.08, places=2)

    def test_earnings_48h(self):
        rb = PortfolioRiskBudget()
        snap = rb.build_exposure(self._positions(), equity=100000)
        # TSLA has days_to_earnings=1 → 8000/100000 = 0.08
        self.assertIn("TSLA", snap.earnings_48h_tickers)
        self.assertAlmostEqual(snap.earnings_48h_weight, 0.08, places=2)

    def test_gross_net_exposure(self):
        rb = PortfolioRiskBudget()
        positions = self._positions() + [{
            "ticker": "SQQQ", "sector": "ETF",
            "market_value": 3000, "direction": "SHORT",
            "beta": -3.0,
        }]
        snap = rb.build_exposure(positions, equity=100000)
        # long = 23000, short = 3000
        self.assertAlmostEqual(snap.long_weight, 0.23, places=2)
        self.assertAlmostEqual(snap.short_weight, 0.03, places=2)
        self.assertAlmostEqual(snap.gross_exposure, 0.26, places=2)
        self.assertAlmostEqual(snap.net_exposure, 0.20, places=2)

    def test_empty_positions(self):
        rb = PortfolioRiskBudget()
        snap = rb.build_exposure([], equity=100000)
        self.assertEqual(snap.open_positions, 0)
        self.assertEqual(snap.gross_exposure, 0.0)

    def test_exposure_to_dict(self):
        snap = ExposureSnapshot()
        snap.sector_weights = {"Tech": 0.15}
        d = snap.to_dict()
        self.assertIn("sector_weights", d)
        self.assertIn("portfolio_beta", d)
        self.assertIn("open_positions", d)


# ═════════════════════════════════════════════════════════
#  C. CoverageFunnel
# ═════════════════════════════════════════════════════════

class TestCoverageFunnel(unittest.TestCase):
    """C1-C3: Funnel metrics."""

    def test_pass_rate(self):
        f = CoverageFunnel(
            watched=100, eligible=60, ranked=50,
            approved=10, rejected=40, executed=5,
        )
        self.assertAlmostEqual(f.pass_rate, 0.05, places=2)

    def test_rejection_rate(self):
        f = CoverageFunnel(
            watched=100, eligible=60, ranked=50,
            approved=10, rejected=40, executed=5,
        )
        self.assertAlmostEqual(f.rejection_rate, 0.80, places=2)

    def test_empty_funnel(self):
        f = CoverageFunnel()
        self.assertEqual(f.pass_rate, 0)
        self.assertEqual(f.rejection_rate, 0)

    def test_to_dict(self):
        f = CoverageFunnel(watched=10, executed=2)
        d = f.to_dict()
        self.assertEqual(d["watched"], 10)
        self.assertEqual(d["executed"], 2)


# ═════════════════════════════════════════════════════════
#  D. ProfessionalKPI — record + compute
# ═════════════════════════════════════════════════════════

class TestProfessionalKPIRecording(unittest.TestCase):
    """D1-D2: Record trades and cycles."""

    def test_record_trade_stores(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.5, r_multiple=1.5, hold_hours=12)
        kpi.record_trade(pnl_pct=-1.0, r_multiple=-0.5, hold_hours=6)
        self.assertEqual(len(kpi._trades), 2)

    def test_record_cycle_counts(self):
        kpi = ProfessionalKPI()
        kpi.record_cycle(traded=True)
        kpi.record_cycle(traded=False)
        kpi.record_cycle(traded=True)
        self.assertEqual(kpi._cycles, 3)
        self.assertEqual(kpi._no_trade_cycles, 1)


class TestProfessionalKPICompute(unittest.TestCase):
    """D3-D9: Compute all KPIs."""

    def _make_kpi(self):
        kpi = ProfessionalKPI()
        # 6 wins, 4 losses → WR = 60%
        wins = [
            (3.0, 2.0, 24), (1.5, 1.0, 18), (2.0, 1.5, 30),
            (4.0, 2.5, 12), (1.0, 0.8, 20), (0.5, 0.3, 8),
        ]
        losses = [
            (-1.5, -1.0, 10), (-2.0, -1.2, 15),
            (-1.0, -0.8, 6), (-0.8, -0.5, 4),
        ]
        for pnl, r, h in wins:
            kpi.record_trade(pnl_pct=pnl, r_multiple=r, hold_hours=h)
        for pnl, r, h in losses:
            kpi.record_trade(pnl_pct=pnl, r_multiple=r, hold_hours=h)
        # 20 cycles, 12 no-trade
        for i in range(20):
            kpi.record_cycle(traded=(i < 8))
        return kpi

    def test_win_rate(self):
        snap = self._make_kpi().compute()
        self.assertAlmostEqual(snap.win_rate, 0.60, places=2)

    def test_net_expectancy_positive(self):
        snap = self._make_kpi().compute()
        # 60% win rate with positive wins, net expectancy should > 0
        self.assertGreater(snap.net_expectancy_r, 0)

    def test_avg_r_multiple(self):
        snap = self._make_kpi().compute()
        # Average of all R multiples
        self.assertIsInstance(snap.avg_r_multiple, float)
        self.assertNotEqual(snap.avg_r_multiple, 0)

    def test_profit_factor(self):
        snap = self._make_kpi().compute()
        # sum(wins) = 12.0, sum(abs(losses)) = 5.3 → PF ≈ 2.26
        self.assertGreater(snap.profit_factor, 1.0)

    def test_max_drawdown_negative(self):
        snap = self._make_kpi().compute()
        # Max drawdown is non-positive
        self.assertLessEqual(snap.max_drawdown, 0)

    def test_cvar_95(self):
        snap = self._make_kpi().compute()
        # CVaR-95 is in the negative tail
        self.assertLessEqual(snap.cvar_95, 0)

    def test_turnover(self):
        snap = self._make_kpi().compute()
        # 10 trades / 20 cycles = 0.5
        self.assertAlmostEqual(snap.turnover, 0.5, places=1)

    def test_no_trade_rate(self):
        snap = self._make_kpi().compute()
        # 12 no-trade / 20 cycles = 0.60
        self.assertAlmostEqual(snap.no_trade_rate, 0.60, places=2)

    def test_total_trades(self):
        snap = self._make_kpi().compute()
        self.assertEqual(snap.total_trades, 10)

    def test_total_cycles(self):
        snap = self._make_kpi().compute()
        self.assertEqual(snap.total_cycles, 20)


class TestKPIEmpty(unittest.TestCase):
    """D10: KPI compute with no trades."""

    def test_empty_returns_defaults(self):
        kpi = ProfessionalKPI()
        snap = kpi.compute()
        self.assertEqual(snap.total_trades, 0)
        self.assertEqual(snap.win_rate, 0)
        self.assertEqual(snap.profit_factor, 0)


# ═════════════════════════════════════════════════════════
#  E. KPISnapshot — serialization
# ═════════════════════════════════════════════════════════

class TestKPISnapshotSerialization(unittest.TestCase):
    """E1-E2: to_dict and summary_text."""

    def test_to_dict_has_all_keys(self):
        snap = KPISnapshot(
            net_expectancy_r=0.15,
            profit_factor=1.8,
            win_rate=0.62,
            max_drawdown=-0.05,
        )
        d = snap.to_dict()
        required = [
            "net_expectancy_r", "profit_factor",
            "win_rate", "max_drawdown", "cvar_95",
            "turnover", "no_trade_rate",
            "total_trades", "funnel",
        ]
        for key in required:
            self.assertIn(key, d)

    def test_summary_text(self):
        snap = KPISnapshot(
            net_expectancy_r=0.15,
            profit_factor=1.8,
            win_rate=0.62,
            max_drawdown=-0.05,
            total_trades=50,
        )
        text = snap.summary_text()
        self.assertIn("Professional KPI", text)
        self.assertIn("Profit Factor", text)
        self.assertIn("Win Rate", text)
        self.assertIn("Coverage Funnel", text)


class TestKPICalibrationError(unittest.TestCase):
    """E3: Calibration error between predicted and actual WR."""

    def test_calibration_perfect(self):
        kpi = ProfessionalKPI()
        # All predicted 50%, actual 50% wins
        kpi.record_trade(1.0, 0.5, 12, predicted_wr=0.5)
        kpi.record_trade(-1.0, -0.5, 12, predicted_wr=0.5)
        snap = kpi.compute()
        self.assertAlmostEqual(snap.calibration_error, 0.0, places=2)

    def test_calibration_off(self):
        kpi = ProfessionalKPI()
        # Predicted 80% but only 50% actual
        kpi.record_trade(1.0, 0.5, 12, predicted_wr=0.8)
        kpi.record_trade(-1.0, -0.5, 12, predicted_wr=0.8)
        snap = kpi.compute()
        # |0.80 - 0.50| = 0.30
        self.assertAlmostEqual(snap.calibration_error, 0.30, places=2)


class TestKPIFunnelAggregation(unittest.TestCase):
    """E4: Funnel aggregation across cycles."""

    def test_funnel_sums(self):
        kpi = ProfessionalKPI()
        f1 = CoverageFunnel(
            watched=100, eligible=60, ranked=50,
            approved=10, rejected=40, executed=3,
        )
        f2 = CoverageFunnel(
            watched=80, eligible=40, ranked=30,
            approved=5, rejected=25, executed=2,
        )
        kpi.record_cycle(traded=True, funnel=f1)
        kpi.record_cycle(traded=True, funnel=f2)
        # Need at least one trade so compute() doesn't
        # return early before funnel aggregation
        kpi.record_trade(pnl_pct=1.0, r_multiple=0.5)
        snap = kpi.compute()
        self.assertEqual(snap.funnel.watched, 180)
        self.assertEqual(snap.funnel.executed, 5)
        self.assertEqual(snap.funnel.rejected, 65)


# ═════════════════════════════════════════════════════════
#  F. Wiring — auto_trading_engine source inspection
# ═════════════════════════════════════════════════════════

class TestAutoTradingEngineWiring(unittest.TestCase):
    """F1-F3: Verify wiring in auto_trading_engine source."""

    @classmethod
    def setUpClass(cls):
        ate_path = os.path.join(
            BASE, "src", "engines", "auto_trading_engine.py",
        )
        with open(ate_path) as f:
            cls.src = f.read()

    def test_imports_risk_budget(self):
        self.assertIn(
            "from src.engines.portfolio_risk_budget "
            "import PortfolioRiskBudget",
            self.src,
        )

    def test_imports_professional_kpi(self):
        self.assertIn(
            "from src.engines.professional_kpi "
            "import ProfessionalKPI",
            self.src,
        )

    def test_init_risk_budget(self):
        self.assertIn(
            "self.risk_budget = PortfolioRiskBudget()",
            self.src,
        )

    def test_init_kpi(self):
        self.assertIn(
            "self.kpi = ProfessionalKPI()",
            self.src,
        )

    def test_sizing_has_budget_mult(self):
        self.assertIn("budget_mult", self.src)
        self.assertIn(
            "risk_budget.check_budget",
            self.src,
        )

    def test_kpi_record_trade(self):
        self.assertIn(
            "self.kpi.record_trade(",
            self.src,
        )

    def test_kpi_record_cycle(self):
        self.assertIn(
            "self.kpi.record_cycle(",
            self.src,
        )


# ═════════════════════════════════════════════════════════
#  G. Integration — budget + KPI together
# ═════════════════════════════════════════════════════════

class TestIntegrationBudgetAndKPI(unittest.TestCase):
    """G1-G2: Combined scenarios."""

    def test_budget_blocks_then_kpi_records(self):
        """A blocked trade should still be recordable in KPI."""
        rb = PortfolioRiskBudget()
        exp = ExposureSnapshot()
        exp.open_positions = 15
        result = rb.check_budget("AAPL", "Tech", 0.03, exp)
        self.assertFalse(result["allowed"])

        # KPI still works independently
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.0, r_multiple=1.0)
        snap = kpi.compute()
        self.assertEqual(snap.total_trades, 1)

    def test_full_flow(self):
        """Build exposure → check budget → record KPI."""
        rb = PortfolioRiskBudget()
        positions = [
            {
                "ticker": "AAPL", "sector": "Tech",
                "market_value": 5000, "direction": "LONG",
                "beta": 1.2,
            },
        ]
        exp = rb.build_exposure(positions, equity=100000)
        result = rb.check_budget(
            "GOOGL", "Tech", 0.04, exp,
        )
        self.assertTrue(result["allowed"])

        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=1.5, r_multiple=0.8)
        kpi.record_cycle(traded=True)
        snap = kpi.compute()
        self.assertEqual(snap.total_trades, 1)
        self.assertEqual(snap.total_cycles, 1)


if __name__ == "__main__":
    unittest.main()
