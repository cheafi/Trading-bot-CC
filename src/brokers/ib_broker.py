"""
Interactive Brokers (IB) Connector

Connects to IB TWS or IB Gateway for trading on:
- US Markets (NYSE, NASDAQ, AMEX)
- European Markets
- Asian Markets
- Futures, Options, Forex

Requirements:
- IB TWS or IB Gateway running
- pip install ib_insync

Documentation: https://ib-insync.readthedocs.io/
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.brokers.base import (
    BaseBroker,
    OrderRequest,
    OrderResult,
    Position,
    AccountInfo,
    Quote,
    OrderType,
    OrderSide,
    OrderStatus,
    Market,
)
from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

try:
    from src.core.errors import BrokerError
except ImportError:

    class BrokerError(Exception):
        pass


class IBBroker(BaseBroker):
    """
    Interactive Brokers Connector using ib_insync.

    Supports comprehensive trading across global markets.

    Configuration (.env):
        IB_HOST=127.0.0.1
        IB_PORT=7497 (TWS) or 4001 (Gateway)
        IB_CLIENT_ID=1
        IB_ACCOUNT=your_account_id (optional, auto-detected)
    """

    def __init__(self):
        super().__init__("InteractiveBrokers")
        self.host = getattr(settings, "ib_host", "127.0.0.1")
        self.port = getattr(settings, "ib_port", 7497)
        self.client_id = getattr(settings, "ib_client_id", 1)
        self.account = getattr(settings, "ib_account", "")

        self._ib = None
        self._ib_insync_available = False

        # Try to import ib_insync
        try:
            from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder, StopOrder
            from ib_insync import util

            self._ib_insync = __import__("ib_insync")
            self._ib_insync_available = True
        except ImportError:
            logger.warning("ib_insync not installed. Run: pip install ib_insync")
            self._ib_insync = None

    @property
    def is_available(self) -> bool:
        """Check if ib_insync is available."""
        return self._ib_insync_available

    async def connect(self) -> bool:
        """Connect to IB TWS or Gateway."""
        if not self._ib_insync_available:
            logger.error("ib_insync not available. Install with: pip install ib_insync")
            raise BrokerError(message="Connection failed", broker=self.name)

        try:
            self._ib = self._ib_insync.IB()

            # ib_insync has its own event loop handling
            await self._ib.connectAsync(
                host=self.host, port=self.port, clientId=self.client_id
            )

            # Auto-detect account if not specified
            if not self.account:
                accounts = self._ib.managedAccounts()
                if accounts:
                    self.account = accounts[0]
                    logger.info(f"Using IB account: {self.account}")

            self.is_connected = True
            logger.info(f"Connected to Interactive Brokers at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"IB connection error: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from IB."""
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

        self.is_connected = False
        logger.info("Disconnected from Interactive Brokers")

    async def get_account(self) -> AccountInfo:
        """Get account information."""
        if not self.is_connected or not self._ib:
            return AccountInfo(account_id="", cash=0, buying_power=0)

        try:
            # Get account values
            account_values = self._ib.accountValues(self.account)

            # Parse account values
            cash = 0.0
            buying_power = 0.0
            portfolio_value = 0.0
            unrealized_pnl = 0.0
            realized_pnl = 0.0

            for av in account_values:
                if av.tag == "AvailableFunds" and av.currency == "USD":
                    cash = float(av.value)
                elif av.tag == "BuyingPower" and av.currency == "USD":
                    buying_power = float(av.value)
                elif av.tag == "NetLiquidation" and av.currency == "USD":
                    portfolio_value = float(av.value)
                elif av.tag == "UnrealizedPnL" and av.currency == "USD":
                    unrealized_pnl = float(av.value)
                elif av.tag == "RealizedPnL" and av.currency == "USD":
                    realized_pnl = float(av.value)

            return AccountInfo(
                account_id=self.account,
                currency="USD",
                cash=cash,
                buying_power=buying_power,
                portfolio_value=portfolio_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl_today=realized_pnl,
            )

        except Exception as e:
            logger.error(f"Get IB account error: {e}")
            return AccountInfo(account_id=self.account, cash=0)

    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self.is_connected or not self._ib:
            return []

        positions = []

        try:
            ib_positions = self._ib.positions(self.account)

            for pos in ib_positions:
                contract = pos.contract
                ticker = contract.symbol

                # Determine market
                market = Market.US
                if contract.exchange in ["SEHK", "HKFE"]:
                    market = Market.HK
                elif contract.exchange in ["SSE", "SZSE"]:
                    market = Market.CN

                position = Position(
                    ticker=ticker,
                    quantity=int(pos.position),
                    avg_price=float(pos.avgCost),
                    current_price=0.0,  # Need separate quote call
                    market_value=float(pos.position * pos.avgCost),
                    market=market,
                )

                # Get current price
                quote = await self.get_quote(ticker, market)
                if quote:
                    position.update_price(quote.price)

                positions.append(position)

        except Exception as e:
            logger.error(f"Get IB positions error: {e}")

        return positions

    async def get_quote(
        self, ticker: str, market: Market = Market.US
    ) -> Optional[Quote]:
        """Get real-time quote."""
        if not self.is_connected or not self._ib:
            return None

        try:
            # Create contract
            contract = self._create_contract(ticker, market)

            # Qualify the contract
            await self._ib.qualifyContractsAsync(contract)

            # Request market data
            self._ib.reqMktData(contract)
            await asyncio.sleep(0.5)  # Wait for data

            ticker_obj = self._ib.ticker(contract)
            if not ticker_obj:
                return None

            return Quote(
                ticker=ticker,
                price=float(ticker_obj.last or ticker_obj.close or 0),
                bid=float(ticker_obj.bid or 0),
                ask=float(ticker_obj.ask or 0),
                bid_size=int(ticker_obj.bidSize or 0),
                ask_size=int(ticker_obj.askSize or 0),
                volume=int(ticker_obj.volume or 0),
                open=float(ticker_obj.open or 0),
                high=float(ticker_obj.high or 0),
                low=float(ticker_obj.low or 0),
                prev_close=float(ticker_obj.close or 0),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Get IB quote error for {ticker}: {e}")
            return None

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a trading order."""
        if not self.is_connected or not self._ib:
            raise BrokerError(
                message="place_order called but IBBroker is not connected — "
                "call connect() first or check TWS/Gateway is running",
                broker=self.name,
            )

        try:
            # Create contract
            contract = self._create_contract(order.ticker, order.market)
            await self._ib.qualifyContractsAsync(contract)

            # Create order
            ib_order = self._create_order(order)

            # Place order
            trade = self._ib.placeOrder(contract, ib_order)

            # Wait for order to be submitted
            await asyncio.sleep(0.5)

            return OrderResult(
                success=True,
                order_id=str(trade.order.orderId),
                status=self._map_ib_status(trade.orderStatus.status),
                filled_qty=int(trade.orderStatus.filled),
                avg_fill_price=(
                    float(trade.orderStatus.avgFillPrice)
                    if trade.orderStatus.avgFillPrice
                    else None
                ),
                message="Order placed successfully",
            )

        except Exception as e:
            logger.error(f"IB place order error: {e}")
            return OrderResult(success=False, message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if not self.is_connected or not self._ib:
            return False

        try:
            # Find the order
            open_orders = self._ib.openOrders()
            for order in open_orders:
                if str(order.orderId) == order_id:
                    self._ib.cancelOrder(order)
                    return True

            logger.warning(f"Order {order_id} not found")
            return False

        except Exception as e:
            logger.error(f"IB cancel order error: {e}")
            return False

    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Dict]:
        """Get orders."""
        if not self.is_connected or not self._ib:
            return []

        orders = []

        try:
            # Get open orders
            open_orders = self._ib.openOrders()

            for order in open_orders:
                trade = self._ib.trades().get(order.orderId)
                order_status = self._map_ib_status(
                    trade.orderStatus.status if trade else "Submitted"
                )

                if status is None or order_status == status:
                    orders.append(
                        {
                            "order_id": str(order.orderId),
                            "ticker": (
                                order.contract.symbol
                                if hasattr(order, "contract")
                                else ""
                            ),
                            "side": "buy" if order.action == "BUY" else "sell",
                            "quantity": int(order.totalQuantity),
                            "filled_qty": int(trade.orderStatus.filled) if trade else 0,
                            "price": (
                                float(order.lmtPrice)
                                if hasattr(order, "lmtPrice")
                                else 0
                            ),
                            "status": order_status.value,
                        }
                    )

            # Get filled orders from executions
            if status is None or status == OrderStatus.FILLED:
                fills = self._ib.fills()
                for fill in fills:
                    orders.append(
                        {
                            "order_id": str(fill.execution.orderId),
                            "ticker": fill.contract.symbol,
                            "side": "buy" if fill.execution.side == "BOT" else "sell",
                            "quantity": int(fill.execution.shares),
                            "filled_qty": int(fill.execution.shares),
                            "avg_fill_price": float(fill.execution.avgPrice),
                            "status": OrderStatus.FILLED.value,
                            "fill_time": fill.execution.time,
                        }
                    )

        except Exception as e:
            logger.error(f"Get IB orders error: {e}")

        return orders

    def _create_contract(self, ticker: str, market: Market):
        """Create IB contract."""
        Stock = self._ib_insync.Stock

        # Determine exchange based on market
        exchange_map = {
            Market.US: "SMART",
            Market.HK: "SEHK",
            Market.CN: "SSE",  # or SZSE
        }

        currency_map = {
            Market.US: "USD",
            Market.HK: "HKD",
            Market.CN: "CNY",
        }

        return Stock(
            symbol=ticker,
            exchange=exchange_map.get(market, "SMART"),
            currency=currency_map.get(market, "USD"),
        )

    def _create_order(self, order: OrderRequest):
        """Create IB order object."""
        action = "BUY" if order.side == OrderSide.BUY else "SELL"

        if order.order_type == OrderType.MARKET:
            return self._ib_insync.MarketOrder(
                action=action, totalQuantity=order.quantity
            )
        elif order.order_type == OrderType.LIMIT:
            return self._ib_insync.LimitOrder(
                action=action, totalQuantity=order.quantity, lmtPrice=order.limit_price
            )
        elif order.order_type == OrderType.STOP:
            return self._ib_insync.StopOrder(
                action=action, totalQuantity=order.quantity, stopPrice=order.stop_price
            )
        elif order.order_type == OrderType.STOP_LIMIT:
            order_obj = self._ib_insync.Order(
                action=action,
                totalQuantity=order.quantity,
                orderType="STP LMT",
                lmtPrice=order.limit_price,
                auxPrice=order.stop_price,
            )
            return order_obj
        elif order.order_type == OrderType.TRAILING_STOP:
            return self._ib_insync.Order(
                action=action,
                totalQuantity=order.quantity,
                orderType="TRAIL",
                trailingPercent=order.trailing_pct,
            )
        else:
            return self._ib_insync.MarketOrder(
                action=action, totalQuantity=order.quantity
            )

    def _map_ib_status(self, ib_status: str) -> OrderStatus:
        """Map IB order status to OrderStatus enum."""
        status_map = {
            "PendingSubmit": OrderStatus.PENDING,
            "PendingCancel": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.PENDING,
            "Submitted": OrderStatus.SUBMITTED,
            "Cancelled": OrderStatus.CANCELLED,
            "Filled": OrderStatus.FILLED,
            "Inactive": OrderStatus.REJECTED,
            "ApiPending": OrderStatus.PENDING,
            "ApiCancelled": OrderStatus.CANCELLED,
        }
        return status_map.get(ib_status, OrderStatus.PENDING)

    # IB-specific methods

    async def get_contract_details(
        self, ticker: str, market: Market = Market.US
    ) -> Optional[Dict]:
        """Get detailed contract information."""
        if not self.is_connected:
            return None

        try:
            contract = self._create_contract(ticker, market)
            details = await self._ib.reqContractDetailsAsync(contract)

            if details:
                d = details[0]
                return {
                    "ticker": ticker,
                    "name": d.longName,
                    "industry": d.industry,
                    "category": d.category,
                    "subcategory": d.subcategory,
                    "exchange": d.contract.exchange,
                    "currency": d.contract.currency,
                    "min_tick": d.minTick,
                    "trading_hours": d.tradingHours,
                }
            return None

        except Exception as e:
            logger.error(f"Get contract details error: {e}")
            return None

    async def get_historical_data(
        self,
        ticker: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        market: Market = Market.US,
    ) -> Optional[List[Dict]]:
        """Get historical OHLCV data."""
        if not self.is_connected:
            return None

        try:
            contract = self._create_contract(ticker, market)
            await self._ib.qualifyContractsAsync(contract)

            bars = await self._ib.reqHistoricalDataAsync(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
            )

            data = []
            for bar in bars:
                data.append(
                    {
                        "date": bar.date,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                    }
                )

            return data

        except Exception as e:
            logger.error(f"Get historical data error: {e}")
            return None

    async def subscribe_realtime(
        self, tickers: List[str], market: Market = Market.US, callback=None
    ):
        """Subscribe to real-time market data."""
        if not self.is_connected:
            return False

        try:
            for ticker in tickers:
                contract = self._create_contract(ticker, market)
                await self._ib.qualifyContractsAsync(contract)

                # Request streaming data
                self._ib.reqMktData(contract, "", False, False)

                if callback:
                    self._ib.pendingTickersEvent += lambda tickers: callback(tickers)

            return True

        except Exception as e:
            logger.error(f"Subscribe realtime error: {e}")
            return False

    async def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary with Greeks for options."""
        if not self.is_connected:
            return {}

        try:
            portfolio = self._ib.portfolio(self.account)

            summary = {
                "positions": [],
                "total_value": 0.0,
                "total_unrealized_pnl": 0.0,
                "total_realized_pnl": 0.0,
            }

            for item in portfolio:
                pos_dict = {
                    "ticker": item.contract.symbol,
                    "sec_type": item.contract.secType,
                    "quantity": int(item.position),
                    "market_value": float(item.marketValue),
                    "avg_cost": float(item.averageCost),
                    "unrealized_pnl": float(item.unrealizedPNL),
                    "realized_pnl": float(item.realizedPNL),
                }
                summary["positions"].append(pos_dict)
                summary["total_value"] += float(item.marketValue)
                summary["total_unrealized_pnl"] += float(item.unrealizedPNL)
                summary["total_realized_pnl"] += float(item.realizedPNL)

            return summary

        except Exception as e:
            logger.error(f"Get portfolio summary error: {e}")
            return {}
