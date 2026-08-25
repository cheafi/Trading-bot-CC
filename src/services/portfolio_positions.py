"""Portfolio position record builders — shared by API and tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.api.routers.portfolio import PositionAddRequest


def build_position_record(
    req: "PositionAddRequest",
    *,
    price: Optional[float],
    now: str,
) -> dict:
    """Build a position dict — stops/targets only when explicitly provided."""
    t = req.ticker.upper().strip()
    entry = float(req.entry_price)
    shares = float(req.shares)
    stop = float(req.stop_price) if req.stop_price and req.stop_price > 0 else 0.0
    stop_defined = stop > 0
    risk = abs(entry - stop) if stop_defined else 0.0

    t1r = float(req.target_1r) if req.target_1r and req.target_1r > 0 else 0.0
    t2r = float(req.target_2r) if req.target_2r and req.target_2r > 0 else 0.0
    if stop_defined and not t1r:
        t1r = round(entry + risk, 2)
    if stop_defined and not t2r:
        t2r = round(entry + 2 * risk, 2)

    quote_pending = price is None
    pos: dict = {
        "ticker": t,
        "shares": shares,
        "avg_cost": entry,
        "entry_price": entry,
        "current_price": price,
        "stop_price": stop if stop_defined else 0,
        "target_1r": t1r if stop_defined else 0,
        "target_2r": t2r if stop_defined else 0,
        "market_value": round(price * shares, 2) if price else None,
        "cost_basis": round(entry * shares, 2),
        "unrealized_pnl": round((price - entry) * shares, 2) if price else None,
        "pnl_pct": round((price / entry - 1) * 100, 2) if price and entry else None,
        "r_multiple": (
            round((price - entry) / risk, 2)
            if price and stop_defined and risk
            else None
        ),
        "stop_defined": stop_defined,
        "quote_pending": quote_pending,
        "status": "OPEN",
        "added_at": now,
        "notes": req.notes or "",
    }
    if req.sleeve and req.sleeve.strip():
        pos["sleeve"] = req.sleeve.strip()
    if req.sector and req.sector.strip():
        pos["sector"] = req.sector.strip()
    return pos


def portfolio_header_snapshot(*, ibkr_connected: bool = False) -> dict:
    """Lightweight book snapshot for CC header / portfolio tab authority."""
    manual = not ibkr_connected
    return {
        "mode": "portfolio",
        "book_label": "Manual book" if manual else "IBKR",
        "position_count": 0,
        "positions_label": "No positions",
        "broker_sync": "ok" if ibkr_connected else "unavailable",
        "broker_sync_label": (
            "Broker sync unavailable" if not ibkr_connected else "Broker linked"
        ),
        "rebalance_only": True,
        "rebalance_label": "Rebalance support only",
        "source": "manual" if manual else "ibkr",
    }
