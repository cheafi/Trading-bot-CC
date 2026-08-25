"""Research-tier opportunity filters — more watch names, less noise."""

from __future__ import annotations

from src.services.opportunity_scan_filters import (
    dedupe_correlated_rows,
    filter_watch_promotion_candidates,
    passes_liquidity_filter,
    passes_scanner_agreement,
    scanner_agreement_count,
)
from src.services.playbook_near_miss import (
    PLAYBOOK_NEAR_MISS_LIMIT,
    build_playbook_near_miss_rows,
)


def test_scanner_agreement_requires_two_flags():
    weak = {"ticker": "A", "score": 6.0, "vol_ratio": 1.0}
    strong = {
        "ticker": "B",
        "score": 6.5,
        "vol_ratio": 1.4,
        "rs_rank": 78,
        "leader": "LEADER",
        "near_52w_high": True,
    }
    assert scanner_agreement_count(weak) < 2
    assert not passes_scanner_agreement(weak)
    assert scanner_agreement_count(strong) >= 2
    assert passes_scanner_agreement(strong)


def test_liquidity_filter_drops_dead_volume():
    assert passes_liquidity_filter({"vol_ratio": 1.1}) is True
    assert passes_liquidity_filter({"vol_ratio": 0.5}) is False


def test_dedupe_correlated_sector_cap():
    rows = [
        {"ticker": f"T{i}", "sector_type": "TECH", "theme": f"Theme{i}", "score": 6.0 + i * 0.1}
        for i in range(6)
    ]
    kept, dropped = dedupe_correlated_rows(rows, max_per_sector=3, max_per_theme=2)
    assert len(kept) == 3
    assert dropped == 3


def test_filter_watch_promotion_increases_quality():
    rows = [
        {"ticker": "GOOD", "score": 6.2, "vol_ratio": 1.5, "rs_rank": 75, "leader": "LEADER"},
        {"ticker": "BAD_VOL", "score": 6.5, "vol_ratio": 0.4},
        {"ticker": "BAD_AGREE", "score": 6.0, "vol_ratio": 1.0},
    ]
    out, stats = filter_watch_promotion_candidates(rows)
    tickers = {r["ticker"] for r in out}
    assert "GOOD" in tickers
    assert "BAD_VOL" not in tickers
    assert stats["liquidity_dropped"] >= 1


def test_near_miss_pool_expanded_without_deploy_inflation():
    opps = [
        {
            "ticker": f"W{i}",
            "action": "WATCH",
            "score": 5.2 + i * 0.05,
            "vol_ratio": 1.3,
            "rs_rank": 70 + i,
            "leader": "LEADER",
            "execution_ready": False,
        }
        for i in range(20)
    ] + [
        {
            "ticker": "DEPLOY1",
            "action": "TRADE",
            "score": 9.0,
            "execution_ready": True,
        }
    ]
    near = build_playbook_near_miss_rows(opps, limit=PLAYBOOK_NEAR_MISS_LIMIT)
    assert len(near) <= PLAYBOOK_NEAR_MISS_LIMIT
    assert PLAYBOOK_NEAR_MISS_LIMIT == 24
    assert all(not r.get("execution_ready") for r in near)
    assert "DEPLOY1" not in {r["ticker"] for r in near}
