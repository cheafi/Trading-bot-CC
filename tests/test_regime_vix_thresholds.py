"""Regime engine — VIX crisis threshold at 28."""

from __future__ import annotations

from src.services.regime_engine import (
    VIX_CRISIS_THRESHOLD,
    build_regime_stack,
    derive_tradeability,
    explain_regime_conflict,
)
from src.services.system_truth import classify_volatility_state


def test_no_crisis_below_28():
    assert classify_volatility_state(27.9) != "crisis"
    assert classify_volatility_state(27.9) == "stress"


def test_crisis_at_or_above_28():
    assert classify_volatility_state(28.0) == "crisis"
    assert classify_volatility_state(35.0) == "crisis"


def test_vix_crisis_threshold_constant():
    assert VIX_CRISIS_THRESHOLD == 28.0


def test_derive_tradeability_no_trade_on_crisis_vol():
    tb = derive_tradeability(
        should_trade=True,
        tradeability="TRADE",
        vix=30.0,
        breadth=55.0,
    )
    assert tb == "NO_TRADE"


def test_regime_stack_not_deploy_authority():
    stack = build_regime_stack(vix=30, tradeability="WAIT")
    assert stack["may_authorize_deploy"] is False
    assert stack["crisis"] is True


def test_explain_regime_conflict_on_vol_downgrade():
    line = explain_regime_conflict(
        tradeability="TRADE",
        honest_tradeability="SELECTIVE",
        vix=30.0,
        breadth=50.0,
    )
    assert "conflict" in line.lower()
    assert "not deploy" in line.lower()
