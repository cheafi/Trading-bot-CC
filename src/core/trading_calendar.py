"""
src/core/trading_calendar.py — Deterministic NYSE/NASDAQ trading calendar
=========================================================================

Single source of truth for *trading-day* arithmetic. Replaces the
``calendar_days * 5 / 7`` approximation previously used by
``src.algo.position_manager.Position.days_held``, which systematically
mis-stated holding periods (e.g. 3 calendar days → 2 "trading days"
regardless of whether any session actually occurred).

Design constraints
------------------
* **Zero new dependencies.** US equity holidays are derived from the
  published NYSE rules rather than a vendored data file, so the module
  stays correct for future years without maintenance.
* **Deterministic & testable.** No network, no clock reads except where
  an explicit default is required.
* **Timezone-safe.** All inputs are normalised to US/Eastern *dates*
  before counting, so a UTC timestamp just after midnight does not leak
  into the next session.

Observed holidays (NYSE):
    New Year's Day, MLK Day, Washington's Birthday, Good Friday,
    Memorial Day, Juneteenth (from 2022), Independence Day, Labor Day,
    Thanksgiving, Christmas.

Weekend-observance rule: a holiday falling on Saturday is observed on the
preceding Friday; on Sunday, the following Monday. Juneteenth was first
observed by the NYSE in 2022.

Not modelled: ad-hoc closures (e.g. national days of mourning, Hurricane
Sandy). These are rare and cannot be derived from rules; callers needing
exact historical fidelity should supply ``extra_holidays``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Iterable
from zoneinfo import ZoneInfo

__all__ = [
    "EXCHANGE_TZ",
    "is_trading_day",
    "nyse_holidays",
    "to_exchange_date",
    "trading_days_between",
]

EXCHANGE_TZ = ZoneInfo("America/New_York")

# NYSE began observing Juneteenth National Independence Day in 2022.
_JUNETEENTH_FIRST_YEAR = 2022


# ── Date helpers ────────────────────────────────────────────────────────


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th ``weekday`` (Mon=0) of ``month``. ``n`` is 1-based."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Last ``weekday`` (Mon=0) of ``month``."""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month, day = divmod(h + ll - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _observed(day: date) -> date:
    """Apply the NYSE weekend-observance rule."""
    if day.weekday() == 5:  # Saturday → preceding Friday
        return day - timedelta(days=1)
    if day.weekday() == 6:  # Sunday → following Monday
        return day + timedelta(days=1)
    return day


@lru_cache(maxsize=256)
def nyse_holidays(year: int) -> frozenset[date]:
    """Full-day NYSE market closures for ``year`` (weekends excluded)."""
    days: set[date] = {
        _observed(date(year, 1, 1)),  # New Year's Day
        _nth_weekday(year, 1, 0, 3),  # MLK Day — 3rd Monday Jan
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday — 3rd Monday Feb
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day — last Monday May
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day — 1st Monday Sep
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving — 4th Thursday Nov
        _observed(date(year, 12, 25)),  # Christmas Day
    }
    if year >= _JUNETEENTH_FIRST_YEAR:
        days.add(_observed(date(year, 6, 19)))

    # A Saturday holiday observed on the preceding Friday can roll into the
    # previous calendar year (1 Jan on a Saturday → 31 Dec).
    return frozenset(d for d in days if d.weekday() < 5)


def to_exchange_date(value: datetime | date) -> date:
    """Normalise a timestamp to the US/Eastern calendar date of its session.

    Naive datetimes are assumed to already be exchange-local (the historical
    convention in this codebase); aware datetimes are converted.
    """
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(EXCHANGE_TZ)
        return value.date()
    return value


def is_trading_day(
    value: datetime | date,
    *,
    extra_holidays: Iterable[date] | None = None,
) -> bool:
    """True when the US equity market holds a regular session on ``value``."""
    day = to_exchange_date(value)
    if day.weekday() >= 5:
        return False
    if day in nyse_holidays(day.year):
        return False
    if extra_holidays and day in set(extra_holidays):
        return False
    return True


def trading_days_between(
    start: datetime | date,
    end: datetime | date,
    *,
    extra_holidays: Iterable[date] | None = None,
) -> int:
    """Completed exchange sessions in the half-open range [start, end).

    Semantics match the previous ``days_held`` contract: entering and exiting
    on the same session yields ``0``. Reversed ranges yield ``0`` rather than a
    negative holding period, which would corrupt downstream averages.
    """
    start_d = to_exchange_date(start)
    end_d = to_exchange_date(end)
    if end_d <= start_d:
        return 0

    extra = set(extra_holidays or ())
    # Count whole weeks analytically, then walk the remainder. Bounded by
    # 6 iterations plus one holiday scan per year, so this stays O(years).
    count = 0
    cursor = start_d
    while cursor < end_d:
        # Fast-forward in 7-day blocks: each block contributes exactly 5
        # weekdays regardless of alignment.
        if (end_d - cursor).days >= 7:
            weeks = (end_d - cursor).days // 7
            count += 5 * weeks
            cursor += timedelta(days=7 * weeks)
            continue
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)

    # Subtract holidays inside the range (weekday-only by construction).
    for year in range(start_d.year, end_d.year + 1):
        for holiday in nyse_holidays(year):
            if start_d <= holiday < end_d:
                count -= 1
    for holiday in extra:
        if start_d <= holiday < end_d and holiday.weekday() < 5:
            count -= 1

    return max(count, 0)
