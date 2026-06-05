"""Strategy allocator — hints only."""

from src.services.strategy_allocator import (
    build_allocator_context,
    build_sleeve_budgets,
    routing_suggestion,
)


def test_sleeves_do_not_control_capital():
    sleeves = build_sleeve_budgets()
    assert all(s.get("controls_capital") is False for s in sleeves)


def test_routing_strongest_weakest():
    route = routing_suggestion(build_sleeve_budgets())
    assert route["strongest"] is not None
    assert route["weakest"] is not None
    assert "not a trade route" in route["suggestion"]


def test_allocator_context_no_deploy():
    ctx = build_allocator_context()
    assert ctx["deploy_from_allocator_alone"] is False
    assert ctx["controls_capital"] is False
