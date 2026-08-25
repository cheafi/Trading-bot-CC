"""
Central stock universe — single source for watchlists, RS ranking, briefs, and demos.

Scan engine uses the larger ``_SCAN_WATCHLIST`` in main.py; this module feeds
surfaces that need a focused liquid-US set without duplicating ticker strings.
"""

from __future__ import annotations

# Liquid US equities — mega/large cap + high-volume growth (≈80 names)
CORE_WATCHLIST: list[str] = [
    # Mega tech
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "GOOG",
    "AMZN",
    "META",
    "TSLA",
    # Semis / hardware
    "AMD",
    "AVGO",
    "INTC",
    "QCOM",
    "TXN",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "ADI",
    "MRVL",
    "ON",
    "ARM",
    "SMCI",
    "CRDO",
    "ANET",
    "DELL",
    # Software / cloud
    "CRM",
    "ORCL",
    "ADBE",
    "NOW",
    "INTU",
    "PANW",
    "CRWD",
    "SNOW",
    "DDOG",
    "ZS",
    "NET",
    "PLTR",
    "SHOP",
    "UBER",
    "ABNB",
    "COIN",
    "HOOD",
    # Consumer / media
    "NFLX",
    "DIS",
    "CMCSA",
    "NKE",
    "SBUX",
    "MCD",
    "COST",
    "WMT",
    "HD",
    "LOW",
    # Financials
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "V",
    "MA",
    "AXP",
    "SCHW",
    "BLK",
    "PYPL",
    # Healthcare
    "UNH",
    "LLY",
    "JNJ",
    "PFE",
    "ABBV",
    "MRK",
    "GILD",
    "REGN",
    "ISRG",
    "VRTX",
    # Energy / industrials
    "XOM",
    "CVX",
    "COP",
    "BA",
    "CAT",
    "GE",
    "RTX",
    "LMT",
    "DE",
    "HON",
    # Fintech / speculative liquid
    "SOFI",
    "MSTR",
    "IONQ",
    "RBLX",
]

# Relative-strength ranking universe (subset — fast refresh)
RS_UNIVERSE: list[str] = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "TSLA",
    "AMD",
    "AVGO",
    "INTC",
    "QCOM",
    "MU",
    "SMCI",
    "ARM",
    "CRDO",
    "ANET",
    "PLTR",
    "CRM",
    "ORCL",
    "ADBE",
    "NOW",
    "PANW",
    "CRWD",
    "SNOW",
    "DDOG",
    "NET",
    "ZS",
    "NFLX",
    "UBER",
    "COIN",
    "HOOD",
    "SHOP",
    "ABNB",
    "PYPL",
    "XYZ",
    "JPM",
    "V",
    "MA",
    "BAC",
    "GS",
    "XOM",
    "CVX",
    "LLY",
    "UNH",
    "JNJ",
    "COST",
    "WMT",
    "HD",
    "NKE",
    "BA",
    "CAT",
    "GE",
    "SOFI",
    "MSTR",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    # Sector & thematic ETFs (RS cards + Discovery leaders)
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLI",
    "XLC",
    "XLY",
    "XLP",
    "XLRE",
    "XLU",
    "XLB",
    "SOXX",
    "SMH",
    "IGV",
    "ARKK",
    "KWEB",
    "FXI",
    "EEM",
    "GLD",
    "VNQ",
    "GDX",
    "XBI",
    "ITA",
]

# Broad index ETFs
INDEX_ETFS: list[str] = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "RSP",
    "MDY",
    "VTI",
    "VOO",
    "IVV",
    "SPLG",
]

# GICS sector SPDRs + key rotation proxies
SECTOR_ETFS: list[str] = [
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLI",
    "XLC",
    "XLY",
    "XLP",
    "XLRE",
    "XLU",
    "XLB",
]

