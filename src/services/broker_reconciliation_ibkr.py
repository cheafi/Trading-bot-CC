"""Replay IBKR open orders + positions into the reconciliation engine (crash recovery)."""

from __future__ import annotations

from typing import Any, Dict, List

from src.engines.broker_reconciliation import broker_reconciliation
from src.services.research_safety import sanitize_research_payload


def positions_to_qty_map(positions: List[Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for pos in positions or []:
        sym = str(
            getattr(pos, "symbol", None) or getattr(pos, "ticker", "") or ""
        ).upper()
        if not sym:
            continue
        qty = int(getattr(pos, "quantity", getattr(pos, "qty", 0)) or 0)
        side = str(
            getattr(pos, "direction", getattr(pos, "side", "long")) or "long"
        ).lower()
        signed = qty if side in ("long", "buy") else -abs(qty)
        out[sym] = out.get(sym, 0) + signed
    return out


async def sync_reconciliation_from_ibkr() -> Dict[str, Any]:
    """Fetch IBKR truth, merge orders, reconcile positions — fail-closed until OK."""
    from src.services.ibkr_service import get_ibkr_service

    svc = get_ibkr_service()
    if not svc.is_connected:
        return sanitize_research_payload(
            {
                "ok": False,
                "error": "ibkr_not_connected",
                "recovery": broker_reconciliation.recovery_gate(),
            }
        )
    open_orders = await svc.get_open_orders()
    positions = await svc.get_positions()
    merge = broker_reconciliation.import_broker_open_orders(open_orders)
    pos_map = positions_to_qty_map(positions)
    status = broker_reconciliation.reconcile(broker_positions=pos_map)
    return sanitize_research_payload(
        {
            "ok": True,
            "reconciliation_status": status.value,
            "can_trade": broker_reconciliation.can_trade(),
            "positions": pos_map,
            "merge": merge,
            "recovery": broker_reconciliation.recovery_gate(),
        }
    )
