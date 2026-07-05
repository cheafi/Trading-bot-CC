"""Central stock universe config."""

from src.core.stock_universe import (
    CORE_WATCHLIST,
    DEMO_PORTFOLIO_POSITIONS,
    RS_UNIVERSE,
    rs_sector_for,
    universe_summary,
)


def test_core_watchlist_size():
    assert len(CORE_WATCHLIST) >= 60


def test_rs_universe_expanded():
    assert len(RS_UNIVERSE) >= 50
    assert "SPY" in RS_UNIVERSE


def test_demo_portfolio_diversified():
    assert len(DEMO_PORTFOLIO_POSITIONS) >= 8
    tickers = {p["ticker"] for p in DEMO_PORTFOLIO_POSITIONS}
    assert len(tickers) == len(DEMO_PORTFOLIO_POSITIONS)


def test_rs_sector_for_known():
    assert rs_sector_for("NVDA") == "Tech"


def test_universe_summary_counts():
    s = universe_summary()
    assert s["core_watchlist_count"] == len(CORE_WATCHLIST)
    assert s["rs_universe_count"] == len(RS_UNIVERSE)