# Thematic / industry ETFs for sector breadth
THEMATIC_ETFS: list[str] = [
    "SOXX",
    "SMH",
    "IGV",
    "ARKK",
    "ARKW",
    "ARKG",
    "ARKQ",
    "HACK",
    "WCLD",
    "CLOU",
    "KWEB",
    "FXI",
    "EEM",
    "VWO",
    "GLD",
    "SLV",
    "TLT",
    "HYG",
    "VNQ",
    "GDX",
    "GDXJ",
    "XBI",
    "IBB",
    "ITA",
    "KRE",
    "XRT",
    "TAN",
    "ICLN",
    "USO",
    "BITO",
    "QQQM",
    "SCHD",
    "XME",
    "BOTZ",
    "SKYY",
    "JETS",
    "XHB",
    "XOP",
]

# Liquid mid/large names often absent from brief
LIQUID_MID_LARGE: list[str] = [
    "ADSK",
    "WDAY",
    "TEAM",
    "MELI",
    "SE",
    "GRAB",
    "APP",
    "RDDT",
    "DUOL",
    "TOST",
    "CAVA",
    "BROS",
    "AXON",
    "FICO",
    "TTWO",
    "EA",
    "LULU",
    "DECK",
    "ONON",
    "CROX",
    "DASH",
    "LYFT",
    "AFRM",
    "UPST",
    "XYZ",
    "VST",
    "CEG",
    "FSLR",
    "ENPH",
    "ANET",
    "CRDO",
    "PLTR",
    "SNOW",
    "NET",
    "DKNG",
    "COIN",
    "HOOD",
    "SOFI",
]


def _dedupe_tickers(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        tk = str(raw or "").strip().upper()
        if tk and tk not in seen:
            seen.add(tk)
            out.append(tk)
    return out


ALL_ETFS: list[str] = _dedupe_tickers(INDEX_ETFS + SECTOR_ETFS + THEMATIC_ETFS)

# Monitor-pool coverage — stocks, indices, sector/thematic ETFs (research tier)
OPPORTUNITY_COVERAGE_UNIVERSE: list[str] = _dedupe_tickers(
    RS_UNIVERSE + CORE_WATCHLIST + ALL_ETFS + LIQUID_MID_LARGE
)

_ETF_SET = frozenset(ALL_ETFS)
_INDEX_SET = frozenset(INDEX_ETFS)


def is_index_or_etf(ticker: str) -> bool:
    """True for broad indices and sector/thematic ETFs."""
    return str(ticker or "").strip().upper() in _ETF_SET


def is_broad_index(ticker: str) -> bool:
    """True for SPY/QQQ/IWM-style benchmark ETFs."""
    return str(ticker or "").strip().upper() in _INDEX_SET


def asset_class_for(ticker: str) -> str:
    """Asset class label for scoring and UI."""
    tk = str(ticker or "").strip().upper()
    if tk in _INDEX_SET:
        return "index"
    if tk in _ETF_SET:
        return "etf"
    return "equity"


def etf_theme_for(ticker: str) -> str:
    """Human theme for ETF/index cards."""
    tk = str(ticker or "").strip().upper()
    themes = {
        "SPY": "Broad Market",
        "QQQ": "Nasdaq 100",
        "IWM": "Russell 2000",
        "DIA": "Dow 30",
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLC": "Communication",
        "XLY": "Consumer Disc.",
        "XLP": "Consumer Staples",
        "XLRE": "Real Estate",
        "XLU": "Utilities",
        "XLB": "Materials",
        "SOXX": "Semiconductors",
        "SMH": "Semiconductors",
        "IGV": "Software",
        "ARKK": "Innovation",
        "KWEB": "China Internet",
        "GLD": "Gold",
        "VNQ": "REITs",
        "GDX": "Gold Miners",
        "XBI": "Biotech",
    }
    return themes.get(tk, "ETF")


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
    "PLTR",
    "CRWD",
    "COIN",
    "HOOD",
    "SMCI",
    "ARM",
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
]

