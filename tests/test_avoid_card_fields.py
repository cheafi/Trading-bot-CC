"""AVOID / rejected cards must not expose deploy fields in opportunity filter."""

from __future__ import annotations

from src.services.today_insights import build_top_opportunities, filter_valid_opportunities


def test_avoid_excluded_from_top_opportunities():
    rows = [
        {"ticker": "BAD", "action": "AVOID", "entry_price": 10, "target_price": 12},
        {"ticker": "OK", "action": "WATCH", "entry_price": 20},
    ]
    out = build_top_opportunities(rows)
    assert len(out) == 1
    assert out[0]["ticker"] == "OK"


def test_no_backfill_with_rejected():
    rows = [
        {"ticker": "A", "action": "AVOID"},
        {"ticker": "B", "action": "NO_TRADE"},
    ]
    assert filter_valid_opportunities(rows) == []


def test_rejected_display_mode_hidden():
    rows = [{"ticker": "Z", "action": "WATCH", "card_display_mode": "rejected"}]
    assert filter_valid_opportunities(rows) == []
