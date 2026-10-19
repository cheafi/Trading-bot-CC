"""HTTP integration for /broker/order idempotency contract."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.brokers.base import OrderResult, OrderSide, OrderStatus, OrderType
from src.core.execution_gateway import ExecutionGateway
from src.core.execution_idempotency import IdempotencyStore
from src.engines.broker_reconciliation import BrokerReconciliationEngine


def _sensitive_client(monkeypatch, tmp_path):
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    api_key = "integration-test-secret-key"

    class _Settings:
        api_secret_key = api_key
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())
    monkeypatch.setattr(
        "src.core.execution_idempotency.execution_idempotency_path",
        lambda: tmp_path / "idem_http.json",
    )
    monkeypatch.setattr(
        "src.core.state_paths.order_reconciliation_snapshot_path",
        lambda: tmp_path / "ledger_http.json",
    )

    from fastapi.testclient import TestClient

    from src.api.main import app

    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "ledger_http.json")
    eng.mark_simulation_ready()
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )

    store = IdempotencyStore(path=tmp_path / "idem_http.json")
    gw = ExecutionGateway(idempotency=store)
    monkeypatch.setattr(
        "src.core.execution_gateway.execution_gateway", gw
    )
    return TestClient(app), api_key, gw, eng


class _MockManager:
    def __init__(self, *, fail: bool = False) -> None:
        from src.brokers.paper_broker import PaperBroker

        self.active_broker = PaperBroker()
        self.calls = 0
        self.fail = fail

    async def get_account(self):
        class _A:
            account_id = "PAPER"

        return _A()

    async def place_order(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("broker_down")
        ledger_oid = str(kwargs.get("ledger_order_id") or kwargs.get("ticker") or "")
        return OrderResult(
            success=True,
            order_id=ledger_oid or "broker-http-1",
            status=OrderStatus.FILLED,
            filled_qty=int(kwargs.get("quantity", 1)),
            avg_fill_price=100.0,
            message="ok",
        )


def test_broker_order_missing_idempotency_header_returns_422(
    monkeypatch, tmp_path
) -> None:
    client, api_key, _, _ = _sensitive_client(monkeypatch, tmp_path)
    manager = _MockManager()
    with patch(
        "src.brokers.broker_manager.get_broker_manager",
        new=AsyncMock(return_value=manager),
    ):
        resp = client.post(
            "/broker/order",
            params={"ticker": "SPY", "side": "buy", "quantity": 1},
            headers={"X-API-Key": api_key},
        )
    assert resp.status_code == 422


def test_broker_order_idempotency_conflict_returns_409(
    monkeypatch, tmp_path
) -> None:
    client, api_key, gw, _ = _sensitive_client(monkeypatch, tmp_path)
    manager = _MockManager()
    key = "http-key-001"
    with patch(
        "src.brokers.broker_manager.get_broker_manager",
        new=AsyncMock(return_value=manager),
    ):
        first = client.post(
            "/broker/order",
            params={"ticker": "SPY", "side": "buy", "quantity": 1},
            headers={"X-API-Key": api_key, "X-Idempotency-Key": key},
        )
        assert first.status_code == 200
        second = client.post(
            "/broker/order",
            params={"ticker": "SPY", "side": "buy", "quantity": 2},
            headers={"X-API-Key": api_key, "X-Idempotency-Key": key},
        )
    assert second.status_code == 409
    body = second.json()
    err = body.get("error") or body.get("detail") or {}
    assert err.get("code") == "idempotency_conflict"
    assert manager.calls == 1


@pytest.mark.asyncio
async def test_broker_order_unknown_retry_returns_503(monkeypatch, tmp_path) -> None:
    client, api_key, _, _ = _sensitive_client(monkeypatch, tmp_path)
    manager = _MockManager(fail=True)
    key = "http-key-002"
    with patch(
        "src.brokers.broker_manager.get_broker_manager",
        new=AsyncMock(return_value=manager),
    ):
        first = client.post(
            "/broker/order",
            params={"ticker": "SPY", "side": "buy", "quantity": 1},
            headers={"X-API-Key": api_key, "X-Idempotency-Key": key},
        )
        assert first.status_code == 503
        first_err = (first.json().get("error") or first.json().get("detail") or {})
        assert first_err.get("code") in (
            "broker_outcome_unknown",
            "persist_failed",
        )
        second = client.post(
            "/broker/order",
            params={"ticker": "SPY", "side": "buy", "quantity": 1},
            headers={"X-API-Key": api_key, "X-Idempotency-Key": key},
        )
    assert second.status_code == 503
    second_err = second.json().get("error") or second.json().get("detail") or {}
    assert second_err.get("code") == "broker_outcome_unknown"
    assert manager.calls == 1
