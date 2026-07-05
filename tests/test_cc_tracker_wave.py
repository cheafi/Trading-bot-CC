"""CC tracker wave — authority preservation and Tier-1 bundle correctness."""

from __future__ import annotations

from src.services.cc_tracker_wave import (
    TRACKER_FEATURE_REGISTRY,
    TIER_1_IDS,
    assert_tracker_wave_no_deploy,
    build_tracker_wave_context,
    build_tier1_live_bundle,
    get_feature,
)
from src.services.signal_provenance import (
    SIGNAL_CC_TRACKER_WAVE,
    SIGNAL_SAFE_AUTOMATION,
    may_authorize_deploy,
)


def test_registry_every_feature_denies_deploy():
    for feat in TRACKER_FEATURE_REGISTRY:
        assert feat["may_authorize_deploy"] is False
        assert feat["may_override_board_gate"] is False
        assert feat.get("authority_level")
        assert feat.get("can_influence")
        assert feat.get("cannot_influence")


def test_tier1_ids_in_registry():
    for fid in TIER_1_IDS:
        assert get_feature(fid) is not None


def test_tracker_wave_envelope_no_deploy():
    payload = build_tracker_wave_context(tradeability="WAIT", degraded=True)
    assert payload["may_authorize_deploy"] is False
    assert may_authorize_deploy(SIGNAL_CC_TRACKER_WAVE) is False
    assert payload["tier1"]["may_authorize_deploy"] is False
    assert_tracker_wave_no_deploy(payload)


def test_tier1_live_bundle_degraded_honesty():
    bundle = build_tier1_live_bundle(degraded=True, ibkr_connected=False)
    assert bundle["degraded"] is True
    assert bundle["may_authorize_deploy"] is False
    assert any("MOCK" in line or "DEGRADED" in line for line in bundle["strip_lines"])


def test_tier1_execution_live_sample_label():
    exec_a = {
        "orders_sampled": 8,
        "sample_state": "live_sample",
        "fill_quality": {"status": "acceptable"},
    }
    bundle = build_tier1_live_bundle(
        execution_analytics=exec_a,
        ibkr_connected=True,
        degraded=False,
    )
    assert bundle["tier1_status"]["execution_analytics"]["sample_state"] == "live_sample"
    assert bundle["may_authorize_deploy"] is False


def test_safe_automation_signal_never_deploys():
    assert may_authorize_deploy(SIGNAL_SAFE_AUTOMATION) is False
