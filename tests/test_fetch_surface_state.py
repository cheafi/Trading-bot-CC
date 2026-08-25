"""Fetch surface degraded states — shared badge/copy contract."""

from __future__ import annotations

from src.services.fetch_surface_state import (
    STATE_FAILED_FETCH,
    STATE_MOCK_ONLY,
    STATE_OK,
    STATE_PROBE_ONLY,
    STATE_RUNTIME_UNKNOWN,
    STATE_STALE,
    describe_fetch_state,
    fetch_state_from_http,
    normalize_fetch_state,
)


def test_normalize_fetch_state_priority():
    assert normalize_fetch_state(loading=True, error="x") == "loading"
    assert normalize_fetch_state(error="boom") == "failed_fetch"
    assert normalize_fetch_state(stale=True) == "stale"
    assert normalize_fetch_state() == STATE_OK


def test_describe_fetch_state_includes_badge():
    d = describe_fetch_state(STATE_STALE)
    assert d["badge"] == "STALE"
    assert d["title"]
    assert d["explanation"]
    assert d["next_action"]


def test_fetch_state_from_http_failed():
    d = fetch_state_from_http(503, error_message="upstream")
    assert d["state"] == STATE_FAILED_FETCH
    assert "503" in d["explanation"] or "upstream" in d["explanation"]


def test_mock_only_state_copy():
    d = describe_fetch_state(STATE_MOCK_ONLY)
    assert "mock" in d["explanation"].lower() or "synthetic" in d["explanation"].lower()


def test_probe_only_and_runtime_unknown_states():
    assert normalize_fetch_state(probe_only=True) == STATE_PROBE_ONLY
    assert normalize_fetch_state(runtime_unknown=True) == STATE_RUNTIME_UNKNOWN
    assert describe_fetch_state(STATE_PROBE_ONLY)["badge"] == "PROBE ONLY"
    assert describe_fetch_state(STATE_RUNTIME_UNKNOWN)["badge"] == "RUNTIME UNKNOWN"
