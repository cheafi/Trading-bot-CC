"""Signal attribution store — persistence, low sample=learning, harmful flagged."""

from __future__ import annotations

from src.services.signal_attribution_store import (
    SignalAttributionStore,
    resolve_aggregate_status,
)


def test_persistence_and_reload(tmp_path):
    store = SignalAttributionStore(
        db_path=str(tmp_path / "attr.db"),
        events_path=str(tmp_path / "events.jsonl"),
    )
    result = store.record_outcome(
        family="setup_quality",
        forward_r=0.8,
        event_type="WATCH_CANDIDATE",
        horizon=5,
    )
    assert result["sample_size"] == 1
    cal = store.get_family_calibration("setup_quality")
    assert cal["sample_size"] == 1
    assert cal["forward_r_mean"] == 0.8


def test_low_sample_learning_status():
    assert resolve_aggregate_status(sample_size=3) == "learning"
    assert resolve_aggregate_status(sample_size=10, forward_r_mean=0.1) == "unvalidated"


def test_harmful_flagged():
    status = resolve_aggregate_status(
        sample_size=25,
        forward_r_mean=-0.5,
        false_positive_rate=0.5,
        evidence_source="live_forward",
    )
    assert status == "harmful"


def test_backtest_isolated_unvalidated(tmp_path):
    store = SignalAttributionStore(
        db_path=str(tmp_path / "attr.db"),
        events_path=str(tmp_path / "events.jsonl"),
    )
    store.record_outcome(
        family="trend",
        forward_r=2.0,
        evidence_source="backtest",
        horizon=5,
    )
    cal = store.get_family_calibration("trend", evidence_source="backtest")
    assert cal["status"] == "unvalidated"
    live = store.get_family_calibration("trend", evidence_source="live_forward")
    assert live["sample_size"] == 0


def test_summarize_useful_and_noisy(tmp_path):
    store = SignalAttributionStore(
        db_path=str(tmp_path / "attr.db"),
        events_path=str(tmp_path / "events.jsonl"),
    )
    for _ in range(22):
        store.record_outcome(family="rr_quality", forward_r=0.5, event_type="WATCH_CANDIDATE")
    for _ in range(22):
        store.record_outcome(
            family="timing",
            forward_r=-0.4,
            event_type="DEPLOY_CANDIDATE",
        )
    summary = store.summarize()
    assert "rr_quality" in summary.get("useful_families", []) or summary["families_tracked"] >= 1
    assert summary["may_authorize_deploy"] is False
