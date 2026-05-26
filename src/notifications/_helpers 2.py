"""
CC Discord Bot — Shared Helpers
================================
Utility functions shared across cogs: fetch stock data,
audit logging, channel helpers, formatting.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def utcnow_iso() -> str:
    """UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def format_price(price: float) -> str:
    """Format price with appropriate decimal places."""
    if price >= 1000:
        return f"${price:,.0f}"
    if price >= 1:
        return f"${price:,.2f}"
    return f"${price:,.4f}"


def format_change(change_pct: float) -> str:
    """Format change percentage with emoji."""
    arrow = "\U0001f7e2" if change_pct >= 0 else "\U0001f534"
    sign = "+" if change_pct >= 0 else ""
    return f"{arrow} {sign}{change_pct:.2f}%"


def format_volume(volume: float) -> str:
    """Human-readable volume (1.2M, 500K, etc)."""
    if volume >= 1e9:
        return f"{volume / 1e9:.1f}B"
    if volume >= 1e6:
        return f"{volume / 1e6:.1f}M"
    if volume >= 1e3:
        return f"{volume / 1e3:.0f}K"
    return str(int(volume))


def format_market_cap(cap: float) -> str:
    """Human-readable market cap."""
    if cap >= 1e12:
        return f"${cap / 1e12:.1f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.1f}B"
    if cap >= 1e6:
        return f"${cap / 1e6:.0f}M"
    return f"${cap:,.0f}"


def truncate(text: str, max_len: int = 1024) -> str:
    """Truncate text for Discord field limits."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def regime_emoji(regime: str) -> str:
    """Map regime label to emoji."""
    mapping = {
        "bull": "\U0001f7e2",
        "bear": "\U0001f534",
        "choppy": "\U0001f7e1",
        "volatile": "\U0001f7e3",
        "recovery": "\U0001f535",
    }
    return mapping.get(regime.lower(), "\u26aa")


def confidence_bar(confidence: float, width: int = 10) -> str:
    """Visual confidence bar: ████░░░░░░ 60%."""
    filled = int(confidence / 100 * width)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty} {confidence:.0f}%"


async def fetch_stock_data(
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch current stock data via yfinance.
    Returns dict with price, change, volume, etc. or None.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        if not info or "regularMarketPrice" not in info:
            return None
        price = info.get("regularMarketPrice", 0)
        prev = info.get("regularMarketPreviousClose", price)
        change = (
            (price - prev) / prev * 100 if prev else 0
        )
        return {
            "ticker": ticker.upper(),
            "price": price,
            "change_pct": round(change, 2),
            "volume": info.get("regularMarketVolume", 0),
            "market_cap": info.get("marketCap", 0),
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", ticker, e)
        return None
