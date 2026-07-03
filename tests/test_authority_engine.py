"""Authority engine — deploy block rules and engine resolver."""

from __future__ import annotations

from src.services.authority_engine import (
    pilot_sizing_allowed,
    primary_operator_state,
    resolve_engine_state,
)


def test_engine_conflict_returns_unknown():
    state = resolve_engine_state(
        {"execution_readiness": {"engine_running": True}},
        {"engine_running": False},
    )
    assert state == "unknown"


def test_engine_single_on_signal():
    state = resolve_engine_state(
        {"execution_readiness": {"engine_running": True}},
        {"engine_running": True},
    )
    assert state == "on"


def test_pilot_sizing_blocked_when_deploy_off():
    assert not pilot_sizing_allowed(
        {
            "deploy_authority": False,
            "broker_freshness": "ready",
            "brief_freshness": "fresh",
            "market_data_freshness": "fresh",
            "ranked_board_freshness": "fresh",
        }
    )


def test_primary_monitor_only_when_blocked():
    posture = primary_operator_state({"deploy_authority": False, "regime_state": "TRADE"})
    assert posture["now"] == "MONITOR ONLY · Deploy blocked"
