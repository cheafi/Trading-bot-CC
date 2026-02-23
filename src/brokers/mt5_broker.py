"""
TradingAI Bot - MetaTrader 5 Broker Integration

Connects to MetaTrader 5 terminal for:
- Forex, CFD, Crypto, Indices execution
- Real-time price feed from MT5
- Account & position management
- Trailing stops, partial closes, hedging

Requires: pip install MetaTrader5
MT5 terminal must be running (Windows or Wine on Linux/Mac).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.brokers.base import (
    AccountInfo,
    BaseBroker,
    Market,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)
from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MetaTraderBroker(BaseBroker):
    """
    MetaTrader 5 broker implementation.

    Supports Forex, CFDs, Crypto, Indices execution
    via the MetaTrader5 Python package.
    """

    # Map our generic order types to MT5 constants
    _ORDER_TYPE_MAP: Dict[str, int] = {}

    def __init__(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        mt5_path: Optional[str] = None,
    ):
        super().__init__("mt5")
        self._login = login or getattr(settings, "mt5_login", None)
        self._password = password or getattr(settings, "mt5_password", None)
        self._server = server or getattr(settings, "mt5_server", None)
        self._mt5_path = mt5_path or getattr(settings, "mt5_path", None)
        self._mt5 = None  # lazy import

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Initialize MT5 connection."""
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            self.logger.error(
                "MetaTrader5 package not installed. "
                "Run: pip install MetaTrader5  (Windows only, or use Wine)"
            )
            return False

        # Populate order type map
        self._ORDER_TYPE_MAP = {
            "buy_market": mt5.ORDER_TYPE_BUY,
            "sell_market": mt5.ORDER_TYPE_SELL,
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
            "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
        }

        init_kwargs: Dict[str, Any] = {}
        if self._mt5_path:
            init_kwargs["path"] = self._mt5_path
        if self._login:
            init_kwargs["login"] = int(self._login)
        if self._password:
            init_kwargs["password"] = self._password
        if self._server:
            init_kwargs["server"] = self._server

        if not mt5.initialize(**init_kwargs):
            error = mt5.last_error()
            self.logger.error(f"MT5 init failed: {error}")
            return False

        account = mt5.account_info()
        if account is None:
            self.logger.error("MT5: Cannot get account info")
            mt5.shutdown()
            return False

        self.is_connected = True
        self.logger.info(
            f"MT5 connected: login={account.login}, "
            f"server={account.server}, "
            f"balance={account.balance:.2f} {account.currency}"
        )
        return True

    async def disconnect(self):
        if self._mt5 and self.is_connected:
            self._mt5.shutdown()
            self.is_connected = False
            self.logger.info("MT5 disconnected")

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        if not self.is_connected:
            return AccountInfo(account_id="")
        info = self._mt5.account_info()
        if info is None:
            return AccountInfo(account_id="")
        return AccountInfo(
            account_id=str(info.login),
            portfolio_value=info.equity,
            cash=info.balance,
            buying_power=info.margin_free,
            unrealized_pnl=info.profit,
            currency=info.currency,
        )

    async def get_balance(self) -> float:
        acc = await self.get_account()
        return acc.portfolio_value or 0.0

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[Position]:
        if not self.is_connected:
            return []
        positions_raw = self._mt5.positions_get()
        if positions_raw is None:
            return []

        result: List[Position] = []
        for p in positions_raw:
            pos = Position(
                ticker=p.symbol,
                quantity=int(p.volume * 100000) if "JPY" not in p.symbol else int(p.volume * 1000),
                avg_price=p.price_open,
                current_price=p.price_current,
                market_value=p.volume * p.price_current,
                unrealized_pnl=p.profit,
                unrealized_pnl_pct=(
                    (p.price_current - p.price_open) / p.price_open * 100
                    if p.price_open > 0 else 0
                ),
                market=Market.US,
            )
            result.append(pos)
        return result

    async def get_position(self, ticker: str) -> Optional[Position]:
        positions = await self.get_positions()
        for p in positions:
            if p.ticker == ticker:
                return p
        return None

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResult:
        if not self.is_connected:
            return OrderResult(success=False, message="MT5 not connected")

        mt5 = self._mt5
        symbol = order.ticker.upper()

        # Ensure symbol is available
        if not mt5.symbol_select(symbol, True):
            return OrderResult(
                success=False,
                message=f"Symbol {symbol} not found in MT5",
            )

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(success=False, message=f"No tick data for {symbol}")

        # Determine price and order type
        if order.order_type == OrderType.MARKET:
            if order.side == OrderSide.BUY:
                price = tick.ask
                mt5_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                mt5_type = mt5.ORDER_TYPE_SELL
        elif order.order_type == OrderType.LIMIT:
            price = order.limit_price or (tick.ask if order.side == OrderSide.BUY else tick.bid)
            mt5_type = (
                mt5.ORDER_TYPE_BUY_LIMIT
                if order.side == OrderSide.BUY
                else mt5.ORDER_TYPE_SELL_LIMIT
            )
        elif order.order_type == OrderType.STOP:
            price = order.stop_price or (tick.ask if order.side == OrderSide.BUY else tick.bid)
            mt5_type = (
                mt5.ORDER_TYPE_BUY_STOP
                if order.side == OrderSide.BUY
                else mt5.ORDER_TYPE_SELL_STOP
            )
        else:
            return OrderResult(
                success=False,
                message=f"Unsupported order type: {order.order_type}",
            )

        # Convert quantity to lots (MT5 uses lot sizes)
        symbol_info = mt5.symbol_info(symbol)
        lot_size = order.quantity
        if symbol_info:
            lot_size = max(symbol_info.volume_min, round(order.quantity * symbol_info.volume_step, 2))

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order.order_type == OrderType.MARKET else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": mt5_type,
            "price": price,
            "deviation": 20,  # slippage in points
            "magic": 234000,
            "comment": "TradingAI Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Add SL/TP if provided
        if order.stop_price and order.order_type == OrderType.MARKET:
            request["sl"] = order.stop_price
        if order.limit_price and order.order_type == OrderType.MARKET:
            request["tp"] = order.limit_price

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(success=False, message="MT5 order_send returned None")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(
                success=False,
                status=OrderStatus.REJECTED,
                message=f"MT5 error {result.retcode}: {result.comment}",
                raw_response=result._asdict() if hasattr(result, "_asdict") else {},
            )

        return OrderResult(
            success=True,
            order_id=str(result.order),
            status=OrderStatus.FILLED,
            filled_qty=order.quantity,
            avg_fill_price=result.price,
            message=f"Filled at {result.price}",
            timestamp=datetime.now(timezone.utc),
        )

    async def cancel_order(self, order_id: str) -> bool:
        if not self.is_connected:
            return False
        mt5 = self._mt5
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(order_id),
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    async def get_orders(
        self, status: Optional[OrderStatus] = None
    ) -> List[Dict]:
        """Get pending orders from MT5, optionally filtered by status."""
        if not self.is_connected:
            return []
        mt5 = self._mt5
        orders = mt5.orders_get()
        if orders is None:
            return []

        result: List[Dict] = []
        for o in orders:
            order_dict: Dict[str, Any] = {
                "order_id": str(o.ticket),
                "ticker": o.symbol,
                "side": "buy" if o.type in (0, 2, 4) else "sell",
                "quantity": o.volume_current,
                "order_type": "limit" if o.type in (2, 3) else "stop",
                "price": o.price_open,
                "status": OrderStatus.SUBMITTED.value,
                "time": datetime.fromtimestamp(
                    o.time_setup, tz=timezone.utc
                ).isoformat(),
                "comment": o.comment,
            }
            if status is None or order_dict["status"] == status.value:
                result.append(order_dict)
        return result

    async def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        if not self.is_connected:
            return None
        mt5 = self._mt5
        orders = mt5.orders_get(ticket=int(order_id))
        if orders:
            o = orders[0]
            return OrderResult(
                success=True,
                order_id=str(o.ticket),
                status=OrderStatus.SUBMITTED,
                message=f"Pending: {o.comment}",
            )
        # Check history
        deals = mt5.history_deals_get(ticket=int(order_id))
        if deals:
            d = deals[0]
            return OrderResult(
                success=True,
                order_id=str(d.ticket),
                status=OrderStatus.FILLED,
                avg_fill_price=d.price,
                filled_qty=int(d.volume),
                message="Filled",
            )
        return None

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_quote(
        self, ticker: str, market: Market = Market.US
    ) -> Optional[Quote]:
        if not self.is_connected:
            return None
        mt5 = self._mt5
        tick = mt5.symbol_info_tick(ticker)
        if tick is None:
            return None
        return Quote(
            ticker=ticker,
            price=tick.last,
            bid=tick.bid,
            ask=tick.ask,
            volume=tick.volume,
            timestamp=datetime.fromtimestamp(
                tick.time, tz=timezone.utc
            ),
        )

    async def get_historical(
        self,
        ticker: str,
        timeframe: str = "D1",
        count: int = 500,
    ) -> Optional[Any]:
        """Get OHLCV bars from MT5."""
        if not self.is_connected:
            return None
        mt5 = self._mt5

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
        }
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_D1)
        rates = mt5.copy_rates_from_pos(ticker, mt5_tf, 0, count)
        if rates is None:
            return None

        import pandas as pd
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(
            columns={
                "time": "ts",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "tick_volume": "volume",
            },
            inplace=True,
        )
        return df

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def get_order_history(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if not self.is_connected:
            return []
        mt5 = self._mt5
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        deals = mt5.history_deals_get(now - timedelta(days=30), now)
        if deals is None:
            return []
        result = []
        for d in deals:
            if ticker and d.symbol != ticker:
                continue
            result.append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "type": d.type,
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "commission": d.commission,
                "swap": d.swap,
                "time": datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
                "comment": d.comment,
            })
        return result[:limit]
