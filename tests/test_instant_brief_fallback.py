"""Instant server must show brief stocks when :8001 is down."""

from __future__ import annotations

import json
import sys

import pytest

from _synthetic_brief_fixture import isolated_brief_dir  # noqa: F401

from _cc_instant import (
    _brief_fallback_ranked_rows,
    _ranked_payload_has_names,
    _stale_ranked_bytes,
    _stale_today_bytes,
)


@pytest.fixture
def instant_state(isolated_brief_dir, monkeypatch):  # noqa: F811
    # Patch the defining module, not root-launcher copies of its globals.
    impl = sys.modules[_stale_today_bytes.__module__]
    monkeypatch.setattr(impl, "_REPO_ROOT", isolated_brief_dir.parent)
    monkeypatch.setattr(impl, "_BRIEF_GLOB", isolated_brief_dir)
    monkeypatch.setattr(
        impl,
        "_RANKED_SNAPSHOT_PATH",
        isolated_brief_dir / "cache" / "playbook_ranked_snapshot.json",
    )
    monkeypatch.setenv("CC_LIVE_DATA_ONLY", "0")
    return isolated_brief_dir


@pytest.fixture
def synthetic_brief(instant_state):
    """SYNTHETIC temporary brief, read through the real BriefDataService."""
    brief = {
        "date": "2026-01-01",
        "synthetic": True,
        "watch": [
            {
                "ticker": "TEST",
                "conviction": "WATCH",
                "rs_score": 82,
                "entry": 100,
                "stop": 95,
                "target_2r": 110,
            }
        ],
    }
    (instant_state / "brief-2026-01-01.json").write_text(
        json.dumps(brief), encoding="utf-8"
    )
    return brief


def test_brief_fallback_ranked_has_tickers(synthetic_brief):
    rows = _brief_fallback_ranked_rows(limit=10)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "TEST"
    assert rows[0].get("action") == "WATCH"
    assert rows[0]["execution_ready"] is False


def test_stale_ranked_bytes_not_empty(synthetic_brief):
    body = _stale_ranked_bytes("backend importing — test")
    payload = json.loads(body)
    assert _ranked_payload_has_names(payload)
    assert payload["count"] == 1
    assert payload["opportunities"][0]["ticker"] == "TEST"
    assert payload["opportunities"][0]["execution_ready"] is False
    assert payload["trust"]["stale"] is True


def test_stale_today_bytes_has_top5(synthetic_brief):
    payload = json.loads(_stale_today_bytes("backend importing — test"))
    assert len(payload["top_5"]) == 1
    assert payload["top_5"][0]["ticker"] == "TEST"
    assert payload["top_5"][0]["execution_ready"] is False
    assert payload["market_regime"]["should_trade"] is False
    assert payload["todays_decision"]["can_deploy_today"] is False


def test_missing_brief_does_not_invent_names(instant_state):
    assert _brief_fallback_ranked_rows(limit=10) == []
    ranked = json.loads(_stale_ranked_bytes("SYNTHETIC empty data test"))
    today = json.loads(_stale_today_bytes("SYNTHETIC empty data test"))
    assert not _ranked_payload_has_names(ranked)
    assert ranked["count"] == 0
    assert today["top_5"] == []
    assert today["market_regime"]["should_trade"] is False


def test_live_only_policy_does_not_surface_synthetic_brief(
    synthetic_brief, monkeypatch
):
    monkeypatch.setenv("CC_LIVE_DATA_ONLY", "1")
    ranked = json.loads(_stale_ranked_bytes("SYNTHETIC policy test"))
    today = json.loads(_stale_today_bytes("SYNTHETIC policy test"))
    assert not _ranked_payload_has_names(ranked)
    assert today["top_5"] == []
