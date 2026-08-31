"""Central stock universe config and JSON loader validation."""

import json
from pathlib import Path

import pytest

from src.core.stock_universe import (
    CORE_WATCHLIST,
    DEMO_PORTFOLIO_POSITIONS,
    OPPORTUNITY_COVERAGE_UNIVERSE,
    RS_UNIVERSE,
    asset_class_for,
    is_broad_index,
    is_index_or_etf,
    rs_sector_for,
    tiered_scan_universe,
    universe_summary,
)
from src.core.universe_loader import (
    load_universe,
    parse_universe,
    reset_universe_cache,
    validate_ticker,
)


def test_core_watchlist_size():
    assert len(CORE_WATCHLIST) >= 100


def test_rs_universe_expanded():
    assert len(RS_UNIVERSE) >= 80
    assert "SPY" in RS_UNIVERSE
    assert "QQQ" in RS_UNIVERSE
    assert "IWM" in RS_UNIVERSE
    assert "DIA" in RS_UNIVERSE
    assert "XLK" in RS_UNIVERSE
    assert "SOXX" in RS_UNIVERSE


def test_opportunity_coverage_universe():
    assert len(OPPORTUNITY_COVERAGE_UNIVERSE) >= len(RS_UNIVERSE)
    assert is_index_or_etf("QQQ")
    assert is_broad_index("SPY")
    assert asset_class_for("SPY") == "index_proxy"
    assert asset_class_for("XLK") == "etf"
    assert asset_class_for("NVDA") == "equity"
    assert "NVDA" in OPPORTUNITY_COVERAGE_UNIVERSE


def test_demo_portfolio_diversified():
    assert len(DEMO_PORTFOLIO_POSITIONS) >= 8
    tickers = {p["ticker"] for p in DEMO_PORTFOLIO_POSITIONS}
    assert len(tickers) == len(DEMO_PORTFOLIO_POSITIONS)


def test_rs_sector_for_known():
    assert rs_sector_for("NVDA") == "Tech"
    assert rs_sector_for("SPY") == "Index"
    assert rs_sector_for("XLK") == "ETF"


def test_universe_summary_counts():
    s = universe_summary()
    assert s["core_watchlist_count"] == len(CORE_WATCHLIST)
    assert s["rs_universe_count"] == len(RS_UNIVERSE)
    assert s["coverage_universe_count"] >= s["rs_universe_count"]
    assert s["equity_count"] >= 200
    assert s["etf_count"] >= 50
    assert s["index_proxy_count"] >= 10
    assert s["universe_source"] == "curated_liquid_us"
    assert s["universe_provenance"] == "static_config"
    assert s["tier_scan_caps"]["core"] >= 100


def test_tiered_scan_universe_core_first():
    tiered = tiered_scan_universe()
    assert len(tiered) >= 150
    assert tiered[0] in RS_UNIVERSE
    assert "SPY" in tiered[:50]


def test_validate_ticker_rules():
    assert validate_ticker("nvda") == "NVDA"
    assert validate_ticker("BRK.B") == "BRK.B"
    assert validate_ticker("") is None
    assert validate_ticker("INVALID TICKER") is None
    assert validate_ticker("A" * 20) is None


def test_universe_json_loads():
    loaded = load_universe()
    assert loaded.summary()["total_symbols"] >= 400
    assert not loaded.errors


def test_universe_json_rejects_invalid_entries(tmp_path):
    bad = {
        "meta": {"source": "test", "provenance": "unit"},
        "tiers": {"core": {"scan_cap": 10}},
        "symbols": [
            {"ticker": "GOOD", "asset_class": "equity", "tier": "core"},
            {"ticker": "bad ticker", "asset_class": "equity", "tier": "core"},
            {"ticker": "SPY", "asset_class": "not_valid", "tier": "core"},
        ],
    }
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    parsed = parse_universe(json.loads(path.read_text()))
    tickers = {r.ticker for r in parsed.records}
    assert "GOOD" in tickers
    assert "SPY" not in tickers
    assert len(parsed.errors) >= 2


def test_universe_json_file_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "data" / "universe.json").is_file()
