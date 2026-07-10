"""Threshold registry — SSOT and policy guards."""

from __future__ import annotations

from src.services.threshold_registry import (
    THRESHOLD_REGISTRY,
    get_threshold,
    is_risk_reducing,
    list_thresholds,
    registry_summary,
    validate_proposed_value,
)


def test_all_thresholds_block_auto_loosen():
    for key, defn in THRESHOLD_REGISTRY.items():
        d = defn.to_dict()
        assert d["can_auto_loosen"] is False, key


def test_deploy_thresholds_require_human_approval():
    for key in ("playbook.deploy_score_min", "playbook.deploy_rr_min", "capital.max_position_risk_pct"):
        defn = get_threshold(key)
        assert defn is not None
        assert defn.requires_human_approval is True


def test_tighten_must_be_risk_reducing():
    assert is_risk_reducing("playbook.deploy_score_min", 80.0, current_value=72.0)
    assert not is_risk_reducing("playbook.deploy_score_min", 65.0, current_value=72.0)


def test_validate_loosen_review_never_auto():
    ok, msg = validate_proposed_value("playbook.deploy_score_min", 65.0, proposal_type="loosen_review")
    assert ok is True
    assert "human approval" in msg


def test_registry_has_sixteen_thresholds():
    assert len(THRESHOLD_REGISTRY) == 16


def test_all_thresholds_have_domain_and_authority():
    for key, defn in THRESHOLD_REGISTRY.items():
        assert defn.domain in ("playbook", "opportunity", "alpha", "capital", "discovery", "strategy", "governor"), key
        d = defn.to_dict()
        assert d["authority_effect"] == "none", key
        assert d["may_authorize_deploy"] is False, key


def test_registry_summary_authority():
    s = registry_summary()
    assert s["can_auto_loosen_globally"] is False
    assert s["may_authorize_deploy"] is False
    assert s["authority_effect"] == "none"
    assert len(list_thresholds()) == len(THRESHOLD_REGISTRY)
