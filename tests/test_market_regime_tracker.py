"""Tests for the market regime tracker (research/monitor-only)."""

from __future__ import annotations

import pytest

from src.services.market_regime_tracker import (
    FOLLOW_THROUGH_CONFIRMED,
    FOLLOW_THROUGH_FAILED,
    MarketRegimeTracker,
    breadth_health,
    build_regime_timeline_context,
)


@pytest.fixture()
def trk(tmp_path):
    return MarketRegimeTracker(path=str(tmp_path / "regime.jsonl"))


def _seed_down_days(trk, n, start_day=1):
    for i in range(n):
        trk.record_snapshot(
            date=f"2026-06-{start_day + i:02d}",
            trend="SIDEWAYS",
            tradeability="SELECTIVE",
            index_change_pct=-0.5,
            volume_vs_prior=1.3,  # rising volume → distribution day
            vix=22.0,
            breadth=45.0,
        )


def test_distribution_day_count(trk):
    _seed_down_days(trk, 5)
    dist = trk.distribution_day_count()
    assert dist["count"] == 5
    assert dist["severity"] == "elevated"
    assert dist["sessions_missing_data"] == 0


def test_distribution_ignores_missing_data(trk):
    trk.record_snapshot(
        date="2026-06-01", trend="UP", tradeability="GO",
        index_change_pct=None, volume_vs_prior=None,
    )
    dist = trk.distribution_day_count()
    assert dist["count"] == 0
    assert dist["sessions_missing_data"] == 1


def test_follow_through_confirmed(trk):
    trk.record_snapshot(
        date="2026-06-01", trend="DOWN", tradeability="WAIT",
        index_change_pct=-0.8, volume_vs_prior=1.1,
    )
    trk.record_snapshot(
        date="2026-06-02", trend="UP", tradeability="SELECTIVE",
        index_change_pct=1.5, volume_vs_prior=1.4,
    )
    assert trk.follow_through_state()["state"] == FOLLOW_THROUGH_CONFIRMED


def test_follow_through_failed(trk):
    trk.record_snapshot(
        date="2026-06-01", trend="UP", tradeability="GO",
        index_change_pct=0.9, volume_vs_prior=1.0,
    )
    trk.record_snapshot(
        date="2026-06-02", trend="DOWN", tradeability="WAIT",
        index_change_pct=-1.3, volume_vs_prior=1.2,
    )
    assert trk.follow_through_state()["state"] == FOLLOW_THROUGH_FAILED


def test_regime_timeline_records_transitions(trk):
    trk.record_snapshot(date="d1", trend="UP", tradeability="GO", index_change_pct=0.5)
    trk.record_snapshot(date="d2", trend="UP", tradeability="GO", index_change_pct=0.3)
    trk.record_snapshot(date="d3", trend="DOWN", tradeability="WAIT", index_change_pct=-1.0)
    timeline = trk.regime_timeline()
    # First snapshot + one transition (d3).
    assert len(timeline) == 2
    assert timeline[-1]["date"] == "d3"
    assert timeline[-1]["from_trend"] == "UP"


def test_market_pressure_downgrade_only_and_componentized(trk):
    _seed_down_days(trk, 6)  # heavy distribution + elevated VIX + thin breadth
    pressure = trk.market_pressure_score()
    assert pressure["posture"] in {"defensive", "neutral", "constructive"}
    assert "distribution_days" in pressure["components"]
    assert "vix" in pressure["components"]
    # Heavy distribution + VIX 22 + breadth 45 should read defensive/neutral.
    assert pressure["score"] >= 40


def test_pressure_empty_is_degraded(trk):
    pressure = trk.market_pressure_score()
    assert pressure["degraded"] is True
    assert pressure["score"] is None


def test_sector_persistence(trk):
    trk.record_snapshot(
        date="d1", trend="UP", tradeability="GO", index_change_pct=0.5,
        leaders=["tech", "energy"], laggards=["utilities"],
    )
    trk.record_snapshot(
        date="d2", trend="UP", tradeability="GO", index_change_pct=0.4,
        leaders=["tech"], laggards=["utilities"],
    )
    sp = trk.sector_persistence()
    leaders = dict(sp["leader_cluster"])
    assert leaders["tech"] == 2
    assert dict(sp["laggard_cluster"])["utilities"] == 2


def test_context_payload_shape(trk):
    trk.record_snapshot(
        date="d1", trend="UP", tradeability="GO",
        index_change_pct=0.5, vix=18.0, breadth=55.0,
    )
    ctx = build_regime_timeline_context(trk)
    assert "market_pressure" in ctx
    assert "distribution_days" in ctx
    assert "regime_timeline" in ctx


def test_breadth_health():
    assert breadth_health(None) == "unknown"
    assert breadth_health(70) == "broad"
    assert breadth_health(30) == "thin"
