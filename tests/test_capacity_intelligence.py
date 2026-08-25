"""Tests for the capacity intelligence layer (research-only, downgrade-only)."""

from __future__ import annotations

import math

from src.services.capacity_intelligence import (
    CAP_GOOD_CANNOT_SCALE,
    CAP_LOW_CAPACITY,
    CAP_PILOT_ONLY,
    CAP_SCALES_CLEAN,
    CAP_SCALE_WEAK_EXEC,
    CAP_UNKNOWN,
    HARD_LIMIT_PARTICIPATION,
    TARGET_PARTICIPATION,
    assess_capacity,
    build_capacity_chip,
    build_capacity_context,
    build_sleeve_capacity,
    classify_capacity,
    edge_net_of_scale,
    market_impact_bps,
    participation_ceiling_shares,
    participation_fraction,
)


# -- primitives -------------------------------------------------------------
def test_participation_fraction():
    assert participation_fraction(1000, 100_000) == 0.01
    assert participation_fraction(1000, None) is None
    assert participation_fraction(0, 100_000) is None


def test_participation_ceiling_shares():
    assert participation_ceiling_shares(1_000_000, HARD_LIMIT_PARTICIPATION) == 100_000
    assert participation_ceiling_shares(None, 0.1) is None


def test_market_impact_sqrt_law_monotonic():
    small = market_impact_bps(0.01)
    big = market_impact_bps(0.10)
    assert small is not None and big is not None
    assert big > small  # more participation -> more impact
    # sqrt-law sanity: impact ~ vol*sqrt(part)*1e4
    assert math.isclose(market_impact_bps(0.04, 0.02), 0.02 * math.sqrt(0.04) * 10000, rel_tol=1e-6)


def test_market_impact_degraded():
    assert market_impact_bps(None) is None


def test_edge_net_of_scale_penalizes_size():
    small = edge_net_of_scale(8.0, part_frac=0.005)
    large = edge_net_of_scale(8.0, part_frac=0.09)
    assert large["net_of_scale_score"] < small["net_of_scale_score"]
    assert small["scale_known"] is True


def test_edge_net_of_scale_unknown_when_no_adv():
    e = edge_net_of_scale(8.0, part_frac=None)
    assert e["scale_known"] is False
    assert e["scale_penalty"] == 0.0


# -- classification ---------------------------------------------------------
def test_classify_unknown_when_no_participation():
    assert (
        classify_capacity(
            net_of_scale_score=7, net_after_cost=7, part_frac=None,
            impact_bps=None, spread_bps=None,
        )
        == CAP_UNKNOWN
    )


def test_classify_scales_clean():
    cls = classify_capacity(
        net_of_scale_score=7.5, net_after_cost=7.5,
        part_frac=TARGET_PARTICIPATION * 0.5, impact_bps=15, spread_bps=8,
    )
    assert cls == CAP_SCALES_CLEAN


def test_classify_good_but_cannot_scale():
    # Strong edge but order is past the hard refuse line.
    cls = classify_capacity(
        net_of_scale_score=6.5, net_after_cost=7.5,
        part_frac=HARD_LIMIT_PARTICIPATION + 0.02, impact_bps=40, spread_bps=10,
    )
    assert cls == CAP_GOOD_CANNOT_SCALE


def test_classify_pilot_only():
    # Just above the clean target, below the hard refuse line: only pilot fits.
    cls = classify_capacity(
        net_of_scale_score=6.0, net_after_cost=6.5,
        part_frac=TARGET_PARTICIPATION + 0.005, impact_bps=30, spread_bps=10,
    )
    assert cls == CAP_PILOT_ONLY


def test_classify_weak_execution():
    cls = classify_capacity(
        net_of_scale_score=6.0, net_after_cost=6.5,
        part_frac=TARGET_PARTICIPATION * 0.5, impact_bps=20, spread_bps=40,
    )
    assert cls == CAP_SCALE_WEAK_EXEC


def test_classify_low_capacity():
    cls = classify_capacity(
        net_of_scale_score=3.0, net_after_cost=4.0,
        part_frac=0.08, impact_bps=70, spread_bps=60,
    )
    assert cls == CAP_LOW_CAPACITY


# -- assess / chip / sleeve -------------------------------------------------
def test_assess_capacity_degraded_without_adv():
    a = assess_capacity(ticker="aapl", size_shares=1000, adv=None)
    assert a["degraded"] is True
    assert a["classification"] == CAP_UNKNOWN
    assert a["participation_pct"] is None
    assert a["may_authorize_deploy"] is False


def test_assess_capacity_clean_liquid_name():
    a = assess_capacity(ticker="SPY", size_shares=1000, adv=50_000_000, raw_score=7.5, spread_bps=2)
    assert a["classification"] == CAP_SCALES_CLEAN
    assert a["participation_pct"] < 1.0
    assert a["headroom_to_clean_shares"] > 0


def test_chip_is_downgrade_only_and_never_green():
    chip = build_capacity_chip(ticker="XYZ", size_shares=50_000, adv=200_000, spread_bps=60)
    assert chip["downgrade_only"] is True
    assert chip["tone"] in {"neutral", "caution", "muted"}  # never a deploy/green tone


def test_sleeve_capacity_ranks_headroom():
    out = build_sleeve_capacity(
        [
            {"name": "liquid", "size_shares": 1000, "adv": 10_000_000},
            {"name": "thin", "size_shares": 9000, "adv": 100_000},
        ]
    )
    assert out["best_funded_sleeve"] == "liquid"
    assert out["most_constrained_sleeve"] == "thin"


# -- authority --------------------------------------------------------------
def test_context_payload_is_research_only():
    from src.services.signal_provenance import assert_no_deploy_from_signals
    from src.services.surface_authority import AUTHORITY_RESEARCH

    ctx = build_capacity_context(ticker="AAPL", size_shares=1000, adv=2_000_000)
    assert ctx["authority_ceiling"] == AUTHORITY_RESEARCH
    assert ctx["provenance"]["deploy_from_signal_alone"] is False
    assert ctx["provenance"]["page_gate_required"] is True
    assert ctx["provenance"].get("downgrade_only") is True
    assert_no_deploy_from_signals([ctx])
