"""
CC Discord Bot — Constants
===========================
Shared constants, colors, roles, and server layout definitions.
Extracted from discord_bot.py to reduce monolith size.
"""
from __future__ import annotations

# ── Brand Colors ──────────────────────────────────────────────
COLOR_GREEN = 0x00FF88
COLOR_RED = 0xFF4444
COLOR_BLUE = 0x5865F2
COLOR_GOLD = 0xFFD700
COLOR_ORANGE = 0xFF8C00
COLOR_PURPLE = 0x9B59B6
COLOR_CYAN = 0x00BCD4
COLOR_GRAY = 0x95A5A6
COLOR_WHITE = 0xFFFFFF

# ── Regime Colors ─────────────────────────────────────────────
REGIME_COLORS = {
    "bull": COLOR_GREEN,
    "bear": COLOR_RED,
    "choppy": COLOR_ORANGE,
    "volatile": COLOR_PURPLE,
    "unknown": COLOR_GRAY,
}

# ── Action State Emoji ────────────────────────────────────────
ACTION_EMOJI = {
    "STRONG_BUY": "\U0001f7e2",
    "BUY_SMALL": "\U0001f535",
    "WATCH": "\U0001f7e1",
    "NO_TRADE": "\U0001f534",
    "REDUCE": "\U0001f7e0",
    "HEDGE": "\U0001f7e3",
}

# ── Server Layout ─────────────────────────────────────────────
SERVER_LAYOUT = {
    "\U0001f4ca Trading Signals": [
        "signals", "breakouts", "dip-buys",
        "swing-trades", "ai-picks",
    ],
    "\U0001f4bc Portfolio": [
        "portfolio", "positions", "pnl-tracker",
    ],
    "\U0001f6a8 Alerts": [
        "price-alerts", "vix-monitor",
        "news-feed", "earnings-watch",
    ],
    "\U0001f4c8 Market Intel": [
        "market-pulse", "sector-rotation",
        "macro-data", "crypto-watch",
    ],
    "\U0001f916 AI Lab": [
        "ai-analysis", "regime-tracker",
        "strategy-lab", "backtest-results",
    ],
    "\u2699\ufe0f Admin": [
        "bot-commands", "bot-logs", "announcements",
    ],
}

# ── Default Watchlist ─────────────────────────────────────────
DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "UNH",
    "XOM", "JNJ", "PG", "MA", "HD",
    "CVX", "MRK", "ABBV", "PEP", "COST",
    "AVGO", "TMO", "MCD", "WMT", "CSCO",
    "ACN", "ABT", "DHR", "NEE", "LIN",
]

# ── Sector ETFs ───────────────────────────────────────────────
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Disc.": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication": "XLC",
}

# ── Macro Indicators ──────────────────────────────────────────
MACRO_TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
    "10Y Treasury": "^TNX",
    "US Dollar": "DX-Y.NYB",
    "Gold": "GC=F",
    "Oil (WTI)": "CL=F",
    "Bitcoin": "BTC-USD",
}
