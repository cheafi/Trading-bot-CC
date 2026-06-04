"""Event noise filter unit tests."""

from src.services.event_noise_filter import (
    IMPACT_FRAMING_NOISE,
    TIER_D_RUMOR,
    build_event_risk_context,
    cluster_events,
    frame_impact,
)


def test_rumor_filtered_noise():
    framing, _ = frame_impact(
        taxonomy="social_noise",
        credibility_tier=TIER_D_RUMOR,
    )
    assert framing == IMPACT_FRAMING_NOISE


def test_cluster_dedup():
    events = [
        {"title": "Foo", "source": "Bar", "credibility_tier": "tier_b_secondary"},
        {"title": "Foo", "source": "Bar", "credibility_tier": "tier_a_primary"},
    ]
    out = cluster_events(events)
    assert len(out) == 1


def test_build_events_mock():
    ctx = build_event_risk_context("TSLA")
    assert ctx["downgrade_only"] is True
