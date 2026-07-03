"""Volatility monitor label — normal calm is not Crisis Monitor."""

from __future__ import annotations

from src.services.crisis_regime import evaluate_crisis_regime


def test_normal_volatility_uses_volatility_monitor_label():
    ev = evaluate_crisis_regime(vix=16, breadth=55, should_trade=True)
    assert ev["level"] == "normal"
    assert ev["monitor_label"] == "Volatility Monitor"


def test_crisis_level_uses_crisis_monitor_label():
    ev = evaluate_crisis_regime(vix=36, tradeability="NO_TRADE", should_trade=False)
    assert ev["monitor_label"] == "Crisis Monitor"
