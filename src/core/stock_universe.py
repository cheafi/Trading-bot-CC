"""
Central stock universe — single source for watchlists, RS ranking, briefs, and demos.

Loads from ``data/universe.json`` (core + extended tiers). Scan engine uses the
larger ``US_UNIVERSE`` in scanners; this module feeds CC X surfaces that need a
focused liquid-US set with index/ETF classification.
"""

from __future__ import annotations

from typing import Dict, List

from src.core.universe_loader import LoadedUniverse, get_universe, validate_ticker


def _dedupe_lists(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for items in lists:
        for raw in items:
            tk = validate_ticker(raw)
            if tk and tk not in seen:
                seen.add(tk)
                out.append(tk)
    return out


_loaded: LoadedUniverse = get_universe()

# ── Tiered ticker lists (from data/universe.json) ─────────────────

CORE_EQUITIES: list[str] = [
    r.ticker for r in _loaded.records if r.asset_class == "equity" and r.tier == "core"
]
EXTENDED_EQUITIES: list[str] = [
    r.ticker
    for r in _loaded.records
    if r.asset_class == "equity" and r.tier == "extended"
]

INDEX_ETFS: list[str] = _loaded.by_asset_class("index_proxy")
SECTOR_ETFS: list[str] = [
    r.ticker
    for r in _loaded.records
    if r.asset_class == "etf" and r.sector == "ETF" and r.theme in {
        "Technology",
        "Financials",
        "Healthcare",
        "Energy",
        "Industrials",
        "Communication",
        "Consumer Disc.",
        "Consumer Staples",
        "Real Estate",
        "Utilities",
        "Materials",
    }
]
THEMATIC_ETFS: list[str] = [
    r.ticker for r in _loaded.records if r.asset_class == "etf" and r.ticker not in SECTOR_ETFS
]

# Liquid US equities — mega/large cap + high-volume growth (core tier equities)
CORE_WATCHLIST: list[str] = list(CORE_EQUITIES)

# Relative-strength ranking universe — core equities + index/sector/thematic benchmarks
RS_UNIVERSE: list[str] = _dedupe_lists(
    CORE_EQUITIES
    + INDEX_ETFS
    + [r.ticker for r in _loaded.records if r.asset_class == "etf" and r.tier == "core"]
)

ALL_ETFS: list[str] = _loaded.by_asset_class("etf") + INDEX_ETFS

# Monitor-pool coverage — core + extended (research tier)
OPPORTUNITY_COVERAGE_UNIVERSE: list[str] = _loaded.all_tickers

# Tier caps from config — core scanned first to protect rate limits
TIER_SCAN_CAPS: dict[str, int] = dict(_loaded.tier_caps)
CORE_TIER_TICKERS: list[str] = _loaded.core_tickers
EXTENDED_TIER_TICKERS: list[str] = _loaded.extended_tickers

_ETF_SET = frozenset(ALL_ETFS)
_INDEX_SET = frozenset(INDEX_ETFS)

# Build sector / theme maps from JSON records
SECTOR_BY_TICKER: Dict[str, str] = {}
ETF_THEME_BY_TICKER: Dict[str, str] = {}
ASSET_CLASS_BY_TICKER: Dict[str, str] = {}
for _rec in _loaded.records:
    if _rec.sector:
        SECTOR_BY_TICKER[_rec.ticker] = _rec.sector
    if _rec.theme:
        ETF_THEME_BY_TICKER[_rec.ticker] = _rec.theme
    ASSET_CLASS_BY_TICKER[_rec.ticker] = _rec.asset_class

# Short sector labels (playbook RS cards)
RS_SECTOR_SHORT: dict[str, str] = {
    "Technology": "Tech",
    "Consumer Discretionary": "Consumer",
    "Communication Services": "Consumer",
    "Financials": "Finance",
    "Healthcare": "Health",
    "Energy": "Energy",
    "Industrials": "Industrial",
    "Consumer Staples": "Staples",
    "Index": "Index",
    "ETF": "ETF",
}

# Command palette / search popular row
POPULAR_TICKERS: list[str] = [
    "NVDA",
    "AAPL",
    "MSFT",
    "TSLA",
    "META",
    "AMZN",
    "GOOGL",
    "AMD",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "PLTR",
    "CRWD",
    "COIN",
    "HOOD",
    "SMCI",
    "ARM",
    "SOXX",
    "XLK",
]

# Demo portfolio seed (diversified sectors)
DEMO_PORTFOLIO_POSITIONS: list[dict] = [
    {"ticker": "AAPL", "shares": 100},
    {"ticker": "MSFT", "shares": 50},
    {"ticker": "NVDA", "shares": 30},
    {"ticker": "GOOGL", "shares": 40},
    {"ticker": "META", "shares": 35},
    {"ticker": "AMD", "shares": 60},
    {"ticker": "JPM", "shares": 45},
    {"ticker": "XOM", "shares": 80},
    {"ticker": "LLY", "shares": 15},
    {"ticker": "PLTR", "shares": 100},
    {"ticker": "SPY", "shares": 25},
    {"ticker": "QQQ", "shares": 20},
]


def tiered_scan_universe(*, include_extended: bool = True) -> list[str]:
    """Core tier first, then extended — honors scan_cap from universe.json."""
    core_cap = TIER_SCAN_CAPS.get("core", 150)
    ext_cap = TIER_SCAN_CAPS.get("extended", 400)
    ordered = list(CORE_TIER_TICKERS[:core_cap])
    if include_extended:
        ordered = _dedupe_lists(ordered, EXTENDED_TIER_TICKERS[:ext_cap])
    return ordered


def is_index_or_etf(ticker: str) -> bool:
    """True for broad indices and sector/thematic ETFs."""
    return str(ticker or "").strip().upper() in _ETF_SET


def is_broad_index(ticker: str) -> bool:
    """True for SPY/QQQ/IWM-style benchmark ETFs."""
    return str(ticker or "").strip().upper() in _INDEX_SET


def asset_class_for(ticker: str) -> str:
    """Asset class label for scoring and UI: equity | etf | index_proxy."""
    tk = str(ticker or "").strip().upper()
    return ASSET_CLASS_BY_TICKER.get(tk, "equity")


def etf_theme_for(ticker: str) -> str:
    """Human theme for ETF/index cards."""
    tk = str(ticker or "").strip().upper()
    return ETF_THEME_BY_TICKER.get(tk, "ETF")


def rs_sector_for(ticker: str) -> str:
    """Sector label for RS universe cards."""
    tk = str(ticker or "").strip().upper()
    if is_broad_index(tk):
        return "Index"
    if is_index_or_etf(tk):
        return "ETF"
    full = SECTOR_BY_TICKER.get(tk, "Other")
    return RS_SECTOR_SHORT.get(full, full[:12] if full != "Other" else "Other")


def universe_summary() -> dict:
    """Metadata for /api/health and ops."""
    summary = _loaded.summary()
    return {
        "core_watchlist_count": len(CORE_WATCHLIST),
        "rs_universe_count": len(RS_UNIVERSE),
        "index_etf_count": len(ALL_ETFS),
        "coverage_universe_count": len(OPPORTUNITY_COVERAGE_UNIVERSE),
        "popular_count": len(POPULAR_TICKERS),
        "demo_positions": len(DEMO_PORTFOLIO_POSITIONS),
        "sectors_covered": len(set(SECTOR_BY_TICKER.values())),
        "equity_count": summary["equity_count"],
        "etf_count": summary["etf_count"],
        "index_proxy_count": summary["index_proxy_count"],
        "core_tier_count": summary["core_count"],
        "extended_tier_count": summary["extended_count"],
        "universe_source": summary["source"],
        "universe_provenance": summary["provenance"],
        "universe_version": summary["version"],
        "tier_scan_caps": summary["tier_caps"],
    }
