"""
US Market Calendar Service.

Extracted from src/api/main.py. Computes NYSE/NASDAQ trading holidays
and session status for any date.

Holiday rules:
  - New Year's Day (Jan 1, observed)
  - MLK Jr Day (3rd Monday in Jan)
  - Presidents Day (3rd Monday in Feb)
  - Good Friday (2 days before Easter Sunday)
  - Memorial Day (last Monday in May)
  - Juneteenth (Jun 19, observed)
  - Independence Day (Jul 4, observed)
  - Labor Day (1st Monday in Sep)
  - Thanksgiving (4th Thursday in Nov)
  - Christmas (Dec 25, observed)
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# HOLIDAY COMPUTATION
# ═══════════════════════════════════════════════════════════════════

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> int:
    """Return day-of-month for the nth occurrence of weekday in month.
    weekday: 0=Mon … 6=Sun. n: 1-based.
    """
    first = date(year, month, 1)
    days_ahead = weekday - first.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return 1 + days_ahead + (n - 1) * 7


def _last_weekday(year: int, month: int, weekday: int) -> int:
    """Return day-of-month for the last occurrence of weekday in month."""
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    days_behind = last.weekday() - weekday
    if days_behind < 0:
        days_behind += 7
    return last_day - days_behind


def _easter_sunday(year: int) -> Tuple[int, int, int]:
    """Anonymous Gregorian algorithm for Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return (year, month, day)


def _observed(d: date) -> date:
    """Move Saturday holidays to Friday, Sunday holidays to Monday."""
    if d.weekday() == 5:   # Saturday → Friday
        return d - timedelta(days=1)
    if d.weekday() == 6:   # Sunday → Monday
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=8)
def us_market_holidays(year: int) -> Set[date]:
    """Compute US market holidays (NYSE/NASDAQ) for a given year.

    Result is cached per year — safe to call on every request.
    """
    holidays: Set[date] = set()

    # New Year's Day
    holidays.add(_observed(date(year, 1, 1)))

    # MLK Jr Day — 3rd Monday in January
    holidays.add(date(year, 1, _nth_weekday(year, 1, 0, 3)))

    # Presidents Day — 3rd Monday in February
    holidays.add(date(year, 2, _nth_weekday(year, 2, 0, 3)))

    # Good Friday — 2 days before Easter
    ey, em, ed = _easter_sunday(year)
    good_friday = date(ey, em, ed) - timedelta(days=2)
    holidays.add(good_friday)

    # Memorial Day — last Monday in May
    holidays.add(date(year, 5, _last_weekday(year, 5, 0)))

    # Juneteenth (since 2022)
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))

    # Independence Day
    holidays.add(_observed(date(year, 7, 4)))

    # Labor Day — 1st Monday in September
    holidays.add(date(year, 9, _nth_weekday(year, 9, 0, 1)))

    # Thanksgiving — 4th Thursday in November
    holidays.add(date(year, 11, _nth_weekday(year, 11, 3, 4)))

    # Christmas
    holidays.add(_observed(date(year, 12, 25)))

    return holidays


def is_us_market_holiday(d: Optional[date] = None) -> bool:
    """Return True if d (default: today) is a NYSE/NASDAQ holiday."""
    if d is None:
        d = date.today()
    return d in us_market_holidays(d.year)


def is_us_market_open(d: Optional[date] = None) -> bool:
    """Return True if US market trades on d (weekday and not holiday)."""
    if d is None:
        d = date.today()
    if d.weekday() >= 5:            # Saturday=5, Sunday=6
        return False
    return not is_us_market_holiday(d)


def next_trading_day(d: Optional[date] = None) -> date:
    """Return the next US market trading day after d (default: today)."""
    if d is None:
        d = date.today()
    candidate = d + timedelta(days=1)
    while not is_us_market_open(candidate):
        candidate += timedelta(days=1)
    return candidate


def prev_trading_day(d: Optional[date] = None) -> date:
    """Return the previous US market trading day before d (default: today)."""
    if d is None:
        d = date.today()
    candidate = d - timedelta(days=1)
    while not is_us_market_open(candidate):
        candidate -= timedelta(days=1)
    return candidate


def trading_days_between(start: date, end: date) -> int:
    """Count trading days between start (inclusive) and end (inclusive)."""
    count = 0
    d = start
    while d <= end:
        if is_us_market_open(d):
            count += 1
        d += timedelta(days=1)
    return count
