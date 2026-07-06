"""Discovery funnel caps — shortlist / watch / priority limits."""

from __future__ import annotations

from src.engines.scanner_matrix import (
    DISCOVERY_HIGH_PRIORITY_CAP,
    DISCOVERY_QUALIFIED_WATCH_CAP,
    DISCOVERY_SHORTLIST_CAP,
    ScannerCategory,
    ScannerHit,
    ScannerMatrix,
    ScannerPriority,
)


def test_discovery_funnel_cap_constants():
    assert DISCOVERY_SHORTLIST_CAP == 10
    assert DISCOVERY_QUALIFIED_WATCH_CAP == 10
    assert DISCOVERY_HIGH_PRIORITY_CAP == 5


def test_similar_pattern_debug_only_bucket():
    hits = [
        {"ticker": f"T{i}", "score": 7.0, "scanner": "similar_pattern"}
        for i in range(15)
    ]
    bucket = ScannerMatrix.normalize_scanner_bucket(hits, scanner_name="similar_pattern")
    assert bucket.get("debug_only") is True
    assert bucket["display_count"] <= DISCOVERY_QUALIFIED_WATCH_CAP
    assert bucket.get("debug_total_hits") == 15


def test_merged_discovery_rank_caps():
    matrix = ScannerMatrix()
    grouped = {
        "PATTERN": {
            "vcp": {
                "count": 50,
                "top_hits": [
                    {
                        "ticker": f"N{i}",
                        "score": 8.0,
                        "strength": 8.0,
                        "scanner": "vcp",
                        "headline": "VCP",
                    }
                    for i in range(50)
                ],
            }
        }
    }
    summary = {"PATTERN": {"count": 50}}
    out = matrix.build_merged_discovery_rank(grouped, summary, {"label": "UPTREND"}, universe_size=500)
    assert len(out["merged_top_names"]) <= DISCOVERY_SHORTLIST_CAP
    caps = out["funnel_caps"]
    assert caps["shortlist_count"] <= DISCOVERY_SHORTLIST_CAP
    assert caps["qualified_watch_count"] <= DISCOVERY_QUALIFIED_WATCH_CAP
    assert caps["high_priority_count"] <= DISCOVERY_HIGH_PRIORITY_CAP


def test_enrich_hit_invalid_score():
    hit = ScannerHit(
        scanner_name="vcp",
        category=ScannerCategory.PATTERN,
        ticker="BAD",
        score=-491.5,
        headline="bad",
    )
    row = ScannerMatrix.enrich_hit_for_ui(hit)
    assert row.get("score_display") == "invalid"
    assert row.get("calibration_state") == "invalid"
    assert row.get("score") is None
