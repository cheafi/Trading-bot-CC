"""
Broker Router — Sprint 82
==========================
Extracted from main.py (was 6 inline @app.get/post routes, lines ~2562-2828).

Endpoints:
    GET  /broker/status
    POST /broker/switch/{broker_type}
    GET  /broker/account
    GET  /broker/positions
    POST /broker/order
    GET  /broker/quote/{ticker}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/status")
async def get_broker_status(_: bool = Depends(verify_api_key)):
    """
    Get status of all connected brokers.

    Returns:
    - List of brokers with connection status
    - Active broker
    - Account balances
    """
    from src.brokers.broker_manager import get_broker_manager

    try:
        manager = await get_broker_manager()
        brokers = manager.get_available_brokers()

        return {
            "active_broker": manager.active_broker_type.value,
            "brokers": brokers,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Broker status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/switch/{broker_type}")
async def switch_broker(broker_type: str, _: bool = Depends(verify_api_key)):
    """
    Switch active broker.

    Args:
        broker_type: 'futu', 'ib', or 'paper'
    """
    from src.brokers.broker_manager import BrokerType, get_broker_manager

    try:
        broker_enum = BrokerType(broker_type.lower())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid broker type: {broker_type}",
        ) from e

    try:
        manager = await get_broker_manager()
        success = manager.set_active_broker(broker_enum)

        if success:
            return {
                "success": True,
                "active_broker": broker_type,
                "message": f"Switched to {broker_type}",
            }
        else:
            raise HTTPException(
                status_code=400, detail=f"Broker {broker_type} not available"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Switch broker error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/account")
async def get_broker_account(
    broker: Optional[str] = None, _: bool = Depends(verify_api_key)
):
    """
    Get account information from broker.

    Args:
        broker: Specific broker (uses active if not specified)
    """
    from src.brokers.broker_manager import BrokerType, get_broker_manager

    try:
        manager = await get_broker_manager()

        broker_type = None
        if broker:
            try:
                broker_type = BrokerType(broker.lower())
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid broker: {broker}",
                ) from e

        account = await manager.get_account(broker_type)

        return {
            "account_id": account.account_id,
            "currency": account.currency,
            "cash": round(account.cash, 2),
            "buying_power": round(account.buying_power, 2),
            "portfolio_value": round(account.portfolio_value, 2),
            "unrealized_pnl": round(account.unrealized_pnl, 2),
            "realized_pnl_today": round(account.realized_pnl_today, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Account info error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/positions")
async def get_broker_positions(
    broker: Optional[str] = None, _: bool = Depends(verify_api_key)
):
    """
    Get open positions from broker.

    Args:
        broker: Specific broker (uses active if not specified)
    """
    from src.brokers.broker_manager import BrokerType, get_broker_manager

    try:
        manager = await get_broker_manager()

        broker_type = None
        if broker:
            try:
                broker_type = BrokerType(broker.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid broker: {broker}")

        positions = await manager.get_positions(broker_type)

        return {
            "positions": [
                {
                    "ticker": pos.ticker,
                    "quantity": pos.quantity,
                    "avg_price": round(pos.avg_price, 2),
                    "current_price": round(pos.current_price, 2),
                    "market_value": round(pos.market_value, 2),
                    "unrealized_pnl": round(pos.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(pos.unrealized_pnl_pct, 2),
                    "market": pos.market.value,
                }
                for pos in positions
            ],
            "total_positions": len(positions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Positions error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/order")
async def place_order(
    ticker: str,
    side: str,
    quantity: int,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    _: bool = Depends(verify_api_key),
):
    """
    Place a trading order through the active broker.

    Args:
        ticker: Stock symbol
        side: 'buy' or 'sell'
        quantity: Number of shares
        order_type: 'market', 'limit', 'stop'
        limit_price: For limit orders
        stop_price: For stop orders
    """
    from src.brokers.base import OrderSide, OrderType
    from src.brokers.broker_manager import get_broker_manager

    try:
        try:
            order_side = OrderSide(side.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid side: {side}")

        try:
            order_type_enum = OrderType(order_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid order type: {order_type}"
            )

        manager = await get_broker_manager()
        result = await manager.place_order(
            ticker=ticker.upper(),
            side=order_side,
            quantity=quantity,
            order_type=order_type_enum,
            limit_price=limit_price,
            stop_price=stop_price,
        )

        return {
            "success": result.success,
            "order_id": result.order_id,
            "status": result.status.value,
            "filled_qty": result.filled_qty,
            "avg_fill_price": result.avg_fill_price,
            "message": result.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Place order error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/quote/{ticker}")
async def get_broker_quote(ticker: str, _: bool = Depends(verify_api_key)):
    """Get real-time quote for a ticker."""
    from src.brokers.broker_manager import get_broker_manager

    try:
        manager = await get_broker_manager()
        quote = await manager.get_quote(ticker.upper())

        if not quote:
            raise HTTPException(status_code=404, detail=f"Quote not found for {ticker}")

        return {
            "ticker": quote.ticker,
            "price": round(quote.price, 2),
            "bid": round(quote.bid, 2),
            "ask": round(quote.ask, 2),
            "volume": quote.volume,
            "open": round(quote.open, 2),
            "high": round(quote.high, 2),
            "low": round(quote.low, 2),
            "prev_close": round(quote.prev_close, 2),
            "change": round(quote.change, 2),
            "change_pct": round(quote.change_pct, 2),
            "timestamp": quote.timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Quote error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
