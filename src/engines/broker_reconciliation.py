"""
CC — Broker Reconciliation Engine
===================================
Stubs for order-state tracking, fill monitoring, and
broker ↔ internal-state reconciliation.

Institutional requirement: every order sent must have a
reconciled fill, partial fill, or rejection. Discrepancies
trigger alerts and can gate further trading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    # State
    state: OrderState = OrderState.PENDING
    created_at: str = ""
    updated_at: str = ""
    # Fill info
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    fill_timestamp: str = ""
    # Reconciliation
    reconciled: bool = False
    reconciled_at: str = ""
    discrepancy: str = ""


class BrokerReconciliationEngine:
    """
    Tracks orders, monitors fills, and reconciles broker state
    with internal expected state.

    Flow:
    1. record_order() — when order is sent
    2. record_fill() — when broker confirms fill
    3. reconcile() — compare internal vs broker state
    4. status() — report for operator console
    """

    def __init__(self):
        self._orders: Dict[str, OrderRecord] = {}
        self._last_reconciliation: str = ""
        self._reconciliation_status = ReconciliationStatus.PENDING
        self._discrepancies: List[Dict[str, Any]] = []

    def record_order(
        self,
        order_id: str,
        ticker: str,
        direction: str,
        quantity: int,
        limit_price: Optional[float] = None,
    ) -> OrderRecord:
        """Record a new outbound order."""
        now = _utcnow()
        rec = OrderRecord(
            order_id=order_id,
            ticker=ticker,
            direction=direction,
            quantity=quantity,
            limit_price=limit_price,
            state=OrderState.SENT,
            created_at=now,
            updated_at=now,
        )
        self._orders[order_id] = rec
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
        return True

    def record_rejection(self, order_id: str, reason: str = "") -> bool:
        """Record a rejection from the broker."""
        rec = self._orders.get(order_id)
        if not rec:
            return False
        rec.state = OrderState.REJECTED
        rec.discrepancy = reason
        rec.updated_at = _utcnow()
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

        # Check for stale unresolved orders (sent > 5 min ago)
        for oid, rec in self._orders.items():
            if rec.state == OrderState.SENT:
                self._discrepancies.append(
                    {
                        "order_id": oid,
                        "issue": "order still in SENT state",
                        "ticker": rec.ticker,
                    }
                )

        if broker_positions:
            # Compare expected net position vs broker
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

        return self._reconciliation_status

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
            "checked_at": _utcnow(),
        }

    def can_trade(self) -> bool:
        """Gate: block new trades if reconciliation is bad."""
        return self._reconciliation_status in (
            ReconciliationStatus.OK,
            ReconciliationStatus.PENDING,
        )


# Module singleton
broker_reconciliation = BrokerReconciliationEngine()
