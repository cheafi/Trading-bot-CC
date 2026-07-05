"""Candidate lifecycle — mutually exclusive buckets."""

from __future__ import annotations

from src.services.candidate_lifecycle import (
    BUCKET_DEPLOY,
    BUCKET_REJECTED,
    BUCKET_WATCH,
    bucket_candidate,
    enforce_bucket_exclusivity,
    filter_rejected_from_top_slots,
    resolve_no_edge_state,
)


def _row(ticker, action="WATCH", **kw):
    return {"ticker": ticker, "action": action, **kw}


def test_bucket_exclusivity_one_primary():
    rows = [
        _row("A", "TRADE", execution_ready=True, score=8.0),
        _row("B", "AVOID"),
    ]
    buckets = enforce_bucket_exclusivity(rows, deploy_authority=True)
    assert len(buckets[BUCKET_DEPLOY]) == 1
    assert len(buckets[BUCKET_REJECTED]) == 1


def test_filter_rejected_from_top_slots():
    rows = [
        _row("A", "AVOID"),
        _row("B", "AVOID"),
        _row("C", "WATCH", score=7.0),
    ]
    top = filter_rejected_from_top_slots(rows, deploy_authority=False, limit=3)
    tickers = {r["ticker"] for r in top}
    assert "C" in tickers
    assert "A" not in tickers


def test_no_edge_when_only_rejected():
    rows = [_row(f"R{i}", "AVOID") for i in range(4)]
    state = resolve_no_edge_state(rows, deploy_authority=False)
    assert state["no_edge"] is True
    assert "do nothing" in state["best_action"]


def test_archived_bucket():
    row = _row("Z", "TRADE", archived=True)
    assert bucket_candidate(row, deploy_authority=True) == "Archived"


def test_bucket_candidate_matches_playbook_truth():
    from src.services.playbook_truth import assign_primary_bucket

    row = _row("A", "WATCH", score=7.0)
    assert bucket_candidate(row) == assign_primary_bucket(row)
    assert bucket_candidate(row, deploy_authority=True, near_miss=True) == assign_primary_bucket(
        row, deploy_authority=True, near_miss=True
    )


def test_enforce_bucket_exclusivity_single_primary_per_row():
    rows = [
        _row("A", "TRADE", execution_ready=True),
        _row("B", "WATCH", score=7.0),
        _row("C", "AVOID"),
    ]
    buckets = enforce_bucket_exclusivity(rows, deploy_authority=True)
    tagged = [r for group in buckets.values() for r in group]
    assert len(tagged) == 3
    assert len({r["primary_bucket"] for r in tagged}) == 3
