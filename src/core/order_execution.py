"""Lowest-order execution boundary — dry_run default, live gate, simulation ledger."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.live_trading_gate import authorize_live_order
from src.core.state_paths import atomic_write_jsonl_append, simulation_ledger_path

logger = logging.getLogger(__name__)


class LiveTradingRequiredError(RuntimeError):
    """Raised when dry_run=False without full live authorisation."""


def assert_live_order_permitted(
    *, dry_run: bool, account: str = "", paper_port: Optional[int] = None
) -> None:
    """Fail closed unless authorised or a verified IB paper account/session.

    Environment mode alone cannot establish that the connected broker is paper.
    Callers may supply an actual paper-session port, never an environment hint.
    """
    if dry_run:
        return
    if paper_port in (7497, 4002) and str(account).strip().upper().startswith("DU"):
        return
    auth = authorize_live_order(account)
    if not auth.live_allowed:
        missing = ", ".join(auth.missing) or "unknown"
        raise LiveTradingRequiredError(
            f"Live order blocked — missing gate requirements: {missing}"
        )


def append_simulation_ledger(entry: Dict[str, Any]) -> str:
    """Append-only simulation ledger for dry-run orders."""
    path = simulation_ledger_path()
    row = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **entry,
    }
    atomic_write_jsonl_append(path, row)
    return str(path)


def record_dry_run_order(
    *,
    source: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "MKT",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a dry-run order without touching the live broker."""
    payload: Dict[str, Any] = {
        "mode": "dry_run",
        "source": source,
        "symbol": str(symbol or "").upper(),
        "side": str(side or "").upper(),
        "quantity": quantity,
        "order_type": order_type,
    }
    if extra:
        payload.update(extra)
    append_simulation_ledger(payload)
    logger.info(
        "[DRY RUN] recorded %s %s x%s (%s) via %s",
        payload["side"],
        payload["symbol"],
        payload["quantity"],
        payload["order_type"],
        source,
    )


def track_ibkr_bracket_intents(
    *,
    symbol: str,
    parent_action: str,
    child_action: str,
    quantity: int,
    parent_order_id: int,
    stop_order_id: int,
    target_order_id: int,
    entry_price: Optional[float],
    stop_price: float,
    take_profit: float,
    oca_group: str,
) -> dict[str, str]:
    """Persist bracket legs in reconciliation ledger before IB placeOrder."""
    source = "ibkr_bracket"
    parent = track_broker_order_intent(
        source=source,
        symbol=symbol,
        side=parent_action,
        quantity=int(quantity),
        order_id=str(parent_order_id),
        limit_price=entry_price,
    )
    stop = track_broker_order_intent(
        source=source,
        symbol=symbol,
        side=child_action,
        quantity=int(quantity),
        order_id=str(stop_order_id),
        limit_price=stop_price,
    )
    target = track_broker_order_intent(
        source=source,
        symbol=symbol,
        side=child_action,
        quantity=int(quantity),
        order_id=str(target_order_id),
        limit_price=take_profit,
    )
    logger.info(
        "[Reconciliation] bracket intents oca=%s parent=%s stop=%s target=%s",
        oca_group,
        parent,
        stop,
        target,
    )
    return {"parent": parent, "stop": stop, "target": target}


def track_broker_order_intent(
    *,
    source: str,
    symbol: str,
    side: str,
    quantity: int,
    order_id: Optional[str] = None,
    client_order_id: Optional[str] = None,
    limit_price: Optional[float] = None,
) -> str:
    """Persist outbound order in reconciliation ledger (fail-closed gate input)."""
    from src.engines.broker_reconciliation import broker_reconciliation

    cid = str(client_order_id or order_id or uuid.uuid4().hex[:16])
    oid = str(order_id or cid)
    broker_reconciliation.record_order(
        oid,
        str(symbol or "").upper(),
        str(side or "BUY").upper(),
        int(quantity),
        limit_price=limit_price,
        client_order_id=cid,
    )
    logger.debug("[Reconciliation] tracked %s from %s", oid, source)
    return oid


def track_broker_fill(
    order_id: str,
    *,
    filled_quantity: int,
    avg_fill_price: float = 0.0,
) -> None:
    from src.engines.broker_reconciliation import broker_reconciliation

    broker_reconciliation.record_fill(
        str(order_id),
        int(filled_quantity),
        float(avg_fill_price or 0.0),
    )
