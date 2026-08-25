"""Tests for session-aware data freshness tiers."""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.services.data_freshness_service import (
    _bar_session_date,
    _last_us_equity_session,
    _tier_from_bar,
)


def test_last_session_sunday_uses_friday():
    # 2026-05-24 is Sunday
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    assert _last_us_equity_session(now) == date(2026, 5, 22)


def test_friday_bar_on_sunday_is_fresh():
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    bar = date(2026, 5, 22)
    assert _tier_from_bar(bar, age_min=4000, in_hours=False, now=now) == "FRESH"


def test_monday_off_hours_friday_bar_fresh():
    now = datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc)  # Monday pre-open UTC
    bar = date(2026, 5, 22)
    assert _tier_from_bar(bar, age_min=4000, in_hours=False, now=now) == "FRESH"


def test_stale_when_bar_before_last_session():
    now = datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc)
    bar = date(2026, 5, 15)
    assert _tier_from_bar(bar, age_min=10000, in_hours=False, now=now) == "CRITICAL"
