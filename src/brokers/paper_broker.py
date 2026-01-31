"""
Paper Trading Broker

Simulated trading for testing and development.
No real money involved - all trades are simulated.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict

from src.brokers.base import (
    BaseBroker, OrderRequest, OrderResult, Position,
    AccountInfo, Quote, OrderType, OrderSide, OrderStatus, Market
)

logger = logging.getLogger(__name__)


class PaperBroker(BaseBroker):
    """
    Paper Trading Broker for simulation.
    
    Features:
    - Simulated order execution
    - Virtual portfolio tracking
    - P&L calculation
    - Risk-free testing environment
    
    Configuration:
        Initial cash balance defaults to $100,000
    """
    
    def __init__(self, initial_cash: float = 100000.0):
        super().__init__("PaperTrading")
        self.initial_cash = initial_cash
        
        # Account state
        self._cash = initial_cash
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Dict] = {}
        self._order_history: List[Dict] = []
        self._trades: List[Dict] = []
        
        # Market data source (will use Alpaca for quotes)
        self._market_data = None
        
        self.is_connected = True  # Always "connected"
    
    async def connect(self) -> bool:
        """Connect to paper trading (always succeeds)."""
        self.is_connected = True
        logger.info("Paper trading mode activated")
        
        # Initialize market data source
        try:
            from src.ingestors.market_data import MarketDataIngestor
            self._market_data = MarketDataIngestor()
        except Exception as e:
            logger.warning(f"Market data source unavailable: {e}")
        
        return True
    
    async def disconnect(self):
        """Disconnect from paper trading."""
        self.is_connected = False
        logger.info("Paper trading mode deactivated")
    
    async def get_account(self) -> AccountInfo:
        """Get account information."""
        # Calculate portfolio value
        portfolio_value = self._cash
        unrealized_pnl = 0.0
        
        for pos in self._positions.values():
            portfolio_value += pos.market_value
            unrealized_pnl += pos.unrealized_pnl
        
        realized_pnl = sum(t.get('pnl', 0) for t in self._trades)
        
        return AccountInfo(
            account_id="PAPER-001",
            currency="USD",
            cash=self._cash,
            buying_power=self._cash,
            portfolio_value=portfolio_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl_today=realized_pnl
        )
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        # Update current prices
        for ticker, pos in self._positions.items():
            quote = await self.get_quote(ticker, pos.market)
            if quote:
                pos.update_price(quote.price)
        
        return list(self._positions.values())
    
    async def get_quote(self, ticker: str, market: Market = Market.US) -> Optional[Quote]:
        """Get real-time quote from Alpaca."""
        try:
            import aiohttp
            from src.core.config import get_settings
            
            settings = get_settings()
            
            if not settings.alpaca_api_key or not settings.alpaca_secret_key:
                logger.warning("Alpaca credentials not configured")
                return None
            
            # Use Alpaca data API
            url = f"https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest"
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        # Try trades endpoint as fallback
                        trade_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest"
                        async with session.get(trade_url, headers=headers) as trade_resp:
                            if trade_resp.status != 200:
                                return None
                            trade_data = await trade_resp.json()
                            trade = trade_data.get("trade", {})
                            price = float(trade.get("p", 0))
                            
                            return Quote(
                                ticker=ticker,
                                price=price,
                                bid=price,
                                ask=price,
                                volume=int(trade.get("s", 0)),
                            )
                    
                    data = await resp.json()
                    quote_data = data.get("quote", {})
                    
                    bid = float(quote_data.get("bp", 0))
                    ask = float(quote_data.get("ap", 0))
                    price = (bid + ask) / 2 if bid and ask else bid or ask
                    
                    return Quote(
                        ticker=ticker,
                        price=price,
                        bid=bid,
                        ask=ask,
                        bid_size=int(quote_data.get("bs", 0)),
                        ask_size=int(quote_data.get("as", 0)),
                    )
                    
        except Exception as e:
            logger.error(f"Quote fetch error: {e}")
            return None
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Place a simulated trading order.
        
        Market orders are filled immediately at current price.
        Limit/Stop orders are stored and checked periodically.
        """
        order_id = str(uuid.uuid4())[:8]
        
        # Get current price for market orders
        quote = await self.get_quote(order.ticker, order.market)
        
        if not quote:
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Unable to get quote for {order.ticker}"
            )
        
        current_price = quote.price
        
        # Market order - fill immediately
        if order.order_type == OrderType.MARKET:
            return await self._execute_order(order_id, order, current_price)
        
        # Limit order
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                # Buy limit - fill if price <= limit
                if current_price <= order.limit_price:
                    return await self._execute_order(order_id, order, order.limit_price)
            else:
                # Sell limit - fill if price >= limit
                if current_price >= order.limit_price:
                    return await self._execute_order(order_id, order, order.limit_price)
            
            # Store as pending
            self._orders[order_id] = {
                'order_id': order_id,
                'order': order,
                'status': OrderStatus.SUBMITTED,
                'created': datetime.now()
            }
            
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.SUBMITTED,
                message="Limit order submitted"
            )
        
        # Stop order
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY:
                # Buy stop - trigger if price >= stop
                if current_price >= order.stop_price:
                    return await self._execute_order(order_id, order, current_price)
            else:
                # Sell stop - trigger if price <= stop
                if current_price <= order.stop_price:
                    return await self._execute_order(order_id, order, current_price)
            
            # Store as pending
            self._orders[order_id] = {
                'order_id': order_id,
                'order': order,
                'status': OrderStatus.SUBMITTED,
                'created': datetime.now()
            }
            
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.SUBMITTED,
                message="Stop order submitted"
            )
        
        return OrderResult(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message=f"Unsupported order type: {order.order_type}"
        )
    
    async def _execute_order(
        self,
        order_id: str,
        order: OrderRequest,
        fill_price: float
    ) -> OrderResult:
        """Execute an order at the given price."""
        total_cost = fill_price * order.quantity
        
        # Check buying power for buys
        if order.side == OrderSide.BUY:
            if total_cost > self._cash:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"Insufficient funds. Need ${total_cost:.2f}, have ${self._cash:.2f}"
                )
            
            # Deduct cash
            self._cash -= total_cost
            
            # Update or create position
            if order.ticker in self._positions:
                pos = self._positions[order.ticker]
                # Average in
                total_qty = pos.quantity + order.quantity
                total_cost_basis = (pos.avg_price * pos.quantity) + total_cost
                pos.avg_price = total_cost_basis / total_qty
                pos.quantity = total_qty
            else:
                self._positions[order.ticker] = Position(
                    ticker=order.ticker,
                    quantity=order.quantity,
                    avg_price=fill_price,
                    current_price=fill_price,
                    market_value=total_cost,
                    market=order.market
                )
        
        # Sell order
        else:
            # Check position
            if order.ticker not in self._positions:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"No position in {order.ticker}"
                )
            
            pos = self._positions[order.ticker]
            
            if order.quantity > pos.quantity:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"Insufficient shares. Have {pos.quantity}, selling {order.quantity}"
                )
            
            # Calculate P&L
            pnl = (fill_price - pos.avg_price) * order.quantity
            
            # Add cash
            self._cash += total_cost
            
            # Update position
            pos.quantity -= order.quantity
            pos.realized_pnl += pnl
            
            if pos.quantity == 0:
                del self._positions[order.ticker]
            
            # Record trade
            self._trades.append({
                'ticker': order.ticker,
                'side': order.side.value,
                'quantity': order.quantity,
                'price': fill_price,
                'pnl': pnl,
                'timestamp': datetime.now()
            })
        
        # Record in history
        self._order_history.append({
            'order_id': order_id,
            'ticker': order.ticker,
            'side': order.side.value,
            'quantity': order.quantity,
            'fill_price': fill_price,
            'status': OrderStatus.FILLED.value,
            'timestamp': datetime.now()
        })
        
        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_qty=order.quantity,
            avg_fill_price=fill_price,
            message=f"Order filled at ${fill_price:.2f}"
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self._orders:
            self._orders[order_id]['status'] = OrderStatus.CANCELLED
            del self._orders[order_id]
            
            self._order_history.append({
                'order_id': order_id,
                'status': OrderStatus.CANCELLED.value,
                'timestamp': datetime.now()
            })
            
            return True
        return False
    
    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Dict]:
        """Get orders with optional status filter."""
        orders = []
        
        # Pending orders
        for order_id, order_data in self._orders.items():
            order = order_data['order']
            order_status = order_data['status']
            
            if status is None or order_status == status:
                orders.append({
                    'order_id': order_id,
                    'ticker': order.ticker,
                    'side': order.side.value,
                    'quantity': order.quantity,
                    'order_type': order.order_type.value,
                    'limit_price': order.limit_price,
                    'stop_price': order.stop_price,
                    'status': order_status.value,
                    'created': order_data['created'].isoformat()
                })
        
        # Order history
        if status == OrderStatus.FILLED:
            for hist in self._order_history:
                if hist.get('status') == OrderStatus.FILLED.value:
                    orders.append(hist)
        
        return orders
    
    # Paper trading specific methods
    
    def reset(self):
        """Reset account to initial state."""
        self._cash = self.initial_cash
        self._positions.clear()
        self._orders.clear()
        self._order_history.clear()
        self._trades.clear()
        logger.info("Paper trading account reset")
    
    def get_trade_history(self) -> List[Dict]:
        """Get all completed trades."""
        return self._trades.copy()
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary."""
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in self._trades if t.get('pnl', 0) < 0)
        
        total_pnl = sum(t.get('pnl', 0) for t in self._trades)
        
        # Portfolio value
        portfolio_value = self._cash
        unrealized_pnl = 0.0
        
        for pos in self._positions.values():
            portfolio_value += pos.market_value
            unrealized_pnl += pos.unrealized_pnl
        
        return {
            'initial_capital': self.initial_cash,
            'current_portfolio_value': portfolio_value,
            'cash': self._cash,
            'total_return': ((portfolio_value - self.initial_cash) / self.initial_cash) * 100,
            'realized_pnl': total_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'open_positions': len(self._positions),
        }
    
    async def check_pending_orders(self):
        """Check and fill pending orders if conditions are met."""
        to_remove = []
        
        for order_id, order_data in self._orders.items():
            order = order_data['order']
            quote = await self.get_quote(order.ticker, order.market)
            
            if not quote:
                continue
            
            current_price = quote.price
            should_fill = False
            fill_price = current_price
            
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and current_price <= order.limit_price:
                    should_fill = True
                    fill_price = order.limit_price
                elif order.side == OrderSide.SELL and current_price >= order.limit_price:
                    should_fill = True
                    fill_price = order.limit_price
            
            elif order.order_type == OrderType.STOP:
                if order.side == OrderSide.BUY and current_price >= order.stop_price:
                    should_fill = True
                elif order.side == OrderSide.SELL and current_price <= order.stop_price:
                    should_fill = True
            
            if should_fill:
                result = await self._execute_order(order_id, order, fill_price)
                if result.success:
                    to_remove.append(order_id)
        
        for order_id in to_remove:
            del self._orders[order_id]
