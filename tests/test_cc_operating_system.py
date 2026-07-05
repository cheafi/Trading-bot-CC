"""CC operating system — module aggregation and authority."""

from __future__ import annotations

from src.services.cc_capital_control import build_capital_control_context
from src.services.cc_operating_system import (
    TOP_10_BUILD_PRIORITY,
    assert_cc_os_no_deploy,
    build_cc_operating_system_context,
)
from src.services.cc_opportunity_engine import evaluate_opportunity_quality
from src.services.cc_regime_engine import build_advanced_regime_stack
from src.services.signal_provenance import (
    SIGNAL_CC_OPERATING_SYSTEM,
    may_authorize_deploy,
)


def test_cc_os_envelope_no_deploy():
    payload = build_cc_operating_system_context(tradeability="WAIT", degraded=True)
    assert payload["may_authorize_deploy"] is False
    assert may_authorize_deploy(SIGNAL_CC_OPERATING_SYSTEM) is False
    assert_cc_os_no_deploy(payload)


def test_cc_os_modules_present():
    payload = build_cc_operating_system_context(
        tradeability="SELECTIVE",
        vix=18.0,
        breadth=52.0,
        near_miss=[{"ticker": "AAPL", "gaps": ["volume"], "score": 7.5}],
        top5=[{"ticker": "MSFT", "score": 8.0, "action": "WATCH"}],
    )
    mods = payload.get("modules") or {}
    assert "regime_index" in mods
    assert "opportunity_quality" in mods
    assert "capital_control" in mods
    assert "execution" in mods
    assert payload.get("operator_strip")


def test_regime_stack_monitor_only():
    stack = build_advanced_regime_stack(vix=30, breadth=35, tradeability="WAIT")
    assert stack["may_authorize_deploy"] is False
    assert "not deploy" in stack.get("strip_line", "").lower()


def test_opportunity_quality_never_overrides_wait():
    row = evaluate_opportunity_quality(
        {"ticker": "X", "score": 9, "extended": True, "risk_reward": 1.2},
        tradeability="WAIT",
    )
    assert row["may_authorize_deploy"] is False
    assert row["may_override_wait"] is False


def test_capital_control_blocked_on_stale():
    ctx = build_capital_control_context(fallback_or_stale=True)
    assert ctx["may_authorize_deploy"] is False
    assert ctx["combined_multiplier"] == 0.0


def test_top_10_priority_list():
    assert len(TOP_10_BUILD_PRIORITY) == 10
    assert "cost_adjusted_ranker" in TOP_10_BUILD_PRIORITY
