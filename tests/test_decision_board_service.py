"""DecisionBoardService — identical deploy_open across surfaces."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.services.cc_state import attach_system_state, build_cc_state
from src.services.decision_board_service import (
    attach_decision_board,
    build_decision_board,
    decision_board_hash,
)
from src.services.decision_truth_model import build_decision_authority
from src.services.today_insights import build_unlock_deploy


def _base_payload(**overrides: Any) -> Dict[str, Any]:
    tradeability = overrides.pop("tradeability", "WAIT")
    should_trade = overrides.pop("should_trade", True)
    deployable_count = overrides.pop("deployable_count", 0)
    watch_qualified = overrides.pop("watch_qualified_count", 0)
    scanner_degraded = overrides.pop("scanner_degraded", False)
    execution_readiness = overrides.pop(
        "execution_readiness",
        {
            "broker_connected": True,
            "trade_handoff_ready": True,
            "engine_running": True,
        },
    )
    authority_overrides = overrides.pop("authority_overrides", {})
    da = build_decision_authority(
        tradeability=tradeability,
        should_trade=should_trade,
        scanner_degraded=scanner_degraded,
        **{k: v for k, v in authority_overrides.items() if k in (
            "data_stale",
            "fallback_brief",
            "broker_offline",
            "engine_off",
            "exec_blocked",
            "scanner_loading",
        )},
    )
    for key, val in authority_overrides.items():
        if key not in (
            "data_stale",
            "fallback_brief",
            "broker_offline",
            "engine_off",
            "exec_blocked",
            "scanner_loading",
        ):
            da[key] = val
    payload: Dict[str, Any] = {
        "market_regime": {
            "label": "NEUTRAL",
            "trend": "UPTREND",
            "tradeability": tradeability,
            "should_trade": should_trade,
            "vix": 18.0,
            "breadth": 55,
        },
        "decision_authority": da,
        "execution_readiness": execution_readiness,
        "filter_funnel": {
            "watch_qualified_setups": watch_qualified,
            "deploy_qualified_setups": deployable_count,
            "execution_ready_setups": deployable_count,
        },
        "unlock_deploy": build_unlock_deploy(
            tradeability=tradeability,
            should_trade=should_trade,
            watch_qualified_count=watch_qualified,
            deployable_count=deployable_count,
            scanner_degraded=scanner_degraded,
            execution_readiness=execution_readiness,
        ),
        "trust": {"stale": scanner_degraded, "as_of": "2026-08-25T08:00:00Z"},
        "generated_at": "2026-08-25T08:00:00Z",
        "top_5": [],
    }
    payload["cc_state"] = build_cc_state(
        tradeability=tradeability,
        should_trade=should_trade,
        decision_authority=da,
        execution_readiness=execution_readiness,
        trust=payload["trust"],
    )
    attach_system_state(payload)
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "scenario,kwargs,expect_open",
    [
        ("wait", {"tradeability": "WAIT"}, False),
        ("no_trade", {"tradeability": "NO_TRADE", "should_trade": False}, False),
        (
            "stale",
            {
                "tradeability": "TRADE",
                "deployable_count": 2,
                "watch_qualified_count": 3,
                "scanner_degraded": True,
                "authority_overrides": {"data_stale": True},
            },
            False,
        ),
        (
            "broker_offline",
            {
                "tradeability": "TRADE",
                "deployable_count": 2,
                "watch_qualified_count": 3,
                "authority_overrides": {"broker_offline": True},
                "execution_readiness": {
                    "broker_connected": False,
                    "trade_handoff_ready": False,
                    "engine_running": True,
                },
            },
            False,
        ),
        (
            "fallback_brief",
            {
                "tradeability": "WAIT",
                "authority_overrides": {"fallback_brief": True},
            },
            False,
        ),
        (
            "deploy_open",
            {
                "tradeability": "TRADE",
                "deployable_count": 2,
                "watch_qualified_count": 3,
                "authority_overrides": {
                    "gates_active": False,
                    "authority_level": "deploy",
                },
            },
            True,
        ),
    ],
)
def test_deploy_open_gates(scenario: str, kwargs: dict, expect_open: bool):
    payload = _base_payload(**kwargs)
    if expect_open:
        payload["decision_authority"]["gates_active"] = False
        payload["decision_authority"]["authority_level"] = "deploy"
        payload["cc_state"]["board_decision_state"]["state"] = "DEPLOY"
        attach_system_state(payload)

    board = build_decision_board(payload, source="today")
    assert board["deploy_open"] is expect_open, scenario
    assert board["system_state"]["deploy_open"] is expect_open
    assert len(board["gate_reasons"]) >= (0 if expect_open else 1)


def test_identical_deploy_open_across_surfaces():
    payload = _base_payload(
        tradeability="SELECTIVE",
        deployable_count=1,
        watch_qualified_count=2,
        authority_overrides={"gates_active": False, "authority_level": "deploy"},
    )
    payload["decision_authority"]["authority_level"] = "deploy"
    payload["cc_state"]["board_decision_state"]["state"] = "DEPLOY"
    attach_system_state(payload)

    today_board = build_decision_board(payload, source="today")
    playbook_payload = {
        **payload,
        "best_action": {"tradeability": "SELECTIVE"},
        "opportunities": [{"ticker": "AAA", "execution_ready": True}],
    }
    playbook_board = build_decision_board(playbook_payload, source="playbook")
    header_board = build_decision_board(payload, source="header")

    assert today_board["deploy_open"] == playbook_board["deploy_open"]
    assert today_board["deploy_open"] == header_board["deploy_open"]
    assert today_board["system_state"]["deploy_open"] == playbook_board["system_state"]["deploy_open"]


def test_attach_decision_board_syncs_system_state():
    payload = _base_payload(tradeability="WAIT")
    attach_decision_board(payload, source="today")
    assert payload["decision_board"]["deploy_open"] is False
    assert payload["system_state"]["deploy_open"] is False
    assert payload["decision_board_hash"] == payload["decision_board"]["decision_board_hash"]


def test_decision_board_hash_changes_with_deploy_open():
    closed = build_decision_board(_base_payload(tradeability="WAIT"), source="board")
    open_payload = _base_payload(
        tradeability="TRADE",
        deployable_count=2,
        watch_qualified_count=3,
        authority_overrides={"gates_active": False, "authority_level": "deploy"},
    )
    open_payload["decision_authority"]["authority_level"] = "deploy"
    open_payload["cc_state"]["board_decision_state"]["state"] = "DEPLOY"
    attach_system_state(open_payload)
    opened = build_decision_board(open_payload, source="board")
    assert decision_board_hash(closed) != decision_board_hash(opened)


def test_board_includes_unlock_deploy_and_regime():
    payload = _base_payload(tradeability="WAIT", watch_qualified_count=1)
    board = build_decision_board(payload, source="today")
    assert board["unlock_deploy"]["unlocked"] is False
    assert board["regime"]["tradeability"] == "WAIT"
    assert board["deploy_authority"]["gates_active"] is True


def test_board_includes_gate_snapshot_and_rows():
    payload = _base_payload(tradeability="WAIT")
    payload["top_5"] = [{"ticker": "AAPL", "rank": 1, "action": "WATCH"}]
    board = build_decision_board(payload, source="today")
    assert "gate_snapshot" in board
    assert board["gate_snapshot"]["deploy_open"] is False
    assert len(board["board_rows"]) == 1
    assert board["board_rows"][0]["attribution_root_ref"].startswith("attr-root-")
    assert board["board_rows"][0]["decision_id"].startswith("dec-AAPL-")
