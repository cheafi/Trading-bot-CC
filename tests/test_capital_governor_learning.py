"""Capital governor learning feedback — false deploy, broker offline, too conservative."""

from __future__ import annotations

from src.services.capital_allocation_governor import evaluate_capital_allocation


def test_false_deploy_reduces_risk():
    base = evaluate_capital_allocation(
        truth={
            "deploy_authority": True,
            "deploy_qualified_count": 2,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
        },
        false_deploy_rate=0.0,
        sample_size=20,
    )
    high = evaluate_capital_allocation(
        truth={
            "deploy_authority": True,
            "deploy_qualified_count": 2,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
        },
        false_deploy_rate=0.3,
        sample_size=20,
    )
    assert high["max_new_risk_pct"] <= base["max_new_risk_pct"]
    assert high["capital_mode"] == "pilot_review"
    assert high["risk_mode_adjustment"] == "tighten"
    assert high["learning_feedback"]["never_auto_loosen"] is True


def test_broker_offline_blocks():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": False,
            "execution_readiness": {"broker_connected": False},
        },
    )
    assert out["capital_mode"] in ("no_capital", "paper_only")
    assert out["may_authorize_deploy"] is False


def test_too_conservative_suggests_review_only():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": True,
            "deploy_qualified_count": 2,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
        },
        no_edge_quality="too_conservative",
        sample_size=15,
    )
    assert out["requires_human_review"] is True
    assert out["learning_adjustment_reason"] is not None
    assert "NO_EDGE_TOO_CONSERVATIVE" in out["learning_adjustment_reason"]
    assert out["deploy_allowed"] is True
    assert out["learning_feedback"]["never_auto_loosen"] is True


def test_harmful_signal_tightens_not_loosens():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": True,
            "deploy_qualified_count": 2,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
        },
        signal_confidence="harmful",
        sample_size=25,
    )
    assert out["max_new_risk_pct"] <= 0.15
    assert out["requires_human_review"] is True
