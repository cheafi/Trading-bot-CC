"""Mutually exclusive Playbook buckets."""

from __future__ import annotations

from src.services.playbook_truth import assign_primary_bucket, bucket_counts, bucket_rows


def test_one_primary_bucket_per_row():
    rows = [
        {"ticker": "AAA", "action": "TRADE", "execution_ready": True},
        {"ticker": "BBB", "action": "PILOT", "execution_ready": False},
        {"ticker": "CCC", "action": "WATCH", "score": 7.0},
        {"ticker": "DDD", "action": "AVOID"},
        {"ticker": "EEE", "action": "WATCH", "score": 6.5, "whats_missing": "timing"},
    ]
    buckets = bucket_rows(rows, deploy_authority=True, near_miss_tickers={"EEE"})
    assert len(buckets["Deploy"]) == 1
    assert buckets["Deploy"][0]["ticker"] == "AAA"
    assert len(buckets["Pilot"]) == 1
    assert buckets["Pilot"][0]["ticker"] == "BBB"
    assert len(buckets["Watch"]) == 1
    assert buckets["Watch"][0]["ticker"] == "CCC"
    assert len(buckets["Near-miss"]) == 1
    assert buckets["Near-miss"][0]["ticker"] == "EEE"
    assert len(buckets["Rejected"]) == 1
    assert buckets["Rejected"][0]["ticker"] == "DDD"


def test_bucket_counts_sum_to_rows():
    rows = [
        {"ticker": "A", "action": "WATCH", "score": 5},
        {"ticker": "B", "action": "AVOID"},
    ]
    counts = bucket_counts(rows, deploy_authority=False)
    assert sum(counts.values()) == len(rows)


def test_assign_primary_bucket_deploy_requires_authority():
    row = {"ticker": "X", "action": "TRADE", "execution_ready": True}
    assert assign_primary_bucket(row, deploy_authority=False) == "Watch"
    assert assign_primary_bucket(row, deploy_authority=True) == "Deploy"
