"""Playbook funnel layer normalization."""

from __future__ import annotations

from src.services.decision_truth_model import (
    PLAYBOOK_FUNNEL_LAYER_DEFINITIONS,
    format_board_quality_detail,
    normalize_playbook_funnel,
    playbook_funnel_layer_note,
    playbook_scan_ranked_count,
)


def test_normalize_playbook_funnel_layers():
    """Watch count follows funnel / near_miss — not WATCH-labeled board rows."""
    out = normalize_playbook_funnel(
        {"universe_scanned": 50, "execution_ready_setups": 0},
        opportunities=[{"action": "WATCH"}, {"action": "WATCH"}, {"action": "AVOID"}],
        near_miss=[{"ticker": "A"}, {"ticker": "B"}],
    )
    assert out["universe_scanned"] == 50
    assert out["watch_qualified_setups"] == 2
    assert out["deploy_qualified_setups"] == 0


def test_normalize_does_not_inflate_watch_from_opportunity_actions():
    out = normalize_playbook_funnel(
        {"universe_scanned": 50, "execution_ready_setups": 0},
        opportunities=[{"action": "WATCH"}, {"action": "WATCH"}, {"action": "WATCH"}],
    )
    assert out["watch_qualified_setups"] == 0


def test_normalize_does_not_inflate_watch_from_high_score():
    """high_score_setups must not substitute for watch-qualified when watch is zero."""
    out = normalize_playbook_funnel(
        {
            "universe_scanned": 50,
            "watch_qualified_setups": 0,
            "high_score_setups": 50,
            "execution_ready_setups": 0,
        }
    )
    assert out["watch_qualified_setups"] == 0


def test_playbook_funnel_layer_definitions():
    assert "scanned" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS
    assert "near_miss" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS
    assert "monitor upgrade" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS["near_miss"]
    note = playbook_funnel_layer_note()
    assert "Watch-qualified" in note
    assert "Near-miss" in note
    assert "validated" not in note.lower()


def test_board_quality_detail_scan_ranked_when_watch_zero():
    assert format_board_quality_detail(0, scan_ranked=50) == (
        "50 scan-ranked (not watch-qualified)"
    )
    assert format_board_quality_detail(2, scan_ranked=50) == "2 watch-qualified"
    assert playbook_scan_ranked_count(
        {"watch_qualified_setups": 0, "universe_scanned": 50}
    ) == 50
    assert playbook_scan_ranked_count({"watch_qualified_setups": 2}) == 0
