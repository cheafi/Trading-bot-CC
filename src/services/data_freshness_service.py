"""
Data Freshness Watchdog
========================
Reports last-bar age for critical market-data streams.

For each watched ticker (default SPY, VIX proxy, QQQ), fetch the latest
bar timestamp and compute age in minutes vs UTC now.

Tiers:
  FRESH      < 30 min during regular hours; < 24h overnight/weekend
  STALE      30–120 min during hours
  CRITICAL   > 120 min during hours
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_WATCH = ["SPY", "QQQ", "^VIX"]

# Thresholds in minutes (regular session only)
STALE_MIN = 30
CRITICAL_MIN = 120
# Legacy off-hours minute cap (kept for thresholds payload)
WEEKEND_GRACE_MIN = 60 * 60


def _last_us_equity_session(now: datetime) -> date:
    """Most recent *completed* US equity session (not today's incomplete bar)."""
    cur = now.date()
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    # Off-hours: today's daily bar is not final yet — use prior session
    if not _is_market_hours_utc(now) and cur == now.date():
        cur -= timedelta(days=1)
        while cur.weekday() >= 5:
            cur -= timedelta(days=1)
    return cur


def _bar_session_date(ts: datetime) -> date:
    """Calendar date of the bar in US/Eastern when possible."""
    try:
        from zoneinfo import ZoneInfo

        return ts.astimezone(ZoneInfo("America/New_York")).date()
    except Exception:
        return ts.date()


def _is_market_hours_utc(now: datetime) -> bool:
    """Best-effort US equities cash session check (UTC)."""
    if now.weekday() >= 5:
        return False
    # NYSE: 13:30–20:00 UTC (no DST handling — close-enough for a watchdog)
    minute_of_day = now.hour * 60 + now.minute
    return 13 * 60 + 30 <= minute_of_day <= 20 * 60


async def _last_bar_age_minutes(market_data, ticker: str) -> Dict[str, Any]:
    try:
        hist = await market_data.get_history(ticker, period="5d", interval="1d")
    except Exception as exc:
        return {"ticker": ticker, "ok": False, "error": str(exc), "age_min": None}
    if hist is None or len(hist) == 0:
        return {"ticker": ticker, "ok": False, "error": "no data", "age_min": None}
    last_idx = hist.index[-1]
    try:
        ts = (
            last_idx.to_pydatetime()
            if hasattr(last_idx, "to_pydatetime")
            else datetime.fromisoformat(str(last_idx))
        )
    except Exception:
        return {"ticker": ticker, "ok": False, "error": "bad ts", "age_min": None}
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_min = (now - ts).total_seconds() / 60.0
    return {
        "ticker": ticker,
        "ok": True,
        "last_bar_utc": ts.isoformat(),
        "last_bar_date": _bar_session_date(ts).isoformat(),
        "age_min": round(age_min, 1),
        "bars": int(len(hist)),
    }


def _tier_from_bar(
    bar_date: date, age_min: float, in_hours: bool, now: datetime
) -> str:
    """Grade freshness vs last expected US equity session (not raw clock age)."""
    last_session = _last_us_equity_session(now)
    if bar_date >= last_session:
        return "FRESH"
    gap_days = (last_session - bar_date).days
    if in_hours:
        if age_min >= CRITICAL_MIN:
            return "CRITICAL"
        if age_min >= STALE_MIN:
            return "STALE"
        return "FRESH"
    # Off-hours / weekend: only CRITICAL if data is older than last session by 2+ days
    if gap_days >= 3:
        return "CRITICAL"
    if gap_days >= 1:
        return "STALE"
    return "FRESH"


async def freshness_report(market_data, tickers: List[str] = None) -> Dict[str, Any]:
    tickers = tickers or DEFAULT_WATCH
    now = datetime.now(timezone.utc)
    in_hours = _is_market_hours_utc(now)

    rows = await asyncio.gather(
        *(_last_bar_age_minutes(market_data, t) for t in tickers),
        return_exceptions=True,
    )
    safe_rows: List[Dict[str, Any]] = []
    for r in rows:
        if isinstance(r, Exception):
            safe_rows.append(
                {"ticker": "?", "ok": False, "error": str(r), "age_min": None}
            )
        else:
            safe_rows.append(r)

    # Classify vs last US equity session (avoids false CRITICAL on weekends)
    last_session = _last_us_equity_session(now)
    tier_rank = {"FRESH": 0, "STALE": 1, "UNKNOWN": 1, "CRITICAL": 2}
    worst = "FRESH"
    for r in safe_rows:
        if not r.get("ok") or r.get("age_min") is None:
            r["tier"] = "UNKNOWN"
            if tier_rank.get(worst, 0) < tier_rank["STALE"]:
                worst = "STALE"
            continue
        bar_date = date.fromisoformat(r["last_bar_date"])
        tier = _tier_from_bar(bar_date, r["age_min"], in_hours, now)
        r["tier"] = tier
        r["last_session_expected"] = last_session.isoformat()
        if tier_rank.get(tier, 0) > tier_rank.get(worst, 0):
            worst = tier

    return {
        "as_of": now.isoformat(),
        "market_hours_utc": in_hours,
        "last_session_expected": last_session.isoformat(),
        "worst_tier": worst,
        "streams": safe_rows,
        "thresholds": {
            "stale_min": STALE_MIN,
            "critical_min": CRITICAL_MIN,
            "weekend_grace_min": WEEKEND_GRACE_MIN,
        },
    }
