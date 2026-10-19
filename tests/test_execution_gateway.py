"""Unified execution gateway — idempotency, gate, persist fail-closed."""

from __future__ import annotations

import json

import pytest

from src.brokers.base import OrderResult, OrderSide, OrderStatus, OrderType
from src.core.execution_gateway import (
    ExecutionGateway,
    ExecutionIdempotencyConflictError,
    ExecutionInFlightError,
    ExecutionPersistError,
    ExecutionUnknownSubmittedError,
    SubmitOrderCommand,
)
from src.core.execution_idempotency import IdempotencyStore, fingerprint_order_payload
from src.engines.broker_reconciliation import (
    BrokerReconciliationEngine,
    OrderState,
    ReconciliationStatus,
)


class _PaperManager:
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
        return OrderResult(
            success=True,
            order_id="broker-99",
            status=OrderStatus.FILLED,
            filled_qty=kwargs.get("quantity", 1),
            avg_fill_price=100.0,
            message="ok",
        )


def _hash(cmd: SubmitOrderCommand, manager: _PaperManager) -> str:
    return fingerprint_order_payload(
        ticker=cmd.ticker,
        side=cmd.side.value,
        quantity=cmd.quantity,
        order_type=cmd.order_type.value,
        limit_price=cmd.limit_price,
        stop_price=cmd.stop_price,
        broker_scope=type(manager.active_broker).__name__,
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
async def test_gateway_persist_fail_closed_before_broker(tmp_path, monkeypatch) -> None:
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


@pytest.mark.asyncio
async def test_broker_exception_blocks_retry_same_key(tmp_path, monkeypatch) -> None:
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
    manager = _PaperManager(fail=True)
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-004",
    )
    with pytest.raises(ExecutionUnknownSubmittedError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 1
    assert eng._orders["idem-key-004"].state == OrderState.UNKNOWN_PENDING
    with pytest.raises(ExecutionUnknownSubmittedError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 1


def test_idempotency_in_flight_conflict(tmp_path) -> None:
    store = IdempotencyStore(path=tmp_path / "i.json")
    h = "a" * 64
    assert store.begin("key-0001", local_order_id="key-0001", payload_hash=h) == "new"
    assert store.begin("key-0001", local_order_id="key-0001", payload_hash=h) == "in_flight"


def test_idempotency_payload_conflict(tmp_path) -> None:
    store = IdempotencyStore(path=tmp_path / "i.json")
    store.begin("key-0002", local_order_id="key-0002", payload_hash="hash-a")
    store.complete("key-0002", {"ok": True})
    assert store.begin("key-0002", local_order_id="key-0002", payload_hash="hash-b") == "conflict"


def test_begin_persist_failed_rolls_back_memory(tmp_path, monkeypatch) -> None:
    store = IdempotencyStore(path=tmp_path / "i.json")

    def _fail_save() -> bool:
        store._persist_ok = False
        return False

    monkeypatch.setattr(store, "_save", _fail_save)
    assert store.begin("key-0003", local_order_id="key-0003", payload_hash="h") == "persist_failed"
    assert "key-0003" not in store._records


@pytest.mark.asyncio
async def test_mark_unknown_persist_fail_blocks_same_process_retry(
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
    real_save = store._save
    calls = {"n": 0}

    def _flaky_save() -> bool:
        calls["n"] += 1
        if calls["n"] == 3:
            return False
        return real_save()

    monkeypatch.setattr(store, "_save", _flaky_save)
    gw = ExecutionGateway(idempotency=store)
    manager = _PaperManager(fail=True)
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-005",
    )
    with pytest.raises(ExecutionPersistError) as first_exc:
        await gw.submit(cmd, manager=manager)
    assert first_exc.value.broker_may_have_executed is True
    with pytest.raises(ExecutionUnknownSubmittedError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 1


@pytest.mark.asyncio
async def test_complete_persist_fail_survives_restart(tmp_path, monkeypatch) -> None:
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

    real_save = store._save

    def _fail_completed_write() -> bool:
        for row in store._records.values():
            if row.get("status") == "completed":
                return False
        return real_save()

    monkeypatch.setattr(store, "_save", _fail_completed_write)
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-006",
    )
    with pytest.raises(ExecutionPersistError):
        await gw.submit(cmd, manager=manager)
    assert manager.calls == 1

    reloaded = IdempotencyStore(path=idem)
    row = reloaded.get("idem-key-006") or {}
    assert row.get("status") == "unknown_submitted"
    gw2 = ExecutionGateway(idempotency=reloaded)
    with pytest.raises(ExecutionUnknownSubmittedError):
        await gw2.submit(cmd, manager=manager)
    assert manager.calls == 1


@pytest.mark.asyncio
async def test_complete_double_persist_fail_emergency_restart(
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
    real_save = store._save

    def _fail_completed_and_unknown_writes() -> bool:
        for row in store._records.values():
            if row.get("status") in ("completed", "unknown_submitted"):
                return False
        return real_save()

    monkeypatch.setattr(store, "_save", _fail_completed_and_unknown_writes)
    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-007",
    )
    with pytest.raises(ExecutionPersistError):
        await gw.submit(cmd, manager=manager)
    assert (tmp_path / "idem_emergency.json").exists()
    reloaded = IdempotencyStore(path=idem)
    row = reloaded.get("idem-key-007") or {}
    assert row.get("status") == "unknown_submitted"
    gw2 = ExecutionGateway(idempotency=reloaded)
    with pytest.raises(ExecutionUnknownSubmittedError):
        await gw2.submit(cmd, manager=manager)
    assert manager.calls == 1


def test_in_flight_broker_started_blocks_after_reload(tmp_path) -> None:
    path = tmp_path / "idem.json"
    path.write_text(
        json.dumps(
            {
                "records": {
                    "key-7777": {
                        "status": "in_flight",
                        "broker_submit_started": True,
                        "payload_hash": "abc",
                        "local_order_id": "key-7777",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    store = IdempotencyStore(path=path)
    assert (
        store.begin("key-7777", local_order_id="key-7777", payload_hash="abc")
        == "unknown_blocked"
    )


@pytest.mark.asyncio
async def test_account_scope_fail_closed_for_non_paper(tmp_path, monkeypatch) -> None:
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

    class _LiveishManager(_PaperManager):
        async def get_account(self):
            raise RuntimeError("no account")

    manager = _LiveishManager()
    manager.active_broker = object()

    cmd = SubmitOrderCommand(
        ticker="SPY",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        idempotency_key="idem-key-008",
    )
    from src.core.execution_gateway import ExecutionGatewayError

    with pytest.raises(ExecutionGatewayError) as exc:
        await gw.submit(cmd, manager=manager)
    assert exc.value.code == "account_scope_unverified"
    assert manager.calls == 0
