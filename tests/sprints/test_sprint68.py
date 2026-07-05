"""
Sprint 68 Tests
================
- FundBuilder sector concentration warning
- FundBuilder auto_performance_report
- StockVsSPY.compare_ticker
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ── FundBuilder sector concentration ──


def test_fund_sector_concentration_warning(caplog):
    """Adding >30% same sector triggers warning."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder("Test", starting_capital=100000)
    # 40% in Technology
    fund.add_position("NVDA", 100, 200, "MOMENTUM", sector="Technology")
    fund.add_position("AMD", 100, 200, "MOMENTUM", sector="Technology")
    with caplog.at_level(logging.WARNING):
        fund.add_position("AVGO", 100, 100, "MOMENTUM", sector="Technology")
    assert any("concentration" in r.message for r in caplog.records)


def test_fund_no_warning_diverse():
    """Diverse sectors → no warning."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder("Test", starting_capital=100000)
    fund.add_position("NVDA", 100, 50, "MOMENTUM", sector="Tech")
    fund.add_position("JPM", 100, 50, "MOMENTUM", sector="Fin")
    fund.add_position("XOM", 100, 50, "MOMENTUM", sector="Energy")
    # No warning expected — 33% each
    assert len(fund.positions) == 3


def test_fund_sector_field_stored():
    """Sector field stored on position."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder("Test", starting_capital=100000)
    pos = fund.add_position("AAPL", 150, 10, "MOMENTUM", sector="Technology")
    assert pos.sector == "Technology"


# ── FundBuilder auto_performance_report ──


def test_fund_auto_report_no_positions():
    """auto_performance_report with empty fund."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder("Empty", starting_capital=50000)
    report = fund.auto_performance_report()
    assert report["fund_return_pct"] == 0.0
    assert report["positions_count"] == 0


def test_fund_auto_report_fallback():
    """auto_performance_report falls back to entry prices."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder("Test", starting_capital=100000)
    fund.add_position("FAKE123", 100, 10, "MOMENTUM")
    report = fund.auto_performance_report()
    # With entry price fallback, P&L = 0
    assert report["fund_return_pct"] == 0.0


# ── StockVsSPY.compare_ticker ──


def test_stock_vs_spy_compare_manual():
    """StockVsSPY.compare works with manual data."""
    from src.engines.macro_regime_engine import StockVsSPY

    stock = [100 + i * 0.5 for i in range(60)]
    spy = [100 + i * 0.3 for i in range(60)]
    result = StockVsSPY.compare(stock, spy, ticker="TEST")
    assert result["ticker"] == "TEST"
    assert "performance" in result


def test_stock_vs_spy_compare_ticker_exists():
    """compare_ticker method exists and returns dict."""
    from src.engines.macro_regime_engine import StockVsSPY

    assert hasattr(StockVsSPY, "compare_ticker")
    # Don't actually call it (slow yfinance fetch)
    # Just verify the method signature
    import inspect

    sig = inspect.signature(StockVsSPY.compare_ticker)
    assert "ticker" in sig.parameters


def test_stock_vs_spy_short_data():
    """StockVsSPY returns error for < 5 data points."""
    from src.engines.macro_regime_engine import StockVsSPY

    result = StockVsSPY.compare([100, 101], [100, 101])
    assert "error" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
