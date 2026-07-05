"""AVOID must not surface as top monitor or dashboard opportunity."""

from __future__ import annotations

from src.services.today_insights import (
    build_monitor_triggers,
    build_top_monitor,
    build_top_opportunities,
    pick_non_avoid_monitor,
    top_monitor_display_label,
)


def test_pick_non_avoid_monitor_skips_avoid():
    rows = [
        {"ticker": "BAD", "action": "AVOID"},
        {"ticker": "OK", "action": "WATCH"},
    ]
    pick = pick_non_avoid_monitor(rows)
    assert pick and pick["ticker"] == "OK"


def test_top_monitor_label_no_valid_when_all_avoid():
    label = top_monitor_display_label(
        monitors=[{"ticker": "X", "action": "AVOID"}],
        near_miss=[{"ticker": "Y", "action": "NO_TRADE"}],
    )
    assert label == "No valid monitor candidates"


def test_top_opportunities_excludes_avoid():
    rows = build_top_opportunities(
        [
            {"ticker": "AVD", "action": "AVOID"},
            {"ticker": "OK", "action": "WATCH"},
        ]
    )
    assert [r["ticker"] for r in rows] == ["OK"]


def test_top_monitor_never_avoid():
    mon = build_top_monitor(
        top5=[{"ticker": "BAD", "action": "AVOID"}, {"ticker": "GOOD", "action": "WATCH"}],
        near_miss=[],
    )
    assert mon["ticker"] == "GOOD"
    assert mon["valid"] is True
    assert mon["action"] != "AVOID"


def test_monitor_triggers_skip_avoid_near_miss():
    triggers = build_monitor_triggers(
        market_pulse={},
        near_miss=[
            {"ticker": "AVD", "action": "AVOID", "whats_missing": "weak"},
            {"ticker": "NM", "action": "WATCH", "whats_missing": "timing"},
        ],
        vix=18,
        breadth=55,
        tradeability="WAIT",
    )
    labels = [t.get("label") for t in triggers]
    assert any("NM" in (lbl or "") for lbl in labels)
    assert not any("AVD" in (lbl or "") for lbl in labels)
