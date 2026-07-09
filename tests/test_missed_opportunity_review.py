"""Missed opportunity review — never auto-loosen."""

from __future__ import annotations

from src.services.missed_opportunity_review import (
    classify_missed_opportunity,
    review_missed_opportunities,
)


def test_authority_block_classification():
    out = classify_missed_opportunity(
        {"ticker": "NVDA"},
        truth={"deploy_authority": False, "execution_readiness": {"broker_connected": True}},
    )
    assert out["classification"] == "authority_block"
    assert out["auto_loosen_forbidden"] is True
    assert out["may_authorize_deploy"] is False


def test_broker_offline_classification():
    out = classify_missed_opportunity(
        {"ticker": "MSFT"},
        truth={
            "deploy_authority": True,
            "execution_readiness": {"broker_connected": False},
        },
    )
    assert out["classification"] == "broker_offline"


def test_review_never_auto_loosen():
    out = review_missed_opportunities(
        near_miss_rows=[{"ticker": "AAPL", "forward_r_5d": 0.8}],
        truth={
            "deploy_authority": False,
            "deploy_qualified_count": 0,
            "execution_readiness": {"broker_connected": True},
        },
        forward_outcomes=[{"ticker": "AAPL", "forward_r": 0.8}],
    )
    assert out["never_auto_loosen"] is True
    assert out["auto_loosen_forbidden"] is True
    assert out["may_authorize_deploy"] is False
