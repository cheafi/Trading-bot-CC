"""Tests for platform error log ring buffer and changelog loader."""

from __future__ import annotations

from src.services.platform_error_log import (
    clear_error_log_for_tests,
    get_error_log,
    load_changelog,
    log_platform_error,
)


def test_error_log_append_and_filter():
    clear_error_log_for_tests()
    log_platform_error(
        severity="critical",
        component="api",
        message="HTTP 503",
        detail="Service unavailable",
        suggested_action="Retry",
    )
    log_platform_error(
        severity="info",
        component="engine",
        message="Engine idle",
        detail="No cycles yet",
    )
    all_rows = get_error_log(limit=10)
    assert all_rows["count"] == 2
    crit = get_error_log(severity="critical", limit=10)
    assert crit["count"] == 1
    assert crit["entries"][0]["component"] == "api"


def test_error_log_dedupe():
    clear_error_log_for_tests()
    log_platform_error(
        severity="warning",
        component="broker",
        message="Gateway down",
        detail="Cannot reach IB Gateway",
        dedupe_key="broker:down",
    )
    log_platform_error(
        severity="warning",
        component="broker",
        message="Gateway down",
        detail="Cannot reach IB Gateway",
        dedupe_key="broker:down",
    )
    rows = get_error_log(limit=10)
    assert rows["count"] == 1


def test_load_changelog_has_entries():
    data = load_changelog()
    assert "version" in data
    assert isinstance(data.get("entries"), list)
    assert len(data["entries"]) >= 1
    assert "title" in data["entries"][0]
