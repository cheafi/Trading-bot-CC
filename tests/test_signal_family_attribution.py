"""Signal family attribution — validation gates and unvalidated defaults."""

from __future__ import annotations

from src.services.signal_family_attribution import (
    MIN_VALIDATED_SAMPLE,
    attribute_family,
    attribute_families_for_row,
    resolve_family_status,
)


def test_ai_narrative_starts_unvalidated():
    fam = attribute_family("ai_narrative", row={"ai_hint": "bullish"}, sample_size=0)
    assert fam["status"] == "unvalidated"
    assert fam["may_authorize_deploy"] is False


def test_options_flow_unvalidated_without_live_calibration():
    fam = attribute_family(
        "options_flow",
        row={"options_flow": True},
        sample_size=30,
        forward_r_mean=0.5,
        live_calibration=False,
    )
    assert fam["status"] != "validated"


def test_sample_size_required_before_validated():
    status = resolve_family_status(
        family="setup_quality",
        sample_size=MIN_VALIDATED_SAMPLE - 1,
        forward_r_mean=0.8,
    )
    assert status != "validated"
    status_ok = resolve_family_status(
        family="setup_quality",
        sample_size=MIN_VALIDATED_SAMPLE,
        forward_r_mean=0.5,
    )
    assert status_ok == "validated"


def test_expired_brief_excludes_setup_features():
    fams = attribute_families_for_row(
        {"ticker": "AAPL", "score": 8.0, "timing_conf": 0.7},
        truth={"brief_expired": True, "brief_freshness": "expired"},
    )
    families = [f["family"] for f in fams]
    assert "timing" not in families or all(
        f["status"] == "unvalidated" for f in fams if f["family"] == "timing"
    )
