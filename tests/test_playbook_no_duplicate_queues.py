"""Playbook — one primary bucket per ticker, no duplicate queue sections."""

from __future__ import annotations

from src.services.playbook_truth import bucket_rows


def test_no_ticker_in_multiple_primary_buckets():
    rows = [
        {"ticker": "AAA", "action": "TRADE", "execution_ready": True},
        {"ticker": "BBB", "action": "PILOT"},
        {"ticker": "CCC", "action": "WATCH", "score": 7.0},
        {"ticker": "DDD", "action": "WATCH", "score": 6.5, "whats_missing": "timing"},
        {"ticker": "EEE", "action": "AVOID"},
    ]
    buckets = bucket_rows(rows, deploy_authority=True, near_miss_tickers={"DDD"})
    seen: set[str] = set()
    for bucket, items in buckets.items():
        for row in items:
            ticker = str(row.get("ticker") or "").upper()
            assert ticker not in seen, f"{ticker} duplicated across buckets"
            seen.add(ticker)
    assert seen == {"AAA", "BBB", "CCC", "DDD", "EEE"}


def test_each_ticker_appears_in_exactly_one_bucket():
    """Primary queue sections must not show the same ticker twice."""
    rows = [
        {"ticker": "SPY", "action": "TRADE", "execution_ready": True},
        {"ticker": "QQQ", "action": "PILOT"},
        {"ticker": "IWM", "action": "WATCH", "score": 8.0},
    ]
    buckets = bucket_rows(rows, deploy_authority=True)
    ticker_to_bucket: dict[str, str] = {}
    for bucket, items in buckets.items():
        for row in items:
            ticker = str(row.get("ticker") or "").upper()
            assert ticker not in ticker_to_bucket
            ticker_to_bucket[ticker] = bucket
    assert ticker_to_bucket["SPY"] == "Deploy"
    assert ticker_to_bucket["QQQ"] == "Pilot"
    assert ticker_to_bucket["IWM"] == "Watch"
