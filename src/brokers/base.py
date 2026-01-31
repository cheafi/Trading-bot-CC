"""
Base Broker Interface

Abstract base class for all broker implementations.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Market(str, Enum):
    """Trading markets."""
    US = "us"
    HK = "hk"
    CN = "cn"
    CRYPTO = "crypto"


@dataclass
class OrderRequest:
    """Order request details."""
    ticker: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trailing_pct: Optional[float] = None
    time_in_force: str = "day"  # day, gtc, ioc, fok
    market: Market = Market.US
    extended_hours: bool = False


@dataclass
class OrderResult:
    """Order execution result."""
    success: bool
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: Optional[float] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: Optional[Dict] = None


@dataclass
class Position:
    """Portfolio position."""
    ticker: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    market: Market = Market.US
    
    def update_price(self, price: float):
        """Update current price and recalculate P&L."""
        self.current_price = price
        self.market_value = price * self.quantity
        cost_basis = self.avg_price * self.quantity
        self.unrealized_pnl = self.market_value - cost_basis
        if cost_basis > 0:
            self.unrealized_pnl_pct = (self.unrealized_pnl / cost_basis) * 100


@dataclass
class AccountInfo:
    """Account information."""
    account_id: str
    currency: str = "USD"
    cash: float = 0.0
    buying_power: float = 0.0
    portfolio_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0


@dataclass
class Quote:
    """Market quote."""
    ticker: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class BaseBroker(ABC):
    """
    Abstract base class for broker implementations.
    
    All broker connectors must implement these methods.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.is_connected = False
        self.logger = logging.getLogger(f"broker.{name}")
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from broker."""
        pass
    
    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """
        Get account information.
        
        Returns:
            AccountInfo with balances and buying power
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    async def get_quote(self, ticker: str, market: Market = Market.US) -> Optional[Quote]:
        """
        Get real-time quote for a ticker.
        
        Args:
            ticker: Stock symbol
            market: Trading market
            
        Returns:
            Quote object or None
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Place a trading order.
        
        Args:
            order: OrderRequest with order details
            
        Returns:
            OrderResult with execution status
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Dict]:
        """
        Get orders with optional status filter.
        
        Args:
            status: Filter by order status
            
        Returns:
            List of order dictionaries
        """
        pass
    
    async def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            OrderResult or None
        """
        orders = await self.get_orders()
        for order in orders:
            if order.get("order_id") == order_id:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus(order.get("status", "pending")),
                    filled_qty=order.get("filled_qty", 0),
                    avg_fill_price=order.get("avg_fill_price"),
                )
        return None
    
    # Convenience methods
    
    async def buy(
        self,
        ticker: str,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        market: Market = Market.US
    ) -> OrderResult:
        """
        Place a buy order.
        
        Args:
            ticker: Stock symbol
            quantity: Number of shares
            order_type: Order type (market, limit, etc.)
            limit_price: Limit price for limit orders
            market: Trading market
            
        Returns:
            OrderResult
        """
        order = OrderRequest(
            ticker=ticker,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            market=market
        )
        return await self.place_order(order)
    
    async def sell(
        self,
        ticker: str,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        market: Market = Market.US
    ) -> OrderResult:
        """
        Place a sell order.
        
        Args:
            ticker: Stock symbol
            quantity: Number of shares
            order_type: Order type (market, limit, etc.)
            limit_price: Limit price for limit orders
            market: Trading market
            
        Returns:
            OrderResult
        """
        order = OrderRequest(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            market=market
        )
        return await self.place_order(order)
    
    async def close_position(self, ticker: str, market: Market = Market.US) -> OrderResult:
        """
        Close entire position for a ticker.
        
        Args:
            ticker: Stock symbol
            market: Trading market
            
        Returns:
            OrderResult
        """
        positions = await self.get_positions()
        for pos in positions:
            if pos.ticker == ticker and pos.market == market:
                if pos.quantity > 0:
                    return await self.sell(ticker, pos.quantity, market=market)
                elif pos.quantity < 0:
                    return await self.buy(ticker, abs(pos.quantity), market=market)
        
        return OrderResult(
            success=False,
            message=f"No position found for {ticker}"
        )
    
    async def close_all_positions(self) -> List[OrderResult]:
        """
        Close all open positions.
        
        Returns:
            List of OrderResults
        """
        results = []
        positions = await self.get_positions()
        
        for pos in positions:
            result = await self.close_position(pos.ticker, pos.market)
            results.append(result)
        
        return results
    
    def format_ticker(self, ticker: str, market: Market) -> str:
        """
        Format ticker for specific broker/market.
        Override in subclasses if needed.
        
        Args:
            ticker: Raw ticker symbol
            market: Target market
            
        Returns:
            Formatted ticker string
        """
        return ticker.upper()
