"""Drawdown sizer — blocked when research_only / confirm-only."""

from src.services.drawdown_sizer import (
    MODE_BLOCKED,
    MODE_FULL,
    MODE_MINIMAL,
    MODE_REDUCED,
    evaluate_drawdown_sizing,
)


def test_blocked_on_research_only():
    r = evaluate_drawdown_sizing(current_dd_pct=5, research_only=True)
    assert r["sizing_mode"] == MODE_BLOCKED
    assert r["has_sizing_authority"] is False


def test_blocked_on_confirm_only():
    r = evaluate_drawdown_sizing(current_dd_pct=5, confirm_only=True)
    assert r["sizing_mode"] == MODE_BLOCKED


def test_full_within_budget():
    r = evaluate_drawdown_sizing(current_dd_pct=5, dd_budget_pct=15)
    assert r["sizing_mode"] == MODE_FULL
    assert r["size_multiplier"] == 1.0


def test_reduced_under_pressure():
    r = evaluate_drawdown_sizing(current_dd_pct=12, dd_budget_pct=15)
    assert r["sizing_mode"] == MODE_REDUCED


def test_minimal_at_budget():
    r = evaluate_drawdown_sizing(current_dd_pct=16, dd_budget_pct=15)
    assert r["sizing_mode"] == MODE_MINIMAL
