"""Unified execution gateway — idempotency, gate, persist fail-closed."""

from __future__ import annotations

import pytest

from src.brokers.base import OrderResult, OrderSide, OrderStatus, OrderType
from src.core.execution_gateway import (
    ExecutionGateway,
    ExecutionInFlightError,
    ExecutionPersistError,
    SubmitOrderCommand,
)
from src.core.execution_idempotency import IdempotencyStore
from src.engines.broker_reconciliation import BrokerReconciliationEngine, ReconciliationStatus


class _PaperManager:
    def __init__(self) -> None:
        from src.brokers.paper_broker import PaperBroker

        self.active_broker = PaperBroker()
        self.calls = 0

    async def get_account(self):
        class _A:
            account_id = "PAPER"

        return _A()

    async def place_order(self, **kwargs):
        self.calls += 1
        return OrderResult(
            success=True,
            order_id="broker-99",
            status=OrderStatus.FILLED,
            filled_qty=kwargs.get("quantity", 1),
            avg_fill_price=100.0,
            message="ok",
        )


@pytest.mark.asyncio
async def test_gateway_idempotent_replay_single_broker_call(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    snap = tmp_path / "ledger.json"
    idem = tmp_path / "idem.json"
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    eng.mark_simulation_ready()
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    store = IdempotencyStore(path=idem)
    gw = ExecutionGateway(idempotency=store)
    manager = _PaperManager()
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=2,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-001",
    )
    first = await gw.submit(cmd, manager=manager)
    second = await gw.submit(cmd, manager=manager)
    assert manager.calls == 1
    assert first["order_id"] == second["order_id"]
    assert second.get("idempotent_replay") is True


@pytest.mark.asyncio
async def test_gateway_persist_fail_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    snap = tmp_path / "ledger.json"
    idem = tmp_path / "idem.json"
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    eng.mark_simulation_ready()
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    store = IdempotencyStore(path=idem)
    store._persist_ok = False
    gw = ExecutionGateway(idempotency=store)
    manager = _PaperManager()
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-002",
    )
    with pytest.raises(ExecutionPersistError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 0


@pytest.mark.asyncio
async def test_gateway_blocks_when_reconciliation_not_ready(
    tmp_path, monkeypatch
) -> None:
    snap = tmp_path / "ledger.json"
    idem = tmp_path / "idem.json"
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    assert eng._reconciliation_status == ReconciliationStatus.UNKNOWN
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    store = IdempotencyStore(path=idem)
    gw = ExecutionGateway(idempotency=store)
    manager = _PaperManager()
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-003",
    )
    from src.core.execution_gateway import ExecutionGatewayError

    with pytest.raises(ExecutionGatewayError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 0


def test_idempotency_in_flight_conflict(tmp_path) -> None:
    store = IdempotencyStore(path=tmp_path / "i.json")
    assert store.begin("key-0001", local_order_id="key-0001") == "new"
    assert store.begin("key-0001", local_order_id="key-0001") == "in_flight"
