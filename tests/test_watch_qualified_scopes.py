"""Scoped watch/deploy count labels on candidate buckets."""

from __future__ import annotations

from src.services.today_insights import build_candidate_bucket_counts


def test_candidate_bucket_explicit_counts():
    counts = build_candidate_bucket_counts(
        council_results=[object()] * 120,
        funnel={
            "universe_scanned": 120,
            "watch_qualified_setups": 4,
            "deploy_qualified_setups": 0,
        },
        top5=[{"ticker": "A", "action": "WATCH"}, {"ticker": "B", "action": "AVOID"}],
        near_miss=[{"ticker": "C", "action": "WATCH"}],
        avoid_grouped={"total": 3},
    )
    assert counts["scannerCandidates"] == 120
    assert counts["funnelWatchQualified"] == 4
    assert counts["deployQualified"] == 0
    assert counts["validMonitorCount"] == 1
    assert counts["rejectedHidden"] == 3
