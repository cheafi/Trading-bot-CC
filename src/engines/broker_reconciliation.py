"""
CC — Broker Reconciliation Engine
===================================
Order-state tracking, fill monitoring, and broker ↔ internal reconciliation.

Institutional requirement: every order sent must have a reconciled fill, partial
fill, or rejection. Discrepancies gate further trading (fail-closed).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.state_paths import atomic_write_text, order_reconciliation_snapshot_path

logger = logging.getLogger(__name__)

_STALE_SENT_SECONDS = 300


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrderState(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ReconciliationStatus(str, Enum):
    OK = "ok"
    MISMATCH = "mismatch"
    PENDING = "pending"
    STALE = "stale"


@dataclass
class OrderRecord:
    """Tracked order with expected vs actual fill."""

    order_id: str = ""
    ticker: str = ""
    direction: str = "BUY"
    quantity: int = 0
    limit_price: Optional[float] = None
    state: OrderState = OrderState.PENDING
    created_at: str = ""
    updated_at: str = ""
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    fill_timestamp: str = ""
    reconciled: bool = False
    reconciled_at: str = ""
    discrepancy: str = ""
    client_order_id: str = ""


def _record_to_dict(rec: OrderRecord) -> Dict[str, Any]:
    row = asdict(rec)
    row["state"] = rec.state.value
    return row


def _record_from_dict(row: Dict[str, Any]) -> OrderRecord:
    state_raw = str(row.get("state") or OrderState.PENDING.value)
    try:
        state = OrderState(state_raw)
    except ValueError:
        state = OrderState.PENDING
    return OrderRecord(
        order_id=str(row.get("order_id") or ""),
        ticker=str(row.get("ticker") or ""),
        direction=str(row.get("direction") or "BUY"),
        quantity=int(row.get("quantity") or 0),
        limit_price=row.get("limit_price"),
        state=state,
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        filled_quantity=int(row.get("filled_quantity") or 0),
        avg_fill_price=float(row.get("avg_fill_price") or 0.0),
        fill_timestamp=str(row.get("fill_timestamp") or ""),
        reconciled=bool(row.get("reconciled")),
        reconciled_at=str(row.get("reconciled_at") or ""),
        discrepancy=str(row.get("discrepancy") or ""),
        client_order_id=str(row.get("client_order_id") or row.get("order_id") or ""),
    )


class BrokerReconciliationEngine:
    """
    Tracks orders, monitors fills, and reconciles broker state
    with internal expected state. Snapshot persisted under STATE_DATA_DIR.
    """

    def __init__(self, *, snapshot_path: Optional[Path] = None):
        self._snapshot_path = snapshot_path or order_reconciliation_snapshot_path()
        self._orders: Dict[str, OrderRecord] = {}
        self._last_reconciliation: str = ""
        self._reconciliation_status = ReconciliationStatus.PENDING
        self._discrepancies: List[Dict[str, Any]] = []
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        path = self._snapshot_path
        if not path.exists():
            self._reconciliation_status = ReconciliationStatus.OK
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            for row in data.get("orders") or []:
                if isinstance(row, dict) and row.get("order_id"):
                    rec = _record_from_dict(row)
                    self._orders[rec.order_id] = rec
            self._last_reconciliation = str(data.get("last_reconciliation") or "")
            st = str(data.get("reconciliation_status") or ReconciliationStatus.PENDING.value)
            try:
                self._reconciliation_status = ReconciliationStatus(st)
            except ValueError:
                self._reconciliation_status = ReconciliationStatus.PENDING
            if self._orders:
                logger.info(
                    "Loaded %d orders from reconciliation snapshot (status=%s)",
                    len(self._orders),
                    self._reconciliation_status.value,
                )
            elif self._reconciliation_status == ReconciliationStatus.PENDING:
                self._reconciliation_status = ReconciliationStatus.OK
        except Exception as exc:
            logger.warning("Reconciliation snapshot load failed: %s", exc)

    def _persist_snapshot(self) -> None:
        payload = {
            "schema": "cc.order_reconciliation.v1",
            "saved_at": _utcnow(),
            "last_reconciliation": self._last_reconciliation,
            "reconciliation_status": self._reconciliation_status.value,
            "orders": [_record_to_dict(o) for o in self._orders.values()],
        }
        try:
            atomic_write_text(
                self._snapshot_path, json.dumps(payload, indent=2, sort_keys=True)
            )
        except Exception as exc:
            logger.warning("Reconciliation snapshot persist failed: %s", exc)

    def record_order(
        self,
        order_id: str,
        ticker: str,
        direction: str,
        quantity: int,
        limit_price: Optional[float] = None,
        *,
        client_order_id: Optional[str] = None,
    ) -> OrderRecord:
        """Record a new outbound order."""
        now = _utcnow()
        cid = str(client_order_id or order_id).strip()
        rec = OrderRecord(
            order_id=order_id,
            client_order_id=cid,
            ticker=ticker,
            direction=direction,
            quantity=quantity,
            limit_price=limit_price,
            state=OrderState.SENT,
            created_at=now,
            updated_at=now,
        )
        self._orders[order_id] = rec
        self._reconciliation_status = ReconciliationStatus.PENDING
        self._persist_snapshot()
        return rec

    def record_fill(
        self,
        order_id: str,
        filled_quantity: int,
        avg_fill_price: float,
    ) -> bool:
        """Record a fill from the broker."""
        rec = self._orders.get(order_id)
        if not rec:
            logger.warning("Fill for unknown order %s", order_id)
            return False
        now = _utcnow()
        rec.filled_quantity = filled_quantity
        rec.avg_fill_price = avg_fill_price
        rec.fill_timestamp = now
        rec.updated_at = now
        if filled_quantity >= rec.quantity:
            rec.state = OrderState.FILLED
        elif filled_quantity > 0:
            rec.state = OrderState.PARTIAL_FILL
        self._persist_snapshot()
        return True

    def record_rejection(self, order_id: str, reason: str = "") -> bool:
        """Record a rejection from the broker."""
        rec = self._orders.get(order_id)
        if not rec:
            return False
        rec.state = OrderState.REJECTED
        rec.discrepancy = reason
        rec.updated_at = _utcnow()
        self._persist_snapshot()
        return True

    def reconcile(
        self,
        broker_positions: Optional[Dict[str, int]] = None,
    ) -> ReconciliationStatus:
        """
        Compare internal order state with broker positions.
        In production, broker_positions comes from the broker API.
        """
        now = _utcnow()
        self._last_reconciliation = now
        self._discrepancies.clear()

        now_dt = datetime.now(timezone.utc)
        for oid, rec in self._orders.items():
            if rec.state != OrderState.SENT:
                continue
            age_sec = 0.0
            try:
                created = datetime.fromisoformat(rec.created_at.replace("Z", "+00:00"))
                age_sec = (now_dt - created).total_seconds()
            except Exception:
                age_sec = _STALE_SENT_SECONDS + 1
            if age_sec >= _STALE_SENT_SECONDS:
                self._discrepancies.append(
                    {
                        "order_id": oid,
                        "issue": "order stale in SENT state",
                        "ticker": rec.ticker,
                        "age_sec": round(age_sec, 1),
                    }
                )

        if broker_positions is not None:
            expected: Dict[str, int] = {}
            for rec in self._orders.values():
                if rec.state in (OrderState.FILLED, OrderState.PARTIAL_FILL):
                    sign = 1 if rec.direction == "BUY" else -1
                    qty = rec.filled_quantity * sign
                    expected[rec.ticker] = expected.get(rec.ticker, 0) + qty
            for ticker, exp_qty in expected.items():
                broker_qty = broker_positions.get(ticker, 0)
                if exp_qty != broker_qty:
                    self._discrepancies.append(
                        {
                            "ticker": ticker,
                            "expected": exp_qty,
                            "broker": broker_qty,
                            "issue": "position mismatch",
                        }
                    )

        if self._discrepancies:
            self._reconciliation_status = ReconciliationStatus.MISMATCH
        else:
            self._reconciliation_status = ReconciliationStatus.OK

        self._persist_snapshot()
        return self._reconciliation_status

    def import_broker_open_orders(
        self, orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge IBKR (or paper) open-order snapshot after restart."""
        imported = 0
        updated = 0
        for row in orders or []:
            if not isinstance(row, dict):
                continue
            oid = str(row.get("order_id") or row.get("orderId") or "").strip()
            sym = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
            if not oid or not sym:
                continue
            action = str(row.get("action") or "BUY").upper()
            qty = int(float(row.get("quantity") or row.get("remaining") or 0))
            if qty <= 0:
                continue
            status_raw = str(row.get("status") or "").strip().lower()
            if status_raw in ("filled",):
                mapped = OrderState.FILLED
            elif status_raw in ("cancelled", "api cancelled", "inactive"):
                mapped = OrderState.CANCELLED
            else:
                mapped = OrderState.SENT
            rec = self._orders.get(oid)
            if not rec:
                self.record_order(
                    oid,
                    sym,
                    action,
                    qty,
                    limit_price=row.get("lmt_price") or row.get("limit_price"),
                    client_order_id=oid,
                )
                imported += 1
                rec = self._orders.get(oid)
            filled = int(float(row.get("filled") or 0))
            if rec:
                if rec.state != mapped:
                    rec.state = mapped
                    updated += 1
                if mapped == OrderState.FILLED and filled <= 0:
                    filled = rec.quantity
                if filled > 0:
                    rec.filled_quantity = filled
                    rec.avg_fill_price = float(row.get("avg_fill_price") or 0.0)
                rec.updated_at = _utcnow()
        if updated:
            self._persist_snapshot()
        return {
            "imported": imported,
            "updated": updated,
            "broker_order_count": len(orders or []),
        }

    def recovery_gate(self) -> Dict[str, Any]:
        """Post-restart: report open orders before trading unlock."""
        open_orders = [
            _record_to_dict(o)
            for o in self._orders.values()
            if o.state in (OrderState.PENDING, OrderState.SENT, OrderState.PARTIAL_FILL)
        ]
        return {
            "open_orders": open_orders,
            "open_count": len(open_orders),
            "reconciliation_status": self._reconciliation_status.value,
            "can_trade": self.can_trade(),
            "requires_broker_reconcile": bool(open_orders)
            or self._reconciliation_status != ReconciliationStatus.OK,
        }

    def status(self) -> Dict[str, Any]:
        """Operator console status report."""
        total = len(self._orders)
        filled = sum(1 for o in self._orders.values() if o.state == OrderState.FILLED)
        pending = sum(
            1
            for o in self._orders.values()
            if o.state in (OrderState.PENDING, OrderState.SENT)
        )
        rejected = sum(
            1 for o in self._orders.values() if o.state == OrderState.REJECTED
        )
        return {
            "total_orders": total,
            "filled": filled,
            "pending": pending,
            "rejected": rejected,
            "reconciliation_status": (self._reconciliation_status.value),
            "last_reconciliation": (self._last_reconciliation or None),
            "discrepancies": self._discrepancies,
            "snapshot_path": str(self._snapshot_path),
            "checked_at": _utcnow(),
            **self.recovery_gate(),
        }

    def can_trade(self) -> bool:
        """Gate: fail-closed — only trade when reconciliation is explicitly OK."""
        if self._reconciliation_status != ReconciliationStatus.OK:
            return False
        open_orders = [
            o
            for o in self._orders.values()
            if o.state in (OrderState.PENDING, OrderState.SENT, OrderState.PARTIAL_FILL)
        ]
        return len(open_orders) == 0


broker_reconciliation = BrokerReconciliationEngine()
