"""Tests for Playbook 3-layer board fallback."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.services.playbook_board_fallback import (
    BOARD_MODE_COMPRESSED,
    BOARD_MODE_EMERGENCY,
    BOARD_MODE_FULL,
    _COMPRESSED_LABEL,
    _LIVE_BOARD_LABEL,
    _SNAPSHOT_BOARD_LABEL,
    annotate_board_mode,
    build_compressed_fallback,
    build_emergency_response,
    load_playbook_snapshot,
    resolve_board_mode_label,
    save_playbook_snapshot,
)


SAMPLE_BRIEF = {
    "actionable": [
        {
            "ticker": "NVDA",
            "conviction": "WATCH",
            "rs_score": 88,
            "entry": 120,
            "stop": 110,
            "target_3r": 150,
            "vol_ratio": 1.3,
            "near_52w_high": True,
        }
    ],
    "watch": [
        {
            "ticker": "META",
            "conviction": "WATCH",
            "rs_score": 82,
            "entry": 500,
            "stop": 480,
            "target_3r": 560,
            "vol_ratio": 1.1,
        },
        {
            "ticker": "AMD",
            "conviction": "WATCH",
            "rs_score": 78,
            "entry": 160,
            "stop": 150,
            "target_3r": 190,
            "vol_ratio": 0.9,
        },
    ],
    "review": [
        {
            "ticker": "INTC",
            "conviction": "AVOID",
            "rs_score": 55,
            "leader": "LAGGARD",
            "entry": 40,
            "stop": 38,
            "target_3r": 46,
            "risk_reward": 1.5,
            "why_not": "Weak R:R",
        }
    ],
}


def test_build_compressed_fallback_from_brief():
    payload = build_compressed_fallback(30, brief=SAMPLE_BRIEF)
    assert payload["board_mode"] == BOARD_MODE_COMPRESSED
    assert len(payload["opportunities"]) >= 1
    assert len(payload["opportunities"]) <= 5
    assert len(payload["near_miss"]) <= 3
    assert payload["rejection_clusters"]
    assert payload["unlock_deploy"]["unlocked"] is False
    assert payload["board_message"]
    funnel = payload["filter_funnel"]
    assert funnel["universe_scanned"] >= funnel["watch_qualified_setups"]
    assert funnel["deploy_qualified_setups"] == 0
    assert funnel["watch_qualified_setups"] == len(payload["opportunities"]) or funnel[
        "watch_qualified_setups"
    ] >= 1
    board = next(c for c in payload["unlock_deploy"]["conditions"] if c["key"] == "board")
    assert "watch-qualified" in board["detail"] or "scan-ranked" in board["detail"]
    assert "validated" not in board["detail"]
    assert "(watch-qualified)" not in board["detail"] or "not watch-qualified" in board["detail"]
    assert payload["board_mode_label"] == _COMPRESSED_LABEL
    first = payload["opportunities"][0]
    assert first.get("score_display_mode") == "fallback_rank"
    assert first.get("score_display") in ("High", "Medium", "Low")
    assert first.get("priority_tier") == first.get("score_display")


def test_build_emergency_response():
    payload = build_emergency_response(reason="test failure", detail="no data")
    assert payload["board_mode"] == BOARD_MODE_EMERGENCY
    assert payload["count"] == 0
    assert payload["emergency"]["actions"]


def test_annotate_board_mode_full_live():
    payload = annotate_board_mode({"source": "ranked_pipeline"}, from_live=True)
    assert payload["board_mode"] == BOARD_MODE_FULL
    assert payload["board_mode_label"] == _LIVE_BOARD_LABEL
    assert "Full live board" not in payload["board_mode_label"]


def test_annotate_board_mode_snapshot_label():
    payload = annotate_board_mode(
        {"source": "ranked_pipeline", "cached": True, "stale": True},
        from_live=True,
    )
    assert payload["board_mode_label"] == _SNAPSHOT_BOARD_LABEL


def test_resolve_board_mode_label_fallback():
    assert resolve_board_mode_label({"compressed": True}) == _COMPRESSED_LABEL
    assert resolve_board_mode_label({"source": "compressed_fallback"}) == _COMPRESSED_LABEL


def test_snapshot_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "playbook_ranked_snapshot.json")

        def _path():
            return cache_path

        with patch("src.services.playbook_board_fallback._snapshot_path", _path):
            sample = build_compressed_fallback(30, brief=SAMPLE_BRIEF)
            save_playbook_snapshot(sample)
            loaded = load_playbook_snapshot()
            assert loaded is not None
            assert loaded.get("board_mode") == BOARD_MODE_COMPRESSED
            assert loaded.get("cached") is True


def test_compressed_empty_brief_is_emergency():
    payload = build_compressed_fallback(30, brief={})
    assert payload["board_mode"] == BOARD_MODE_EMERGENCY


def test_supplement_zero_deploy_from_all_avoid_scan():
    from src.services.playbook_board_fallback import (
        board_has_content,
        supplement_zero_deploy_board,
    )

    live = {
        "source": "ranked_pipeline",
        "board_mode": BOARD_MODE_FULL,
        "opportunities": [
            {"ticker": "COST", "action": "AVOID", "score": 4.8},
            {"ticker": "PANW", "action": "AVOID", "score": 4.7},
            {"ticker": "JPM", "action": "AVOID", "score": 4.6},
        ],
        "filter_funnel": {"execution_ready_setups": 0},
        "rejection_clusters": [{"key": "laggard", "count": 3}],
    }
    out = supplement_zero_deploy_board(live, 30)
    assert len(out.get("near_miss") or []) >= 1
    assert out["near_miss"][0]["action"] == "WATCH"
    assert board_has_content(out)


def test_supplement_zero_deploy_uses_brief_when_scan_empty():
    from src.services.playbook_board_fallback import supplement_zero_deploy_board

    empty = {
        "source": "ranked_pipeline",
        "opportunities": [],
        "filter_funnel": {"execution_ready_setups": 0},
    }
    out = supplement_zero_deploy_board(empty, 30)
    assert out.get("board_mode") == BOARD_MODE_COMPRESSED or out.get("near_miss")


def test_index_html_legacy_opps_wired_to_effective_card_action():
    index = Path(__file__).resolve().parents[1] / "src" / "api" / "templates" / "index.html"
    raw = index.read_text(encoding="utf-8")
    idx = raw.index("Fallback to legacy opps")
    block = raw[idx : idx + 900]
    assert "effectiveCardAction(r)" in block
    assert "playbookOppsFallbackVisible()" in block


if __name__ == "__main__":
    test_build_compressed_fallback_from_brief()
    test_build_emergency_response()
    test_annotate_board_mode_full_live()
    test_compressed_empty_brief_is_emergency()
    test_snapshot_roundtrip()
    print("all tests passed")
