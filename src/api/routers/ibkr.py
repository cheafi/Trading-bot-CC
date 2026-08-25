"""
IBKR Router — Interactive Brokers API endpoints
Paper trading: port 7497  |  Live: port 7496

Endpoints:
  GET  /api/ibkr/status               — connection state
  POST /api/ibkr/connect              — connect to IB Gateway
  POST /api/ibkr/disconnect           — disconnect
  GET  /api/ibkr/account              — account summary
  GET  /api/ibkr/positions            — open positions
  POST /api/ibkr/order                — place an order (paper-safe)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import verify_api_key, sanitize_for_json
from src.services.ibkr_service import (
    default_ibkr_port,
    get_ibkr_service,
    resolve_ibkr_host,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ibkr", tags=["ibkr"])


# ── Request models ────────────────────────────────────────────────────────────


class ConnectRequest(BaseModel):
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    host: Optional[str] = Field(
        default=None, description="IB Gateway hostname/IP (default 127.0.0.1)"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Override socket port; live IB Gateway defaults to 4001",
    )
    client_id: Optional[int] = Field(
        default=None,
        ge=1,
        le=999999,
        description="Override IB API client ID; defaults to IBKR_CLIENT_ID/IB_CLIENT_ID and auto-retries nearby IDs",
    )
    source: Optional[str] = Field(
        default="ibkr_page",
        description="Diagnostic connect source (ibkr_page, manual_test, account_sync, …)",
    )


class PlaceOrderRequest(BaseModel):
    symbol: str
    sec_type: str = Field(
        default="STK", description="STK | OPT | FUT | CASH | BOND | FND"
    )
    action: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    order_type: str = Field(default="MKT", pattern="^(MKT|LMT|STP)$")
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = Field(default="DAY", pattern="^(DAY|GTC)$")
    exchange: str = "SMART"
    currency: str = "USD"


class PlaceBracketRequest(BaseModel):
    """3-leg bracket order: parent entry + child stop + child target (OCA group)."""

    symbol: str
    sec_type: str = Field(default="STK")
    action: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    entry_price: Optional[float] = Field(
        default=None, description="None → MKT entry; else LMT at this price"
    )
    stop_price: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)
    exchange: str = "SMART"
    currency: str = "USD"
    # Trailing-stop variant: replaces the STP child with a TRAIL order.
    trail: bool = False
    trail_amount: Optional[float] = Field(default=None, gt=0, description="$ trail")
    trail_percent: Optional[float] = Field(
        default=None, gt=0, le=50, description="% trail (0-50)"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/status")
async def ibkr_status(
    manual_positions: int = 0,
    broker_positions: int = 0,
    bracket_enabled: bool = False,
    bracket_stop: Optional[float] = None,
    bracket_target: Optional[float] = None,
):
    """Connection state + execution readiness matrix — no auth required for health polling."""
    svc = get_ibkr_service()
    st = svc.status()
    gateway_reachable = bool(st.get("gateway_reachable"))
    st["diagnostics"] = svc.diagnostics()
    st["readiness"] = svc.build_readiness_matrix(
        gateway_reachable=gateway_reachable,
        broker_position_count=max(0, broker_positions),
        manual_position_count=max(0, manual_positions),
        bracket_enabled=bracket_enabled,
        bracket_stop=bracket_stop,
        bracket_target=bracket_target,
    )
    st["health"] = st.get("health") or st["readiness"].get("health")
    diagnosis = svc.build_diagnosis(
        bracket_status=str(st["readiness"].get("bracket_status") or "unavailable"),
        bracket_enabled=bracket_enabled,
        trade_handoff_ready=bool(st["readiness"].get("full_handoff_ready")),
    )
    st["diagnosis"] = diagnosis
    st["gateway_reachable"] = bool(diagnosis.get("gateway_reachable", gateway_reachable))
    st["api_port_open"] = bool(diagnosis.get("api_port_open"))
    st["health_label"] = diagnosis.get("label") or st.get("health_label")
    st["health_label_short"] = diagnosis.get("short")
    st["source_of_truth"] = {
        "broker_label": "IBKR positions = broker truth",
        "portfolio_label": "Portfolio page = research/manual book",
        "note": (
            st["readiness"].get("portfolio_sync_reason")
            if st.get("connected")
            else "Connect IBKR for broker-authoritative positions"
        ),
    }
    return st


@router.post("/connect")
async def ibkr_connect(req: ConnectRequest, _=Depends(verify_api_key)):
    """
    Connect to IB Gateway / TWS.
    mode='paper' → port 7497 unless overridden
    mode='live'  → port 4001 for IB Gateway unless overridden (7496 for TWS live)
    """
    svc = get_ibkr_service()
    source = (req.source or "ibkr_page").strip() or "ibkr_page"
    result = await svc.connect(
        mode=req.mode,
        host=req.host or None,
        port=req.port,
        client_id=req.client_id,
        source=source,  # type: ignore[arg-type]
    )
    if not result.get("ok"):
        err = result.get("error", "Connection failed")
        try:
            from src.services.platform_error_log import log_broker_event

            log_broker_event(
                event="IBKR connect failed",
                detail=(
                    f"Handshake to IB Gateway did not succeed ({err}). "
                    "The IBKR tab will show disconnected until Gateway/TWS accepts the API session."
                ),
                severity="critical",
            )
        except Exception:
            logger.debug("platform error log append failed", exc_info=True)
        raise HTTPException(status_code=503, detail=err)
    return result


@router.post("/disconnect")
async def ibkr_disconnect(_=Depends(verify_api_key)):
    """Gracefully disconnect from IB Gateway."""
    svc = get_ibkr_service()
    await svc.disconnect()
    return {"ok": True, "connected": False}


class PingRequest(BaseModel):
    host: str = "127.0.0.1"
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    port: Optional[int] = Field(default=None, ge=1, le=65535)


@router.post("/ping")
async def ibkr_ping(req: PingRequest):
    """
    Session snapshot — does NOT open a raw TCP socket (avoids JTS log spam).
    Use POST /connect for a full IB API handshake.
    """
    svc = get_ibkr_service()
    transport = svc.get_transport_snapshot()
    host = resolve_ibkr_host(req.host)
    port = req.port or default_ibkr_port(req.mode)
    from src.services.ibkr_diagnosis import build_ibkr_diagnosis, probe_tcp_port
    from src.services.ibkr_service import IBAPI_AVAILABLE, _running_in_docker

    diagnosis = build_ibkr_diagnosis(
        mode=req.mode,
        host=host,
        port=port,
        docker=_running_in_docker(),
        ibapi_available=IBAPI_AVAILABLE,
        socket_connected=svc.is_connected,
        session_usable=bool(transport.get("session_status") not in ("inactive", "lost")),
        ib_api_ready=bool(transport.get("ib_api_ready")),
        paper_port=svc.PAPER_PORT,
        live_ports=[svc.LIVE_PORT, svc.LIVE_TWS_PORT],
    )
    api_open = probe_tcp_port(host, port)
    reachable = bool(diagnosis.get("gateway_reachable") or transport.get("gateway_reachable"))
    message = diagnosis.get("label") or (
        f"IB API session ready on {host}:{port}"
        if transport.get("ib_api_ready")
        else f"Port {'open' if api_open else 'closed'} at {host}:{port}"
    )
    return {
        "reachable": reachable,
        "api_port_open": api_open,
        "host": host,
        "port": port,
        "mode": req.mode,
        "message": message,
        "hint": diagnosis.get("hint"),
        "diagnosis": diagnosis,
        "transport": transport,
        "probe_type": "tcp_plus_session",
    }


@router.get("/account")
async def ibkr_account(_=Depends(verify_api_key)):
    """
    Fetch account summary from IB Gateway.
    Returns: NetLiquidation, cash, buying power, unrealized/realized PnL.
    """
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Not connected to IB Gateway. POST /api/ibkr/connect first.",
        )

    summary = await svc.get_account_summary()
    if summary is None:
        raise HTTPException(
            status_code=504, detail="Timeout fetching account summary from IB Gateway"
        )

    return sanitize_for_json(
        {
            "account": summary.account,
            "net_liquidation": summary.net_liquidation,
            "cash_balance": summary.cash_balance,
            "buying_power": summary.buying_power,
            "unrealized_pnl": summary.unrealized_pnl,
            "realized_pnl": summary.realized_pnl,
            "gross_position_value": summary.gross_position_value,
            "init_margin_req": summary.init_margin_req,
            "maint_margin_req": summary.maint_margin_req,
            "available_funds": summary.available_funds,
            "leverage": (
                round(summary.gross_position_value / summary.net_liquidation, 2)
                if summary.net_liquidation > 0
                else 0.0
            ),
            "margin_cushion_pct": (
                round(
                    (summary.net_liquidation - summary.maint_margin_req)
                    / summary.net_liquidation
                    * 100,
                    1,
                )
                if summary.net_liquidation > 0
                else 0.0
            ),
            "currency": summary.currency,
        }
    )


@router.get("/positions")
async def ibkr_positions(_=Depends(verify_api_key)):
    """
    Fetch all open positions from IB Gateway.
    Returns list of {symbol, sec_type, position, avg_cost, unrealized_pnl}.
    """
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")

    positions = await svc.get_positions()
    return sanitize_for_json(
        {
            "count": len(positions),
            "positions": [
                {
                    "account": p.account,
                    "symbol": p.symbol,
                    "sec_type": p.sec_type,
                    "exchange": p.exchange,
                    "currency": p.currency,
                    "position": p.position,
                    "avg_cost": p.avg_cost,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                }
                for p in positions
            ],
        }
    )


@router.post("/order")
async def ibkr_place_order(
    req: PlaceOrderRequest,
    _=Depends(verify_api_key),
    x_confirm_live_order: Optional[str] = Header(default=None),
):
    """
    Place an order via IB Gateway.

    ⚠ CRO SAFETY: Live orders require the header `X-Confirm-Live-Order: CONFIRMED`.
    Paper mode works without the header. Never submit live orders without explicit
    confirmation — missing header on a live session raises HTTP 403.

    Supported sec_type: STK (stock), OPT (option), FUT (futures), CASH (FX), BOND, FND (fund)
    """
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")

    mode = svc._mode

    # ── CRO gate: live orders require explicit double-confirmation header ──
    if mode == "live":
        if x_confirm_live_order != "CONFIRMED":
            logger.warning(
                "[IBKR] Blocked live order attempt for %s — missing X-Confirm-Live-Order header",
                req.symbol,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    "Live order blocked: add header 'X-Confirm-Live-Order: CONFIRMED' "
                    "to explicitly authorise a real-money order."
                ),
            )

    logger.info(
        "[IBKR] order request mode=%s %s %.4gx %s (%s) %s lmt=%s",
        mode,
        req.action,
        req.quantity,
        req.symbol,
        req.sec_type,
        req.order_type,
        req.limit_price,
    )

    result = await svc.place_order(
        symbol=req.symbol,
        sec_type=req.sec_type,
        action=req.action,
        quantity=req.quantity,
        order_type=req.order_type,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        tif=req.tif,
        exchange=req.exchange,
        currency=req.currency,
    )

    if result.error and "may still be active" not in result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return sanitize_for_json(
        {
            "order_id": result.order_id,
            "status": result.status,
            "filled": result.filled,
            "remaining": result.remaining,
            "avg_fill_price": result.avg_fill_price,
            "mode": mode,
            "warning": result.error if result.error else None,
        }
    )


@router.post("/bracket")
async def ibkr_place_bracket(
    req: PlaceBracketRequest,
    _=Depends(verify_api_key),
    x_confirm_live_order: Optional[str] = Header(default=None),
):
    """
    Place a 3-leg bracket: parent entry + STP stop child + LMT target child (OCA).
    Same live-order CRO gate as /order. Returns parent + child order ids and OCA group.
    """
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")

    mode = svc._mode
    if mode == "live" and x_confirm_live_order != "CONFIRMED":
        logger.warning(
            "[IBKR] Blocked live bracket attempt for %s — missing X-Confirm-Live-Order header",
            req.symbol,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Live bracket blocked: add header 'X-Confirm-Live-Order: CONFIRMED' "
                "to explicitly authorise a real-money order."
            ),
        )

    logger.info(
        "[IBKR] bracket request mode=%s %s %.4gx %s entry=%s stop=%s target=%s",
        mode,
        req.action,
        req.quantity,
        req.symbol,
        req.entry_price,
        req.stop_price,
        req.take_profit,
    )

    result = await svc.place_bracket_order(
        symbol=req.symbol,
        sec_type=req.sec_type,
        action=req.action,
        quantity=req.quantity,
        entry_price=req.entry_price,
        stop_price=req.stop_price,
        take_profit=req.take_profit,
        exchange=req.exchange,
        currency=req.currency,
        trail=req.trail,
        trail_amount=req.trail_amount,
        trail_percent=req.trail_percent,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    result["mode"] = mode
    return sanitize_for_json(result)


class CancelBracketRequest(BaseModel):
    """Cancel all 3 legs of a bracket. Parent cancel usually cascades to children."""

    parent_order_id: int
    stop_order_id: Optional[int] = None
    target_order_id: Optional[int] = None


@router.delete("/order/{order_id}")
async def ibkr_cancel_order(order_id: int, _=Depends(verify_api_key)):
    """Cancel a single working order by id."""
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")
    result = await svc.cancel_order(order_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Cancel failed")
        )
    return sanitize_for_json(result)


@router.post("/cancel-bracket")
async def ibkr_cancel_bracket(req: CancelBracketRequest, _=Depends(verify_api_key)):
    """Cancel all 3 legs of a bracket (parent + stop + target)."""
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")
    result = await svc.cancel_bracket(
        parent_id=req.parent_order_id,
        stop_id=req.stop_order_id,
        target_id=req.target_order_id,
    )
    return sanitize_for_json(result)


@router.get("/open-orders")
async def ibkr_open_orders(_=Depends(verify_api_key)):
    """
    Snapshot of currently open/working orders (used by the live bracket panel poll).
    Returns list of {order_id, symbol, action, order_type, quantity, parent_id,
    oca_group, status, filled, remaining, avg_fill_price, ...}.
    """
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")
    orders = await svc.get_open_orders()
    return sanitize_for_json({"count": len(orders), "orders": orders})


@router.get("/recent-fills")
async def ibkr_recent_fills(_=Depends(verify_api_key)):
    """Recent execution fills captured from IB execDetails callbacks (session-local)."""
    svc = get_ibkr_service()
    if not svc.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IB Gateway.")
    fills = svc.get_recent_fills()
    return sanitize_for_json({"count": len(fills), "fills": fills})
