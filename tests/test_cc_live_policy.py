"""CC_LIVE_DATA_ONLY policy — refuse brief/stale fallbacks."""

from __future__ import annotations

import os

from src.services.cc_live_policy import (
    build_live_unavailable_ranked,
    build_live_unavailable_today_payload,
    cc_live_data_only_enabled,
)
from src.services.today_insights import merge_brief_board_fallback


def test_live_only_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CC_LIVE_DATA_ONLY", raising=False)
    assert cc_live_data_only_enabled() is False


def test_live_only_enabled(monkeypatch):
    monkeypatch.setenv("CC_LIVE_DATA_ONLY", "1")
    assert cc_live_data_only_enabled() is True


def test_merge_brief_skipped_when_live_only(monkeypatch):
    monkeypatch.setenv("CC_LIVE_DATA_ONLY", "true")
    top5, near_miss, used = merge_brief_board_fallback(
        [],
        [],
        scanner_degraded=True,
    )
    assert top5 == []
    assert near_miss == []
    assert used is False


def test_live_unavailable_today_has_no_deploy_authority():
    payload = build_live_unavailable_today_payload(reason="scanner empty")
    assert payload["top_5"] == []
    assert payload["trust"]["source"] == "live-unavailable"
    assert payload["decision_authority"]["deploy_authority"] is False
    assert payload["live_only_blocked"] is True


def test_live_unavailable_ranked_skips_brief_source():
    payload = build_live_unavailable_ranked(reason="pipeline timeout")
    assert payload["source"] == "live-unavailable"
    assert payload["board_mode"] == "live_unavailable"
    assert payload["opportunities"] == []
