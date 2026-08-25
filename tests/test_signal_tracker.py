"""Tests for the persistent signal tracker (research-only ledger)."""

from __future__ import annotations

import os

import pytest

from src.services.signal_tracker import (
    STAGE_DEPLOY_QUALIFIED,
    STAGE_EXECUTED,
    STAGE_MONITOR,
    STAGE_SCANNED,
    STAGE_STOPPED,
    STAGE_WINNER,
    SignalTracker,
    build_signal_tracking_context,
    rs_bucket,
    vix_bucket,
)


@pytest.fixture()
def tracker(tmp_path):
    return SignalTracker(path=str(tmp_path / "ledger.jsonl"))


def test_record_and_reduce_to_latest(tracker):
    sid = tracker.record_signal(
        ticker="aapl",
        date="2026-06-01",
        strategy_family="breakout",
        vix=18.0,
        rs_pct=92.0,
        sector="tech",
    )
    cur = tracker.current()
    assert sid in cur
    rec = cur[sid]
    assert rec["ticker"] == "AAPL"
    assert rec["stage"] == STAGE_SCANNED
    assert rec["vix_bucket"] == "normal"
    assert rec["rs_bucket"] == "top_decile"


def test_stage_is_monotonic(tracker):
    sid = tracker.record_signal(
        ticker="MSFT", date="2026-06-01", strategy_family="pullback", stage=STAGE_MONITOR
    )
    assert tracker.advance_stage(sid, STAGE_DEPLOY_QUALIFIED) is True
    # Cannot rewind to an earlier stage.
    assert tracker.advance_stage(sid, STAGE_SCANNED) is False
    assert tracker.current()[sid]["stage"] == STAGE_DEPLOY_QUALIFIED
    assert tracker.current()[sid]["deploy_qualified"] is True


def test_stopped_marks_failure_reason(tracker):
    sid = tracker.record_signal(
        ticker="NVDA", date="2026-06-01", strategy_family="breakout", stage=STAGE_EXECUTED
    )
    tracker.advance_stage(sid, STAGE_STOPPED, failure_reason="false_breakout")
    rec = tracker.current()[sid]
    assert rec["failed"] is True
    assert rec["failure_reason"] == "false_breakout"


def test_record_outcome_merges_forward_returns(tracker):
    sid = tracker.record_signal(
        ticker="AMD", date="2026-06-01", strategy_family="breakout"
    )
    tracker.record_outcome(sid, fwd={"d5": 2.1}, mfe_pct=4.0, mae_pct=-1.5)
    tracker.record_outcome(sid, fwd={"d20": 6.3})
    rec = tracker.current()[sid]
    assert rec["fwd"] == {"d5": 2.1, "d20": 6.3}
    assert rec["mfe_pct"] == 4.0
    assert rec["mae_pct"] == -1.5


def test_conversion_funnel_counts_cumulatively(tracker):
    a = tracker.record_signal(ticker="A", date="d", strategy_family="b")
    b = tracker.record_signal(ticker="B", date="d", strategy_family="b", stage=STAGE_EXECUTED)
    tracker.advance_stage(b, STAGE_WINNER)
    funnel = tracker.conversion_funnel()
    assert funnel["total_signals"] == 2
    # Both reached 'scanned'; only one reached executed/winner.
    assert funnel["stages"][STAGE_SCANNED] == 2
    assert funnel["stages"][STAGE_EXECUTED] == 1
    assert funnel["stages"][STAGE_WINNER] == 1
    assert funnel["win_rate_on_executed"] == 1.0


def test_cohort_summary_by_regime(tracker):
    tracker.record_signal(
        ticker="A", date="d", strategy_family="b",
        regime_at_entry={"trend": "UPTREND"}, stage=STAGE_EXECUTED,
    )
    sid = tracker.make_id("A", "d", "b")
    tracker.advance_stage(sid, STAGE_WINNER)
    tracker.record_outcome(sid, fwd={"d20": 5.0})
    summary = tracker.cohort_summary("regime")
    buckets = {c["bucket"]: c for c in summary["cohorts"]}
    assert "UPTREND" in buckets
    assert buckets["UPTREND"]["win_rate"] == 1.0
    assert buckets["UPTREND"]["mean_fwd_20d"] == 5.0


def test_thin_sample_flagged_in_context(tracker):
    tracker.record_signal(ticker="A", date="d", strategy_family="b")
    ctx = build_signal_tracking_context(tracker)
    assert ctx["thin_sample"] is True
    assert ctx["funnel"]["evidence_quality"]["sample_label"] == "thin_sample"


def test_persistence_survives_new_instance(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    t1 = SignalTracker(path=path)
    t1.record_signal(ticker="X", date="d", strategy_family="b")
    assert os.path.exists(path)
    t2 = SignalTracker(path=path)
    assert len(t2.current()) == 1


def test_buckets():
    assert vix_bucket(None) == "unknown"
    assert vix_bucket(10) == "calm"
    assert vix_bucket(45) == "extreme"
    assert rs_bucket(95) == "top_decile"
    assert rs_bucket(5) == "laggard"
    assert rs_bucket(None) == "unknown"
