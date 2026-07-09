"""Forward outcome tracker — study labels, not trade results."""

from __future__ import annotations

from src.services.forward_outcome_tracker import (
    STUDY_LABEL,
    build_forward_outcome_study,
    compute_forward_outcome,
    summarize_forward_outcomes,
)


def test_watch_candidate_labeled_study_not_trade_result():
    outcome = compute_forward_outcome(
        ticker="AAPL",
        event_id="DE-1",
        event_timestamp="2026-07-09T00:00:00Z",
        horizon=5,
        entry_ref=100.0,
        stop_ref=95.0,
        target_ref=110.0,
        future_price=108.0,
        event_type="WATCH_CANDIDATE",
        had_real_trade=False,
    )
    d = outcome.to_dict()
    assert d["label"] == STUDY_LABEL
    assert d["not_trade_result"] is True
    assert d["is_trade_result"] is False


def test_blocked_state_can_record_avoided_loss():
    outcome = compute_forward_outcome(
        ticker="XYZ",
        event_id="DE-2",
        event_timestamp="2026-07-09T00:00:00Z",
        horizon=5,
        entry_ref=50.0,
        stop_ref=48.0,
        future_price=45.0,
        event_type="BOARD_BLOCKED",
    )
    assert outcome.avoided_loss is True
    assert outcome.forward_r is not None
    assert outcome.forward_r < 0


def test_horizons_computed_correctly():
    event = {
        "ticker": "KO",
        "event_id": "DE-3",
        "timestamp": "2026-07-09",
        "entry_ref": 60.0,
        "stop_ref": 58.0,
        "target_ref": 65.0,
        "event_type": "NEAR_MISS",
    }
    study = build_forward_outcome_study(
        event,
        price_series={1: 60.5, 3: 61.0, 5: 62.0, 10: 63.0, 20: 64.0},
    )
    assert len(study) == 5
    horizons = [s["horizon"] for s in study]
    assert horizons == [1, 3, 5, 10, 20]
    assert all(s["label"] == STUDY_LABEL for s in study)
    assert study[2]["forward_return_pct"] is not None


def test_summarize_learning_mode_when_n_low():
    studies = [
        build_forward_outcome_study(
            {"ticker": "A", "event_id": "1", "timestamp": "t", "entry_ref": 10, "stop_ref": 9},
            price_series={5: 10.5},
        )
    ]
    summary = summarize_forward_outcomes(studies)
    assert summary["learning_mode"] is True
    assert "Learning mode" in summary["display_note"]
