"""
Futu Broker Connector (富途)

Connects to Futu OpenD Gateway for trading on:
- Hong Kong Stock Exchange (HKEX)
- US Markets (NYSE, NASDAQ)
- A-Shares (Shanghai, Shenzhen)

Requirements:
- Futu OpenD running locally or remotely
- pip install futu-api

Documentation: https://openapi.futunn.com/
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.brokers.base import (
    BaseBroker, OrderRequest, OrderResult, Position, 
    AccountInfo, Quote, OrderType, OrderSide, OrderStatus, Market
)
from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class FutuBroker(BaseBroker):
    """
    Futu OpenD Broker Connector.
    
    Supports trading on Hong Kong and US markets through Futu's API.
    
    Configuration (.env):
        FUTU_HOST=127.0.0.1
        FUTU_PORT=11111
        FUTU_RSA_FILE=path/to/rsa_private_key.txt (optional for encryption)
        FUTU_TRADE_PASSWORD=your_trade_password
        FUTU_TRADE_UNLOCK_PIN=your_unlock_pin (for HK market)
    """
    
    # Market code mappings
    MARKET_CODES = {
        Market.US: "US",
        Market.HK: "HK",
        Market.CN: "SH",  # Shanghai, use "SZ" for Shenzhen
    }
    
    # Order type mappings
    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",  # Will be converted to Futu enum
        OrderType.LIMIT: "NORMAL",
        OrderType.STOP: "STOP",
        OrderType.STOP_LIMIT: "STOP_LIMIT",
    }
    
    def __init__(self):
        super().__init__("Futu")
        self.host = getattr(settings, 'futu_host', '127.0.0.1')
        self.port = getattr(settings, 'futu_port', 11111)
        self.trade_password = getattr(settings, 'futu_trade_password', '')
        self.unlock_pin = getattr(settings, 'futu_unlock_pin', '')
        
        self._quote_ctx = None
        self._trade_ctx_us = None
        self._trade_ctx_hk = None
        self._futu_available = False
        
        # Try to import futu-api
        try:
            import futu
            self._futu = futu
            self._futu_available = True
        except ImportError:
            logger.warning("futu-api not installed. Run: pip install futu-api")
            self._futu = None
    
    @property
    def is_available(self) -> bool:
        """Check if Futu API is available."""
        return self._futu_available
    
    async def connect(self) -> bool:
        """Connect to Futu OpenD Gateway."""
        if not self._futu_available:
            logger.error("Futu API not available. Install with: pip install futu-api")
            return False
        
        try:
            # Connect in thread pool (Futu API is synchronous)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._connect_sync)
            return success
        except Exception as e:
            logger.error(f"Futu connection error: {e}")
            return False
    
    def _connect_sync(self) -> bool:
        """Synchronous connection to Futu."""
        try:
            # Quote context for market data
            self._quote_ctx = self._futu.OpenQuoteContext(
                host=self.host,
                port=self.port
            )
            
            # Trade contexts for different markets
            self._trade_ctx_us = self._futu.OpenUSTradeContext(
                host=self.host,
                port=self.port
            )
            self._trade_ctx_hk = self._futu.OpenHKTradeContext(
                host=self.host,
                port=self.port
            )
            
            # Unlock trade (required for placing orders)
            if self.trade_password:
                ret, data = self._trade_ctx_us.unlock_trade(self.trade_password)
                if ret != 0:
                    logger.warning(f"Failed to unlock US trade: {data}")
                
                ret, data = self._trade_ctx_hk.unlock_trade(self.trade_password)
                if ret != 0:
                    logger.warning(f"Failed to unlock HK trade: {data}")
            
            self.is_connected = True
            logger.info("Connected to Futu OpenD Gateway")
            return True
            
        except Exception as e:
            logger.error(f"Futu sync connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Futu."""
        if self._quote_ctx:
            self._quote_ctx.close()
        if self._trade_ctx_us:
            self._trade_ctx_us.close()
        if self._trade_ctx_hk:
            self._trade_ctx_hk.close()
        
        self.is_connected = False
        logger.info("Disconnected from Futu")
    
    async def get_account(self) -> AccountInfo:
        """Get account information."""
        if not self.is_connected:
            return AccountInfo(account_id="", cash=0, buying_power=0)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_account_sync)
    
    def _get_account_sync(self) -> AccountInfo:
        """Get account info synchronously."""
        try:
            # Get US account info
            ret, data = self._trade_ctx_us.accinfo_query()
            if ret == 0 and len(data) > 0:
                acc = data.iloc[0]
                return AccountInfo(
                    account_id=str(acc.get('trd_acc_id', '')),
                    currency="USD",
                    cash=float(acc.get('cash', 0)),
                    buying_power=float(acc.get('avl_withdrawal_cash', 0)),
                    portfolio_value=float(acc.get('total_assets', 0)),
                    unrealized_pnl=float(acc.get('unrealized_pl', 0)),
                    margin_used=float(acc.get('used_margin', 0)),
                )
            
            return AccountInfo(account_id="", cash=0)
            
        except Exception as e:
            logger.error(f"Get account error: {e}")
            return AccountInfo(account_id="", cash=0)
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self.is_connected:
            return []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_positions_sync)
    
    def _get_positions_sync(self) -> List[Position]:
        """Get positions synchronously."""
        positions = []
        
        try:
            # Get US positions
            ret, data = self._trade_ctx_us.position_list_query()
            if ret == 0 and len(data) > 0:
                for _, row in data.iterrows():
                    pos = Position(
                        ticker=row.get('code', '').replace('US.', ''),
                        quantity=int(row.get('qty', 0)),
                        avg_price=float(row.get('cost_price', 0)),
                        current_price=float(row.get('market_val', 0)) / max(int(row.get('qty', 1)), 1),
                        market_value=float(row.get('market_val', 0)),
                        unrealized_pnl=float(row.get('pl_val', 0)),
                        unrealized_pnl_pct=float(row.get('pl_ratio', 0)) * 100,
                        market=Market.US
                    )
                    positions.append(pos)
            
            # Get HK positions
            ret, data = self._trade_ctx_hk.position_list_query()
            if ret == 0 and len(data) > 0:
                for _, row in data.iterrows():
                    pos = Position(
                        ticker=row.get('code', '').replace('HK.', ''),
                        quantity=int(row.get('qty', 0)),
                        avg_price=float(row.get('cost_price', 0)),
                        current_price=float(row.get('market_val', 0)) / max(int(row.get('qty', 1)), 1),
                        market_value=float(row.get('market_val', 0)),
                        unrealized_pnl=float(row.get('pl_val', 0)),
                        unrealized_pnl_pct=float(row.get('pl_ratio', 0)) * 100,
                        market=Market.HK
                    )
                    positions.append(pos)
                    
        except Exception as e:
            logger.error(f"Get positions error: {e}")
        
        return positions
    
    async def get_quote(self, ticker: str, market: Market = Market.US) -> Optional[Quote]:
        """Get real-time quote."""
        if not self.is_connected:
            return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_quote_sync, ticker, market)
    
    def _get_quote_sync(self, ticker: str, market: Market) -> Optional[Quote]:
        """Get quote synchronously."""
        try:
            # Format ticker for Futu (e.g., "US.AAPL", "HK.00700")
            futu_ticker = self.format_ticker(ticker, market)
            
            ret, data = self._quote_ctx.get_stock_quote([futu_ticker])
            if ret != 0 or len(data) == 0:
                return None
            
            row = data.iloc[0]
            
            return Quote(
                ticker=ticker,
                price=float(row.get('last_price', 0)),
                bid=float(row.get('bid_price', 0)),
                ask=float(row.get('ask_price', 0)),
                bid_size=int(row.get('bid_vol', 0)),
                ask_size=int(row.get('ask_vol', 0)),
                volume=int(row.get('volume', 0)),
                open=float(row.get('open_price', 0)),
                high=float(row.get('high_price', 0)),
                low=float(row.get('low_price', 0)),
                prev_close=float(row.get('prev_close_price', 0)),
                change=float(row.get('price_spread', 0)),
                change_pct=float(row.get('amplitude', 0)),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Get quote error for {ticker}: {e}")
            return None
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a trading order."""
        if not self.is_connected:
            return OrderResult(success=False, message="Not connected to Futu")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._place_order_sync, order)
    
    def _place_order_sync(self, order: OrderRequest) -> OrderResult:
        """Place order synchronously."""
        try:
            # Select trade context based on market
            trade_ctx = self._trade_ctx_us if order.market == Market.US else self._trade_ctx_hk
            
            # Format ticker
            futu_ticker = self.format_ticker(order.ticker, order.market)
            
            # Map order type
            order_type = self._futu.OrderType.NORMAL
            if order.order_type == OrderType.MARKET:
                order_type = self._futu.OrderType.MARKET
            elif order.order_type == OrderType.LIMIT:
                order_type = self._futu.OrderType.NORMAL
            elif order.order_type == OrderType.STOP:
                order_type = self._futu.OrderType.STOP
            
            # Map trade side
            trade_side = self._futu.TrdSide.BUY if order.side == OrderSide.BUY else self._futu.TrdSide.SELL
            
            # Place order
            price = order.limit_price if order.limit_price else 0
            
            ret, data = trade_ctx.place_order(
                price=price,
                qty=order.quantity,
                code=futu_ticker,
                trd_side=trade_side,
                order_type=order_type
            )
            
            if ret == 0 and len(data) > 0:
                order_info = data.iloc[0]
                return OrderResult(
                    success=True,
                    order_id=str(order_info.get('order_id', '')),
                    status=OrderStatus.SUBMITTED,
                    message="Order placed successfully"
                )
            else:
                return OrderResult(
                    success=False,
                    message=f"Order failed: {data}"
                )
                
        except Exception as e:
            logger.error(f"Place order error: {e}")
            return OrderResult(success=False, message=str(e))
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if not self.is_connected:
            return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._cancel_order_sync, order_id)
    
    def _cancel_order_sync(self, order_id: str) -> bool:
        """Cancel order synchronously."""
        try:
            # Try US market first
            ret, data = self._trade_ctx_us.modify_order(
                modify_order_op=self._futu.ModifyOrderOp.CANCEL,
                order_id=order_id,
                qty=0,
                price=0
            )
            
            if ret == 0:
                return True
            
            # Try HK market
            ret, data = self._trade_ctx_hk.modify_order(
                modify_order_op=self._futu.ModifyOrderOp.CANCEL,
                order_id=order_id,
                qty=0,
                price=0
            )
            
            return ret == 0
            
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False
    
    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Dict]:
        """Get orders."""
        if not self.is_connected:
            return []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_orders_sync, status)
    
    def _get_orders_sync(self, status: Optional[OrderStatus]) -> List[Dict]:
        """Get orders synchronously."""
        orders = []
        
        try:
            # Get US orders
            ret, data = self._trade_ctx_us.order_list_query()
            if ret == 0 and len(data) > 0:
                for _, row in data.iterrows():
                    order_status = self._map_futu_status(row.get('order_status', ''))
                    if status is None or order_status == status:
                        orders.append({
                            'order_id': str(row.get('order_id', '')),
                            'ticker': row.get('code', '').replace('US.', ''),
                            'side': 'buy' if row.get('trd_side') == 'BUY' else 'sell',
                            'quantity': int(row.get('qty', 0)),
                            'filled_qty': int(row.get('dealt_qty', 0)),
                            'price': float(row.get('price', 0)),
                            'avg_fill_price': float(row.get('dealt_avg_price', 0)),
                            'status': order_status.value,
                            'market': 'US',
                            'created_time': row.get('create_time', ''),
                        })
            
            # Get HK orders
            ret, data = self._trade_ctx_hk.order_list_query()
            if ret == 0 and len(data) > 0:
                for _, row in data.iterrows():
                    order_status = self._map_futu_status(row.get('order_status', ''))
                    if status is None or order_status == status:
                        orders.append({
                            'order_id': str(row.get('order_id', '')),
                            'ticker': row.get('code', '').replace('HK.', ''),
                            'side': 'buy' if row.get('trd_side') == 'BUY' else 'sell',
                            'quantity': int(row.get('qty', 0)),
                            'filled_qty': int(row.get('dealt_qty', 0)),
                            'price': float(row.get('price', 0)),
                            'avg_fill_price': float(row.get('dealt_avg_price', 0)),
                            'status': order_status.value,
                            'market': 'HK',
                            'created_time': row.get('create_time', ''),
                        })
                        
        except Exception as e:
            logger.error(f"Get orders error: {e}")
        
        return orders
    
    def _map_futu_status(self, futu_status: str) -> OrderStatus:
        """Map Futu order status to OrderStatus enum."""
        status_map = {
            'UNSUBMITTED': OrderStatus.PENDING,
            'SUBMITTING': OrderStatus.PENDING,
            'SUBMITTED': OrderStatus.SUBMITTED,
            'FILLED_PART': OrderStatus.PARTIAL,
            'FILLED_ALL': OrderStatus.FILLED,
            'CANCELLED_PART': OrderStatus.CANCELLED,
            'CANCELLED_ALL': OrderStatus.CANCELLED,
            'FAILED': OrderStatus.REJECTED,
            'DISABLED': OrderStatus.REJECTED,
            'DELETED': OrderStatus.CANCELLED,
        }
        return status_map.get(futu_status, OrderStatus.PENDING)
    
    def format_ticker(self, ticker: str, market: Market) -> str:
        """Format ticker for Futu API."""
        market_prefix = self.MARKET_CODES.get(market, "US")
        ticker = ticker.upper()
        
        # If already has prefix, return as is
        if ticker.startswith(f"{market_prefix}."):
            return ticker
        
        return f"{market_prefix}.{ticker}"
    
    # Additional Futu-specific methods
    
    async def get_market_snapshot(self, tickers: List[str], market: Market = Market.US) -> List[Quote]:
        """Get market snapshot for multiple tickers."""
        if not self.is_connected:
            return []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_market_snapshot_sync, tickers, market)
    
    def _get_market_snapshot_sync(self, tickers: List[str], market: Market) -> List[Quote]:
        """Get market snapshot synchronously."""
        quotes = []
        
        try:
            futu_tickers = [self.format_ticker(t, market) for t in tickers]
            ret, data = self._quote_ctx.get_stock_quote(futu_tickers)
            
            if ret == 0:
                for _, row in data.iterrows():
                    code = row.get('code', '')
                    ticker = code.split('.')[-1] if '.' in code else code
                    
                    quotes.append(Quote(
                        ticker=ticker,
                        price=float(row.get('last_price', 0)),
                        bid=float(row.get('bid_price', 0)),
                        ask=float(row.get('ask_price', 0)),
                        volume=int(row.get('volume', 0)),
                        open=float(row.get('open_price', 0)),
                        high=float(row.get('high_price', 0)),
                        low=float(row.get('low_price', 0)),
                        prev_close=float(row.get('prev_close_price', 0)),
                    ))
                    
        except Exception as e:
            logger.error(f"Get market snapshot error: {e}")
        
        return quotes
    
    async def subscribe_realtime(self, tickers: List[str], market: Market = Market.US, callback=None):
        """Subscribe to real-time quotes (push updates)."""
        if not self.is_connected:
            return False
        
        try:
            futu_tickers = [self.format_ticker(t, market) for t in tickers]
            ret, data = self._quote_ctx.subscribe(
                futu_tickers,
                [self._futu.SubType.QUOTE],
                subscribe_push=True
            )
            
            if ret == 0 and callback:
                # Set up callback handler
                class QuoteHandler(self._futu.StockQuoteHandlerBase):
                    def on_recv_rsp(handler_self, rsp_pb):
                        ret, data = super().on_recv_rsp(rsp_pb)
                        if ret == 0:
                            callback(data)
                        return ret, data
                
                self._quote_ctx.set_handler(QuoteHandler())
                self._quote_ctx.start()
            
            return ret == 0
            
        except Exception as e:
            logger.error(f"Subscribe realtime error: {e}")
            return False
