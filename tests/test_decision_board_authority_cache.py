"""Authority cache refresh — deploy_open must never be served stale."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.services.cc_state import attach_system_state
from src.services.decision_board_service import build_decision_board
from tests.test_decision_board_service import _base_payload


def _deploy_open_payload() -> Dict[str, Any]:
    payload = _base_payload(
        tradeability="TRADE",
        deployable_count=2,
        watch_qualified_count=3,
        authority_overrides={
            "gates_active": False,
            "authority_level": "deploy",
        },
    )
    payload["decision_authority"]["gates_active"] = False
    payload["decision_authority"]["authority_level"] = "deploy"
    payload["cc_state"]["board_decision_state"]["state"] = "DEPLOY"
    payload["decision_model"] = {"honest_tradeability": "TRADE"}
    attach_system_state(payload)
    board = build_decision_board(payload, source="today")
    assert board["deploy_open"] is True
    return payload


def _mock_request() -> MagicMock:
    req = MagicMock()
    req.app.state = SimpleNamespace()
    return req


@pytest.mark.anyio
async def test_refresh_today_authority_closes_deploy_on_breaker():
    from src.api.routers import decision as decision_router

    payload = _deploy_open_payload()
    regime = SimpleNamespace(
        should_trade=True,
        regime="RISK_ON",
        no_trade_reason="",
    )
    ibkr = MagicMock()
    ibkr.status.return_value = {"connected": True, "session_usable": True}

    with (
        patch.object(decision_router, "_fetch_regime", return_value=regime),
        patch.object(
            decision_router,
            "_board_ops_snapshot",
            return_value={"running": True, "breaker": True},
        ),
        patch(
            "src.services.ibkr_service.get_ibkr_service",
            return_value=ibkr,
        ),
    ):
        refreshed = await decision_router._refresh_today_authority(
            _mock_request(), payload
        )

    assert refreshed["decision_board"]["deploy_open"] is False
    assert refreshed["system_state"]["deploy_open"] is False
    assert refreshed["decision_authority"]["gates"]["exec_blocked"] is True


@pytest.mark.anyio
async def test_refresh_today_authority_closes_deploy_on_regime_wait():
    from src.api.routers import decision as decision_router

    payload = _deploy_open_payload()
    regime = SimpleNamespace(
        should_trade=False,
        regime="NEUTRAL",
        no_trade_reason="",
    )
    ibkr = MagicMock()
    ibkr.status.return_value = {"connected": True, "session_usable": True}

    with (
        patch.object(decision_router, "_fetch_regime", return_value=regime),
        patch.object(
            decision_router,
            "_board_ops_snapshot",
            return_value={"running": True, "breaker": False},
        ),
        patch(
            "src.services.ibkr_service.get_ibkr_service",
            return_value=ibkr,
        ),
    ):
        refreshed = await decision_router._refresh_today_authority(
            _mock_request(), payload
        )

    assert refreshed["market_regime"]["tradeability"] == "WAIT"
    assert refreshed["market_regime"]["should_trade"] is False
    assert refreshed["decision_board"]["deploy_open"] is False
    assert refreshed["system_state"]["deploy_open"] is False
    assert refreshed["decision_authority"]["gates"]["regime_wait"] is True


@pytest.mark.anyio
async def test_board_endpoint_recomputes_not_cached():
    from src.api.routers import decision as decision_router

    payload = _deploy_open_payload()
    regime = SimpleNamespace(
        should_trade=True,
        regime="RISK_ON",
        no_trade_reason="",
    )
    ibkr = MagicMock()
    ibkr.status.return_value = {"connected": True, "session_usable": True}
    ops_sequence = [
        {"running": True, "breaker": False},
        {"running": True, "breaker": False},
        {"running": True, "breaker": True},
        {"running": True, "breaker": True},
    ]

    with (
        patch.object(
            decision_router,
            "_today_payload_for_board",
            return_value=payload,
        ),
        patch.object(decision_router, "_fetch_regime", return_value=regime),
        patch.object(
            decision_router,
            "_board_ops_snapshot",
            side_effect=ops_sequence,
        ),
        patch(
            "src.services.ibkr_service.get_ibkr_service",
            return_value=ibkr,
        ),
    ):
        req = _mock_request()
        first = await decision_router.decision_board(req)
        second = await decision_router.decision_board(req)

    assert first["deploy_open"] is True
    assert second["deploy_open"] is False
    assert not hasattr(decision_router, "_board_cache")
