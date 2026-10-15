"""Exchange session helpers — US regular hours with America/New_York (DST-safe)."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Set, Tuple
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# Non-US sessions remain UTC-minute schedules (engine legacy).
_STATIC_SESSIONS: Dict[str, Dict[str, Any]] = {
    "hk_regular": {"open": (1, 30), "close": (8, 0), "markets": ["hk"]},
    "jp_regular": {"open": (0, 0), "close": (6, 0), "markets": ["jp"]},
    "crypto_247": {"open": (0, 0), "close": (24, 0), "markets": ["crypto"]},
}


def _minutes(h: int, m: int) -> int:
    return h * 60 + m


def us_session_utc_windows(now_utc: datetime | None = None) -> Dict[str, Tuple[int, int]]:
    """Return US pre/regular/afterhours as UTC minute-of-day ranges for ``now``'s date."""
    now = now_utc or datetime.now(timezone.utc)
    et = now.astimezone(_ET)
    day = et.date()

    def _utc_minutes(local_h: int, local_m: int) -> int:
        dt_et = datetime.combine(day, time(local_h, local_m), tzinfo=_ET)
        dt_utc = dt_et.astimezone(timezone.utc)
        return dt_utc.hour * 60 + dt_utc.minute

    pre_open = _utc_minutes(4, 0)
    reg_open = _utc_minutes(9, 30)
    reg_close = _utc_minutes(16, 0)
    after_close = _utc_minutes(20, 0)
    return {
        "us_premarket": (pre_open, reg_open),
        "us_regular": (reg_open, reg_close),
        "us_afterhours": (reg_close, after_close),
    }


def active_markets_at(now_utc: datetime | None = None) -> List[str]:
    """Markets open at ``now_utc`` (US hours DST-aware)."""
    now = now_utc or datetime.now(timezone.utc)
    current_minutes = now.hour * 60 + now.minute
    active: Set[str] = set()

    us_windows = us_session_utc_windows(now)
    for _name, (open_m, close_m) in us_windows.items():
        if open_m <= close_m:
            in_session = open_m <= current_minutes < close_m
        else:
            in_session = current_minutes >= open_m or current_minutes < close_m
        if in_session:
            active.add("us")

    for session in _STATIC_SESSIONS.values():
        open_h, open_m = session["open"]
        close_h, close_m = session["close"]
        open_minutes = _minutes(open_h, open_m)
        close_minutes = _minutes(close_h, close_m)
        if close_minutes >= 24 * 60:
            close_minutes = 24 * 60 - 1
        if open_minutes <= current_minutes < close_minutes:
            active.update(session["markets"])

    return sorted(active)
