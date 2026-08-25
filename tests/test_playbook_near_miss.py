"""Playbook near-miss queue and abnormal-volume research tier."""

from src.engines.scanner_matrix import AbnormalVolumeScanner, ScannerMatrix
from src.services.playbook_near_miss import (
    PLAYBOOK_NEAR_MISS_LIMIT,
    build_discovery_near_miss_strip,
    build_playbook_near_miss_rows,
)


def test_near_miss_includes_high_scoring_avoid_rows():
    opps = [
        {
            "ticker": "NVDA",
            "action": "AVOID",
            "score": 6.2,
            "timing_conf": 0.62,
            "thesis_conf": 0.4,
            "vol_ratio": 1.4,
            "rs_rank": 80,
            "near_52w_high": True,
            "execution_ready": False,
        },
        {
            "ticker": "COST",
            "action": "AVOID",
            "score": 4.0,
            "timing_conf": 0.3,
            "execution_ready": False,
        },
        {
            "ticker": "AAPL",
            "action": "TRADE",
            "score": 8.0,
            "execution_ready": True,
        },
    ]
    near = build_playbook_near_miss_rows(opps, limit=PLAYBOOK_NEAR_MISS_LIMIT)
    tickers = {r["ticker"] for r in near}
    assert "NVDA" in tickers
    assert "COST" not in tickers
    assert "AAPL" not in tickers
    assert near[0]["action"] == "WATCH"
    assert near[0]["near_miss_label"] == "near_miss"
    assert near[0]["execution_ready"] is False


def test_abnormal_volume_research_tier_at_1_5x():
    scanner = AbnormalVolumeScanner()
    hits = scanner.scan(
        [
            {"ticker": "LOW", "vol_ratio": 1.2},
            {"ticker": "MID", "vol_ratio": 1.6},
            {"ticker": "HIGH", "vol_ratio": 2.2},
        ],
        {},
    )
    by_ticker = {h.ticker: h for h in hits}
    assert "LOW" not in by_ticker
    assert by_ticker["MID"].metadata.get("research_only") is True
    assert by_ticker["HIGH"].metadata.get("research_only") is False


def test_abnormal_volume_research_enriched_for_ui():
    scanner = AbnormalVolumeScanner()
    hits = scanner.scan([{"ticker": "X", "vol_ratio": 1.7}], {})
    ui = ScannerMatrix.enrich_hit_for_ui(hits[0])
    assert ui.get("research_only") is True
    assert ui.get("monitor_label") == "research_only"


def test_discovery_near_miss_strip_from_merged():
    merged = [
        {"ticker": "A", "action": "WATCH", "status": "speculative", "max_score": 6.5},
        {"ticker": "B", "action": "TRADE", "status": "confirmed", "max_score": 8.0},
    ]
    strip = build_discovery_near_miss_strip(merged, limit=8)
    assert len(strip) == 1
    assert strip[0]["ticker"] == "A"
    assert strip[0]["research_only"] is True
