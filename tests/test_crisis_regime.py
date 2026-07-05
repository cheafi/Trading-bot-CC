"""Tests for 《乱世华尔街》crisis regime classification."""

from src.services.crisis_regime import (
    classify_crisis_state,
    evaluate_crisis_regime,
    tags_for_playbook_row,
)


def test_calm_when_low_vix():
    state = classify_crisis_state(vix=16, breadth=55, should_trade=True)
    assert state == "calm"
    ev = evaluate_crisis_regime(vix=16, breadth=55, should_trade=True)
    assert ev["level"] == "normal"
    assert ev["deploy_blocked"] is False


def test_cascade_on_extreme_vix():
    state = classify_crisis_state(vix=36, tradeability="NO_TRADE", should_trade=False)
    assert state == "cascade"
    ev = evaluate_crisis_regime(vix=36, tradeability="NO_TRADE", should_trade=False)
    assert ev["deploy_blocked"] is True
    assert ev["capital_preservation_priority"] is True


def test_fragile_elevated_level():
    ev = evaluate_crisis_regime(vix=23, breadth=36, should_trade=True)
    assert ev["state"] == "fragile"
    assert ev["level"] == "elevated"


def test_playbook_tags_preservation_in_crisis():
    tags = tags_for_playbook_row(
        {"vix": 32, "should_trade": False},
        tradeability="WAIT",
    )
    assert tags["capital_preservation_priority"] is True
    assert tags["attack_permission"] is False
    assert "regime_fit" in tags
