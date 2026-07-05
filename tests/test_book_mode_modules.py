"""Tests for book-mode stubs: 巴芒 / Turtle / 乱世."""

from __future__ import annotations

from src.services.crisis_regime import crisis_strip_for_today, evaluate_crisis_regime
from src.services.surface_authority import resolve_authority_for_ui_tab
from src.services.turtle_system import evaluate_turtle_setup
from src.services.value_investing import evaluate_value_posture


def test_value_posture_patience_on_wait():
    v = evaluate_value_posture({"score": 8, "thesis_conf": 0.8}, tradeability="WAIT")
    assert v["action_hint"] == "WATCH"
    assert any("patience" in lb.lower() for lb in v["labels"])


def test_turtle_requires_stop_for_entry():
    row = {
        "structure": {"above_sma20": True, "above_sma50": True, "volume_ratio": 1.3},
        "stop": 100.0,
    }
    t = evaluate_turtle_setup(row, tradeability="TRADE")
    assert t["entry_ok"] is True


def test_crisis_blocks_high_vix():
    c = evaluate_crisis_regime(tradeability="TRADE", vix=30, should_trade=True)
    assert c["level"] == "crisis"
    assert c["deploy_blocked"] is True


def test_crisis_strip_for_today_payload():
    strip = crisis_strip_for_today(
        {"tradeability": "WAIT", "vix": 24, "breadth": 40, "should_trade": False},
        {"honest_tradeability": "WAIT", "macro_regime": "Hostile"},
    )
    assert strip["deploy_blocked"] is True
    assert "乱世" in strip["banner"] or "preservation" in strip["banner"].lower()


def test_ui_tab_alias_playbook():
    auth = resolve_authority_for_ui_tab(
        "signals",
        tradeability="TRADE",
        deployable_count=2,
        ibkr_connected=True,
    )
    assert auth["tab"] == "playbook"
    assert auth["surface"] == "Playbook"
