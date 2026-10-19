"""
Unified execution gateway — single authority for broker-bound orders.

Policy (fail-closed):
  1. Live trading env gate (default paper-only).
  2. TradeGate + reconciliation can_trade semantics.
  3. Idempotency key → at most one broker submission.
  4. Reconciliation intent persisted before broker adapter.
  5. Ledger persist failure → no broker call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.brokers.base import OrderSide, OrderType
from src.brokers.broker_manager import BrokerManager
from src.brokers.paper_broker import PaperBroker
from src.core.execution_idempotency import IdempotencyStore, idempotency_store, validate_idempotency_key
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
    def __init__(self, message: str) -> None:
        super().__init__(message, code="ledger_persist_failed")


class ExecutionInFlightError(ExecutionGatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="idempotency_in_flight")


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

        existing = self._idempotency.get(key)
        if existing and str(existing.get("status")) == "completed":
            cached = existing.get("response")
            if isinstance(cached, dict):
                out = dict(cached)
                out["idempotent_replay"] = True
                return out

        local_oid = key
        begin_state = self._idempotency.begin(key, local_order_id=local_oid)
        if begin_state == "replay":
            cached = self._idempotency.get(key)
            if cached and isinstance(cached.get("response"), dict):
                out = dict(cached["response"])
                out["idempotent_replay"] = True
                return out
        if begin_state == "in_flight":
            raise ExecutionInFlightError(
                "Duplicate request while prior submission is in flight"
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

        try:
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
        except Exception:
            self._idempotency.abort(key)
            raise

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
        self._idempotency.complete(key, response)
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
