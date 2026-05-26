"""
Earnings Calendar — Blackout Enforcement.

Fetches real earnings dates from yfinance and enforces:
1. Blackout period: no new entries ≤3 days before earnings
2. Earnings risk flag in confidence model
3. Calendar data for expert council

Cached per ticker to avoid repeated API calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Cache: ticker → {date, days_to, ...}
_EARNINGS_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 3600 * 6  # 6 hours


def get_earnings_info(
    ticker: str,
) -> Dict[str, Any]:
    """
    Get earnings calendar info for a ticker.

    Returns:
        {
            "next_earnings_date": "2026-05-15" or None,
            "days_to_earnings": 19 or None,
            "in_blackout": False,
            "earnings_risk": "low" / "medium" / "high",
            "source": "yfinance" or "unavailable",
        }
    """
    import time

    now = time.time()
    cached = _EARNINGS_CACHE.get(ticker)
    if cached and now - cached.get("_ts", 0) < _CACHE_TTL:
        return {k: v for k, v in cached.items() if not k.startswith("_")}

    result = _fetch_earnings(ticker)
    result["_ts"] = now
    _EARNINGS_CACHE[ticker] = result
    return {k: v for k, v in result.items() if not k.startswith("_")}


def _fetch_earnings(ticker: str) -> Dict[str, Any]:
    """Fetch from yfinance."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).calendar
        if info is None or not isinstance(info, dict):
            return _no_data()

        # yfinance returns calendar as dict
        # with 'Earnings Date' key
        earn_dates = info.get("Earnings Date")
        if not earn_dates:
            return _no_data()

        # Can be list of dates
        if isinstance(earn_dates, list):
            earn_date = earn_dates[0]
        else:
            earn_date = earn_dates

        # Parse date
        if hasattr(earn_date, "date"):
            ed = earn_date.date()
        elif isinstance(earn_date, str):
            ed = datetime.strptime(earn_date, "%Y-%m-%d").date()
        else:
            return _no_data()

        today = datetime.now(timezone.utc).date()
        days_to = (ed - today).days

        # Classify risk
        if days_to <= 0:
            risk = "post_earnings"
        elif days_to <= 3:
            risk = "high"
        elif days_to <= 7:
            risk = "medium"
        else:
            risk = "low"

        return {
            "next_earnings_date": str(ed),
            "days_to_earnings": max(0, days_to),
            "in_blackout": 0 < days_to <= 3,
            "earnings_risk": risk,
            "source": "yfinance",
        }
    except Exception as e:
        logger.debug("Earnings fetch failed for %s: %s", ticker, e)
        return _no_data()


def _no_data() -> Dict[str, Any]:
    return {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "in_blackout": False,
        "earnings_risk": "unknown",
        "source": "unavailable",
    }


def is_in_blackout(ticker: str) -> bool:
    """Quick check: is ticker in earnings blackout?"""
    info = get_earnings_info(ticker)
    return info.get("in_blackout", False)


def get_days_to_earnings(
    ticker: str,
) -> Optional[int]:
    """Get days until next earnings, or None."""
    info = get_earnings_info(ticker)
    return info.get("days_to_earnings")