# Sector tags for risk / correlation (extend engines.correlation_risk)
SECTOR_BY_TICKER: dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Technology",
    "GOOG": "Technology",
    "AMZN": "Consumer Discretionary",
    "META": "Technology",
    "TSLA": "Consumer Discretionary",
    "AMD": "Technology",
    "AVGO": "Technology",
    "INTC": "Technology",
    "QCOM": "Technology",
    "MU": "Technology",
    "AMAT": "Technology",
    "LRCX": "Technology",
    "CRM": "Technology",
    "ORCL": "Technology",
    "ADBE": "Technology",
    "NOW": "Technology",
    "PANW": "Technology",
    "CRWD": "Technology",
    "SNOW": "Technology",
    "DDOG": "Technology",
    "PLTR": "Technology",
    "NFLX": "Communication Services",
    "DIS": "Communication Services",
    "UBER": "Consumer Discretionary",
    "COIN": "Financials",
    "HOOD": "Financials",
    "PYPL": "Financials",
    "SOFI": "Financials",
    "JPM": "Financials",
    "BAC": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "GS": "Financials",
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "LLY": "Healthcare",
    "UNH": "Healthcare",
    "JNJ": "Healthcare",
    "PFE": "Healthcare",
    "ABBV": "Healthcare",
    "MRK": "Healthcare",
    "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    "HD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "BA": "Industrials",
    "CAT": "Industrials",
    "GE": "Industrials",
    "RTX": "Industrials",
    "LMT": "Industrials",
    "SMCI": "Technology",
    "ARM": "Technology",
    "CRDO": "Technology",
    "MSTR": "Technology",
    "IONQ": "Technology",
    "SPY": "Index",
    "QQQ": "Index",
    "IWM": "Index",
    "DIA": "Index",
    "RSP": "Index",
    "MDY": "Index",
    "VTI": "Index",
    "VOO": "Index",
    "IVV": "Index",
    "XLK": "ETF",
    "XLF": "ETF",
    "XLV": "ETF",
    "XLE": "ETF",
    "XLI": "ETF",
    "XLC": "ETF",
    "XLY": "ETF",
    "XLP": "ETF",
    "XLRE": "ETF",
    "XLU": "ETF",
    "XLB": "ETF",
    "SOXX": "ETF",
    "SMH": "ETF",
    "IGV": "ETF",
    "ARKK": "ETF",
    "KWEB": "ETF",
    "FXI": "ETF",
    "EEM": "ETF",
    "GLD": "ETF",
    "VNQ": "ETF",
    "GDX": "ETF",
    "XBI": "ETF",
    "ITA": "ETF",
    "TLT": "ETF",
    "BITO": "ETF",
    "WFC": "Financials",
    "MS": "Financials",
    "AXP": "Financials",
    "SCHW": "Financials",
    "BLK": "Financials",
    "XYZ": "Financials",
    "GILD": "Healthcare",
    "REGN": "Healthcare",
    "ISRG": "Healthcare",
    "VRTX": "Healthcare",
    "TXN": "Technology",
    "KLAC": "Technology",
    "ADI": "Technology",
    "MRVL": "Technology",
    "ON": "Technology",
    "DELL": "Technology",
    "INTU": "Technology",
    "ZS": "Technology",
    "NET": "Technology",
    "SHOP": "Technology",
    "ABNB": "Consumer Discretionary",
    "CMCSA": "Communication Services",
    "SBUX": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "LOW": "Consumer Discretionary",
    "DE": "Industrials",
    "HON": "Industrials",
    "RBLX": "Communication Services",
}


def rs_sector_for(ticker: str) -> str:
    """Sector label for RS universe cards."""
    full = SECTOR_BY_TICKER.get(ticker.upper(), "Other")
    return RS_SECTOR_SHORT.get(full, full[:12] if full != "Other" else "Other")


def universe_summary() -> dict:
    """Metadata for /api/health and ops."""
    return {
        "core_watchlist_count": len(CORE_WATCHLIST),
        "rs_universe_count": len(RS_UNIVERSE),
        "index_etf_count": len(ALL_ETFS),
        "coverage_universe_count": len(OPPORTUNITY_COVERAGE_UNIVERSE),
        "popular_count": len(POPULAR_TICKERS),
        "demo_positions": len(DEMO_PORTFOLIO_POSITIONS),
        "sectors_covered": len(set(SECTOR_BY_TICKER.values())),
    }
