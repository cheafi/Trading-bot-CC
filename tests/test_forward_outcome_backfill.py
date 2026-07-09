"""Forward outcome backfill — forward return, missing price, watch=study, avoided loss."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.services.forward_outcome_backfill import (
    ForwardOutcomeStore,
    backfill_event_outcomes,
    backfill_missing_outcomes,
    build_price_series_from_history,
    enrich_outcome_record,
)


def _event(**kw):
    base = {
        "event_id": "DE-BF001",
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "ticker": "AAPL",
        "entry_ref": 100.0,
        "stop_ref": 95.0,
        "target_ref": 110.0,
        "event_type": "WATCH_CANDIDATE",
        "authority_state": {"deploy_authority_tier": "blocked"},
    }
    base.update(kw)
    return base


def test_forward_return_from_history(tmp_path):
    history = [
        {"date": "2026-06-01", "close": 100.0},
        {"date": "2026-06-02", "close": 101.0},
        {"date": "2026-06-03", "close": 102.0},
        {"date": "2026-06-04", "close": 103.0},
        {"date": "2026-06-05", "close": 104.0},
    ]
    series = build_price_series_from_history(
        history, event_ts="2026-06-01T12:00:00Z", entry_ref=100.0
    )
    store = ForwardOutcomeStore(path=str(tmp_path / "outcomes.jsonl"))
    outcomes = backfill_event_outcomes(
        _event(timestamp="2026-06-01T12:00:00Z"),
        history_rows=history,
        store=store,
    )
    assert len(outcomes) == 5
    assert outcomes[0]["forward_return_pct"] is not None
    assert outcomes[0]["outcome_label"] == "study"
    assert outcomes[0]["data_quality"] in ("complete", "partial")


def test_missing_price_skipped(tmp_path):
    store = ForwardOutcomeStore(path=str(tmp_path / "outcomes.jsonl"))
    outcomes = backfill_event_outcomes(
        _event(ticker=""),
        price_series={},
        store=store,
    )
    assert outcomes == []


def test_watch_labeled_study_not_trade(tmp_path):
    store = ForwardOutcomeStore(path=str(tmp_path / "outcomes.jsonl"))
    outcomes = backfill_event_outcomes(
        _event(event_type="WATCH_CANDIDATE"),
        price_series={5: 108.0},
        store=store,
    )
    assert outcomes[2]["outcome_label"] == "study"
    assert outcomes[2]["study_not_trade"] is True
    assert outcomes[2]["is_trade_result"] is False


def test_blocked_avoided_loss(tmp_path):
    store = ForwardOutcomeStore(path=str(tmp_path / "outcomes.jsonl"))
    outcomes = backfill_event_outcomes(
        _event(event_type="BOARD_BLOCKED"),
        price_series={5: 90.0},
        store=store,
    )
    h5 = [o for o in outcomes if o["horizon"] == 5][0]
    assert h5["avoided_loss"] is True
    assert h5["forward_r"] is not None
    assert h5["forward_r"] < 0


def test_backfill_missing_dry_run(tmp_path):
    store = ForwardOutcomeStore(path=str(tmp_path / "outcomes.jsonl"))
    events = [_event(event_id="DE-1"), _event(event_id="DE-2", ticker="MSFT")]
    result = backfill_missing_outcomes(
        events,
        price_fetcher=lambda t, h: 105.0,
        store=store,
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert store.count_distinct_events() == 0


def test_enrich_includes_metadata():
    rec = enrich_outcome_record(
        {"horizon": 5, "forward_r": 1.2},
        event=_event(),
        data_quality="complete",
        outcome_source="market_data",
    )
    assert rec["authority_effect"] == "none"
    assert rec["may_authorize_deploy"] is False
    assert rec["outcome_source"] == "market_data"
