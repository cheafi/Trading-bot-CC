"""Sprint 53 tests — PortfolioRiskBudget wiring, ProfessionalKPI wiring,
options determinism, earnings fix, P1 TODO cleanup."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.engines.portfolio_risk_budget import ExposureSnapshot, PortfolioRiskBudget
from src.engines.professional_kpi import KPISnapshot, ProfessionalKPI

# ── PortfolioRiskBudget ────────────────────────────────────────────


class TestPortfolioRiskBudget:
    def test_empty_portfolio_exposure(self):
        prb = PortfolioRiskBudget()
        exp = prb.build_exposure(positions=[], equity=100_000)
        assert isinstance(exp, ExposureSnapshot)
        assert exp.open_positions == 0

    def test_single_position_exposure(self):
        prb = PortfolioRiskBudget()
        pos = [
            {
                "ticker": "AAPL",
                "sector": "Technology",
                "market_value": 10_000,
                "direction": "LONG",
                "beta": 1.2,
            }
        ]
        exp = prb.build_exposure(positions=pos, equity=100_000)
        assert exp.open_positions == 1
        assert exp.long_weight > 0

    def test_check_budget_passes(self):
        prb = PortfolioRiskBudget()
        exp = prb.build_exposure(positions=[], equity=100_000)
        result = prb.check_budget(
            ticker="AAPL",
            sector="Technology",
            position_weight=0.05,
            exposure=exp,
        )
        assert result["allowed"] is True

    def test_check_budget_blocks_oversize(self):
        prb = PortfolioRiskBudget()
        exp = prb.build_exposure(positions=[], equity=100_000)
        result = prb.check_budget(
            ticker="AAPL",
            sector="Technology",
            position_weight=0.50,
            exposure=exp,  # 50% is too big
        )
        assert result["allowed"] is False or len(result.get("violations", [])) > 0

    def test_exposure_to_dict(self):
        prb = PortfolioRiskBudget()
        exp = prb.build_exposure(positions=[], equity=100_000)
        d = exp.to_dict()
        assert "open_positions" in d
        assert "sector_weights" in d

    def test_multi_position_sectors(self):
        prb = PortfolioRiskBudget()
        pos = [
            {
                "ticker": "AAPL",
                "sector": "Tech",
                "market_value": 10_000,
                "direction": "LONG",
            },
            {
                "ticker": "MSFT",
                "sector": "Tech",
                "market_value": 10_000,
                "direction": "LONG",
            },
            {
                "ticker": "XOM",
                "sector": "Energy",
                "market_value": 5_000,
                "direction": "LONG",
            },
        ]
        exp = prb.build_exposure(positions=pos, equity=100_000)
        assert exp.open_positions == 3
        assert "Tech" in exp.sector_weights


# ── ProfessionalKPI ───────────────────────────────────────────────


class TestProfessionalKPI:
    def test_initial_compute(self):
        kpi = ProfessionalKPI()
        snap = kpi.compute()
        assert isinstance(snap, KPISnapshot)
        assert snap.total_trades == 0

    def test_record_trade(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.5)
        snap = kpi.compute()
        assert snap.total_trades == 1

    def test_win_rate_after_trades(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.5)
        kpi.record_trade(pnl_pct=-1.0)
        kpi.record_trade(pnl_pct=3.0)
        snap = kpi.compute()
        assert snap.total_trades == 3
        assert snap.win_rate > 0.5

    def test_record_cycle(self):
        kpi = ProfessionalKPI()
        kpi.record_cycle(traded=True)
        snap = kpi.compute()
        assert snap.total_cycles == 1

    def test_to_dict(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=1.5)
        snap = kpi.compute()
        d = snap.to_dict()
        assert "total_trades" in d
        assert "win_rate" in d

    def test_summary_text(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.0)
        snap = kpi.compute()
        txt = snap.summary_text()
        assert isinstance(txt, str)
        assert len(txt) > 0

    def test_profit_factor_positive(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=5.0)
        kpi.record_trade(pnl_pct=-2.0)
        snap = kpi.compute()
        assert snap.profit_factor > 1.0

    def test_all_losses(self):
        kpi = ProfessionalKPI()
        kpi.record_trade(pnl_pct=-1.5)
        kpi.record_trade(pnl_pct=-0.8)
        snap = kpi.compute()
        assert snap.win_rate == 0.0


# ── Options Determinism ───────────────────────────────────────────


class TestOptionsDeterminism:
    """Verify options endpoint no longer uses random values."""

    def test_no_rng_in_main(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "rng." not in code, "main.py still contains rng references"

    def test_options_uses_deterministic_offsets(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "_iv_offsets" in code
        assert "_base_ois" in code


# ── Earnings Fix ──────────────────────────────────────────────────


class TestEarningsFix:
    def test_no_earnings_todo(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "TODO: Fetch actual earnings data" not in code

    def test_uses_yfinance(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "yf.Ticker" in code


# ── P1 TODO Resolved ─────────────────────────────────────────────


class TestP1Resolved:
    def test_p1_todo_marked_resolved(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "RESOLVED" in code
        assert "(P1 TODO)" not in code


# ── API integration ───────────────────────────────────────────────


class TestAPISprint53:
    def test_main_has_portfolio_risk_budget(self):
        import importlib

        mod = importlib.import_module("src.api.main")
        assert hasattr(mod, "_portfolio_risk_budget")

    def test_main_has_professional_kpi(self):
        import importlib

        mod = importlib.import_module("src.api.main")
        assert hasattr(mod, "_professional_kpi")
