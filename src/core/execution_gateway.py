"""
Unified execution gateway — single authority for broker-bound orders.

Policy (fail-closed):
  1. Live trading env gate (default paper-only).
  2. TradeGate + reconciliation can_trade semantics.
  3. Idempotency key → at most one broker submission (never auto-retry after unknown).
  4. Reconciliation intent persisted before broker adapter.
  5. Ledger / idempotency persist failure → no broker call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.brokers.base import OrderSide, OrderType
from src.brokers.broker_manager import BrokerManager
from src.brokers.paper_broker import PaperBroker
from src.core.execution_gateway_context import (
    enter_gateway_adapter,
    reset_gateway_adapter,
)
from src.core.execution_idempotency import (
    IdempotencyStore,
    fingerprint_order_payload,
    idempotency_store,
    validate_idempotency_key,
)
from src.core.live_trading_gate import evaluate_live_trading_gate
from src.core.order_execution import (
    LiveTradingRequiredError,
    assert_live_order_permitted,
    track_broker_order_intent,
)
from src.engines.trade_gate import TradeGate

logger = logging.getLogger(__name__)

GATEWAY_SOURCE = "execution_gateway"


class ExecutionGatewayError(Exception):
    """Base execution gateway rejection."""

    def __init__(self, message: str, *, code: str = "execution_rejected") -> None:
        super().__init__(message)
        self.code = code


class ExecutionPersistError(ExecutionGatewayError):
    def __init__(
        self, message: str, *, broker_may_have_executed: bool = False
    ) -> None:
        super().__init__(message, code="ledger_persist_failed")
        self.broker_may_have_executed = broker_may_have_executed


class ExecutionInFlightError(ExecutionGatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="idempotency_in_flight")


class ExecutionIdempotencyConflictError(ExecutionGatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="idempotency_conflict")


class ExecutionUnknownSubmittedError(ExecutionGatewayError):
    def __init__(self, message: str, *, record: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, code="broker_outcome_unknown")
        self.record = record


@dataclass(frozen=True)
class SubmitOrderCommand:
    ticker: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    idempotency_key: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


class ExecutionGateway:
    """Single execution path for API-bound broker orders."""

    def __init__(
        self,
        *,
        trade_gate: Optional[TradeGate] = None,
        idempotency: Optional[IdempotencyStore] = None,
    ) -> None:
        self._trade_gate = trade_gate or TradeGate()
        self._idempotency = idempotency or idempotency_store

    def _broker_scope(self, manager: BrokerManager) -> str:
        active = manager.active_broker
        if active is None:
            return "none"
        return type(active).__name__

    def _payload_hash(self, command: SubmitOrderCommand, manager: BrokerManager) -> str:
        return fingerprint_order_payload(
            ticker=command.ticker,
            side=command.side.value,
            quantity=command.quantity,
            order_type=command.order_type.value,
            limit_price=command.limit_price,
            stop_price=command.stop_price,
            broker_scope=self._broker_scope(manager),
        )

    def _replay_if_completed(
        self, key: str, payload_hash: str
    ) -> Optional[Dict[str, Any]]:
        existing = self._idempotency.get(key)
        if not existing or str(existing.get("status")) != "completed":
            return None
        stored_hash = str(existing.get("payload_hash") or "")
        if stored_hash and stored_hash != payload_hash:
            raise ExecutionIdempotencyConflictError(
                "Idempotency key reused with different order payload"
            )
        cached = existing.get("response")
        if not isinstance(cached, dict):
            raise ExecutionGatewayError(
                "Idempotency record corrupt — reconcile before retry",
                code="idempotency_corrupt",
            )
        out = dict(cached)
        out["idempotent_replay"] = True
        return out

    async def submit(
        self,
        command: SubmitOrderCommand,
        *,
        manager: BrokerManager,
    ) -> Dict[str, Any]:
        key = validate_idempotency_key(command.idempotency_key)
        ticker = str(command.ticker or "").upper().strip()
        if not ticker or command.quantity <= 0:
            raise ExecutionGatewayError("Invalid ticker or quantity", code="validation")

        if not self._idempotency._persist_ok:
            raise ExecutionPersistError(
                "Idempotency store unavailable — order not sent"
            )

        payload_hash = self._payload_hash(command, manager)
        replay = self._replay_if_completed(key, payload_hash)
        if replay is not None:
            return replay

        local_oid = key
        begin_state = self._idempotency.begin(
            key, local_order_id=local_oid, payload_hash=payload_hash
        )
        if begin_state == "replay":
            replay = self._replay_if_completed(key, payload_hash)
            if replay is not None:
                return replay
        if begin_state == "conflict":
            raise ExecutionIdempotencyConflictError(
                "Idempotency key reused with different order payload"
            )
        if begin_state == "unknown_blocked":
            row = self._idempotency.get(key) or {}
            raise ExecutionUnknownSubmittedError(
                "Prior submission outcome unknown — reconcile before retry",
                record=row,
            )
        if begin_state == "in_flight":
            raise ExecutionInFlightError(
                "Duplicate request while prior submission is in flight"
            )
        if begin_state == "persist_failed" or not self._idempotency._persist_ok:
            raise ExecutionPersistError(
                "Idempotency reservation persist failed — order not sent"
            )

        try:
            await self._assert_live_policy(manager)
        except ExecutionGatewayError:
            self._idempotency.abort(key)
            raise

        gate = self._trade_gate.evaluate(ticker=ticker)
        if not gate.allowed:
            self._idempotency.abort(key)
            raise ExecutionGatewayError(
                "; ".join(gate.hard_blocks) or "Trade gate blocked",
                code="trade_gate",
            )

        from src.engines.broker_reconciliation import broker_reconciliation

        track_broker_order_intent(
            source=GATEWAY_SOURCE,
            symbol=ticker,
            side=command.side.value,
            quantity=int(command.quantity),
            order_id=local_oid,
            client_order_id=key,
            limit_price=command.limit_price,
        )
        if not broker_reconciliation._persist_ok:
            self._idempotency.abort(key)
            raise ExecutionPersistError(
                "Reconciliation ledger persist failed — order not sent"
            )

        adapter_token = enter_gateway_adapter()
        broker_started = False
        try:
            broker_started = True
            result = await manager.place_order(
                ticker=ticker,
                side=command.side,
                quantity=command.quantity,
                order_type=command.order_type,
                limit_price=command.limit_price,
                stop_price=command.stop_price,
                skip_ledger_intent=True,
                ledger_order_id=local_oid,
            )
        except Exception as exc:
            reason = f"Broker adapter error: {type(exc).__name__}"
            broker_reconciliation.mark_order_unknown_pending(local_oid, reason)
            partial = {
                "success": False,
                "order_id": local_oid,
                "local_order_id": local_oid,
                "idempotency_key": key,
                "status": "unknown_pending",
                "execution_path": GATEWAY_SOURCE,
                "message": reason,
            }
            self._idempotency.mark_unknown_submitted(
                key, reason=reason, partial_response=partial
            )
            raise ExecutionUnknownSubmittedError(
                "Broker outcome unknown — do not retry with same idempotency key",
                record=partial,
            ) from exc
        finally:
            reset_gateway_adapter(adapter_token)

        response = {
            "success": result.success,
            "order_id": result.order_id or local_oid,
            "local_order_id": local_oid,
            "idempotency_key": key,
            "status": result.status.value,
            "filled_qty": result.filled_qty,
            "avg_fill_price": result.avg_fill_price,
            "message": result.message,
            "execution_path": GATEWAY_SOURCE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not self._idempotency.complete(key, response):
            raise ExecutionPersistError(
                "Idempotency result persist failed — broker may have executed; "
                "reconcile before retry",
                broker_may_have_executed=broker_started,
            )
        return response

    async def _assert_live_policy(self, manager: BrokerManager) -> None:
        active = manager.active_broker
        if active is None:
            raise ExecutionGatewayError("No active broker", code="no_broker")
        if isinstance(active, PaperBroker):
            return

        live = evaluate_live_trading_gate()
        if live.live_allowed:
            return

        account = ""
        paper_port: Optional[int] = None
        try:
            info = await manager.get_account()
            account = str(getattr(info, "account_id", "") or "")
        except Exception:
            pass
        try:
            assert_live_order_permitted(
                dry_run=False, account=account, paper_port=paper_port
            )
        except LiveTradingRequiredError as exc:
            raise ExecutionGatewayError(str(exc), code="live_trading_disabled") from exc


execution_gateway = ExecutionGateway()
