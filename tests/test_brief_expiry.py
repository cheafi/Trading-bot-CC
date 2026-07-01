"""Brief hard-expire — briefAgeDays > 2 excludes brief content."""

from __future__ import annotations

from src.services.today_insights import merge_brief_board_fallback


def test_merge_brief_skipped_when_expired():
    top, near, used = merge_brief_board_fallback(
        [],
        [],
        scanner_degraded=True,
        brief_age_days=21,
    )
    assert top == []
    assert near == []
    assert used is False


def test_merge_brief_allowed_when_fresh():
    top, near, used = merge_brief_board_fallback(
        [{"ticker": "LIVE", "action": "WATCH"}],
        [],
        scanner_degraded=False,
        brief_age_days=1,
    )
    assert len(top) == 1
    assert used is False


def test_brief_expired_freshness_in_truth():
    from src.services.system_truth import resolve_system_truth

    truth = resolve_system_truth(
        {"market_regime": {"tradeability": "WAIT", "should_trade": True}, "filter_funnel": {}},
        cc_header={},
        ops={},
        brief_age_days=21,
    )
    assert truth["brief_freshness"] == "expired"
    assert "BRIEF_EXPIRED" in truth["reason_codes"]
    assert "21d" in typed_line(truth)


def typed_line(truth):
    from src.services.system_truth import typed_freshness_display

    return typed_freshness_display(truth)
