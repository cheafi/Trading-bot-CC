"""Overfit guard — caps labels at promising/learning."""

from __future__ import annotations

from src.services.overfit_guard import assess_overfit_risk


def test_high_overfit_caps_learning():
    out = assess_overfit_risk(
        sample_size=4,
        filter_count=6,
        cost_erases_edge=True,
    )
    assert out["overfit_risk"] == "high"
    assert out["label_cap"] == "learning"
    assert out["allow_green_ui"] is False
    assert out["may_authorize_deploy"] is False


def test_low_overfit_allows_validated_when_n_ok():
    out = assess_overfit_risk(
        sample_size=25,
        filter_count=2,
        walk_forward_stable=True,
    )
    assert out["overfit_risk"] == "low"
    assert out["allow_validated_label"] is True


def test_medium_overfit_caps_promising():
    out = assess_overfit_risk(
        sample_size=10,
        filter_count=5,
    )
    assert out["overfit_risk"] in ("medium", "high")
    assert out["label_cap"] in ("promising", "learning")
