"""
Broker Manager - Unified interface for multiple brokers

Manages connections to:
- Futu (富途)
- Interactive Brokers (IB)
- Paper Trading

Integrates with Telegram bot for real-time trading.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

from src.brokers.base import (
    BaseBroker, OrderRequest, OrderResult, Position, 
    AccountInfo, Quote, OrderType, OrderSide, OrderStatus, Market
)
from src.brokers.futu_broker import FutuBroker
from src.brokers.ib_broker import IBBroker
from src.brokers.paper_broker import PaperBroker
from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class BrokerType(str, Enum):
    """Supported brokers."""
    FUTU = "futu"
    IB = "ib"
    PAPER = "paper"


class BrokerManager:
    """
    Unified broker management interface.
    
    Features:
    - Connect to multiple brokers simultaneously
    - Switch active broker for trading
    - Aggregate portfolio view across brokers
    - Real-time quote aggregation
    - Order routing
    """
    
    def __init__(self):
        self._brokers: Dict[BrokerType, BaseBroker] = {}
        self._active_broker: BrokerType = BrokerType.PAPER
        self._callbacks: Dict[str, List[callable]] = {
            'on_order_fill': [],
            'on_position_change': [],
            'on_price_alert': [],
        }
    
    @property
    def active_broker(self) -> Optional[BaseBroker]:
        """Get the active broker instance."""
        return self._brokers.get(self._active_broker)
    
    @property
    def active_broker_type(self) -> BrokerType:
        """Get the active broker type."""
        return self._active_broker
    
    async def initialize(self):
        """Initialize all available brokers."""
        # Always initialize paper trading
        paper = PaperBroker()
        await paper.connect()
        self._brokers[BrokerType.PAPER] = paper
        
        # Initialize Futu if configured
        if settings.has_futu:
            try:
                futu = FutuBroker()
                if await futu.connect():
                    self._brokers[BrokerType.FUTU] = futu
                    logger.info("Futu broker connected")
            except Exception as e:
                logger.warning(f"Futu broker not available: {e}")
        
        # Initialize IB if configured
        if settings.has_ib:
            try:
                ib = IBBroker()
                if await ib.connect():
                    self._brokers[BrokerType.IB] = ib
                    logger.info("Interactive Brokers connected")
            except Exception as e:
                logger.warning(f"IB broker not available: {e}")
        
        logger.info(f"Broker manager initialized with {len(self._brokers)} brokers")
    
    async def shutdown(self):
        """Disconnect all brokers."""
        for broker_type, broker in self._brokers.items():
            try:
                await broker.disconnect()
                logger.info(f"Disconnected from {broker_type.value}")
            except Exception as e:
                logger.error(f"Error disconnecting from {broker_type.value}: {e}")
    
    def set_active_broker(self, broker_type: BrokerType) -> bool:
        """
        Set the active broker for trading.
        
        Args:
            broker_type: The broker to set as active
            
        Returns:
            True if broker is available and set
        """
        if broker_type in self._brokers:
            self._active_broker = broker_type
            logger.info(f"Active broker set to: {broker_type.value}")
            return True
        else:
            logger.warning(f"Broker {broker_type.value} not available")
            return False
    
    def get_available_brokers(self) -> List[Dict]:
        """Get list of available brokers with status."""
        return [
            {
                'type': bt.value,
                'name': broker.name,
                'connected': broker.is_connected,
                'active': bt == self._active_broker
            }
            for bt, broker in self._brokers.items()
        ]
    
    # === Trading Operations ===
    
    async def get_quote(self, ticker: str, market: Market = Market.US) -> Optional[Quote]:
        """Get quote using the best available source."""
        # Try active broker first
        if self.active_broker:
            quote = await self.active_broker.get_quote(ticker, market)
            if quote:
                return quote
        
        # Fallback to paper broker (uses Alpaca data)
        paper = self._brokers.get(BrokerType.PAPER)
        if paper:
            return await paper.get_quote(ticker, market)
        
        return None
    
    async def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        market: Market = Market.US,
        broker: Optional[BrokerType] = None
    ) -> OrderResult:
        """
        Place an order through the specified or active broker.
        
        Args:
            ticker: Stock symbol
            side: BUY or SELL
            quantity: Number of shares
            order_type: MARKET, LIMIT, STOP, etc.
            limit_price: For limit orders
            stop_price: For stop orders
            market: Trading market
            broker: Specific broker (uses active if None)
            
        Returns:
            OrderResult with execution details
        """
        target_broker = self._brokers.get(broker) if broker else self.active_broker
        
        if not target_broker:
            return OrderResult(
                success=False,
                message="No broker available"
            )
        
        order = OrderRequest(
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            market=market
        )
        
        result = await target_broker.place_order(order)
        
        # Notify callbacks
        if result.success:
            for callback in self._callbacks['on_order_fill']:
                try:
                    await callback(result, order)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
        
        return result
    
    async def cancel_order(self, order_id: str, broker: Optional[BrokerType] = None) -> bool:
        """Cancel an order."""
        target_broker = self._brokers.get(broker) if broker else self.active_broker
        
        if not target_broker:
            return False
        
        return await target_broker.cancel_order(order_id)
    
    # === Portfolio Operations ===
    
    async def get_account(self, broker: Optional[BrokerType] = None) -> AccountInfo:
        """Get account info from specified or active broker."""
        target_broker = self._brokers.get(broker) if broker else self.active_broker
        
        if not target_broker:
            return AccountInfo(account_id="", cash=0)
        
        return await target_broker.get_account()
    
    async def get_positions(self, broker: Optional[BrokerType] = None) -> List[Position]:
        """Get positions from specified or active broker."""
        target_broker = self._brokers.get(broker) if broker else self.active_broker
        
        if not target_broker:
            return []
        
        return await target_broker.get_positions()
    
    async def get_all_positions(self) -> Dict[BrokerType, List[Position]]:
        """Get positions from all connected brokers."""
        all_positions = {}
        
        for broker_type, broker in self._brokers.items():
            if broker.is_connected:
                positions = await broker.get_positions()
                all_positions[broker_type] = positions
        
        return all_positions
    
    async def get_aggregated_portfolio(self) -> Dict:
        """Get aggregated portfolio across all brokers."""
        total_value = 0.0
        total_pnl = 0.0
        all_positions = []
        
        for broker_type, broker in self._brokers.items():
            if broker.is_connected:
                account = await broker.get_account()
                positions = await broker.get_positions()
                
                total_value += account.portfolio_value
                total_pnl += account.unrealized_pnl
                
                for pos in positions:
                    all_positions.append({
                        'broker': broker_type.value,
                        'ticker': pos.ticker,
                        'quantity': pos.quantity,
                        'avg_price': pos.avg_price,
                        'current_price': pos.current_price,
                        'market_value': pos.market_value,
                        'pnl': pos.unrealized_pnl,
                        'pnl_pct': pos.unrealized_pnl_pct
                    })
        
        return {
            'total_value': total_value,
            'total_pnl': total_pnl,
            'positions': all_positions,
            'brokers_connected': len([b for b in self._brokers.values() if b.is_connected])
        }
    
    # === Callbacks ===
    
    def on_order_fill(self, callback: callable):
        """Register callback for order fills."""
        self._callbacks['on_order_fill'].append(callback)
    
    def on_position_change(self, callback: callable):
        """Register callback for position changes."""
        self._callbacks['on_position_change'].append(callback)
    
    def on_price_alert(self, callback: callable):
        """Register callback for price alerts."""
        self._callbacks['on_price_alert'].append(callback)


# Global broker manager instance
_broker_manager: Optional[BrokerManager] = None


async def get_broker_manager() -> BrokerManager:
    """Get or create the global broker manager instance."""
    global _broker_manager
    
    if _broker_manager is None:
        _broker_manager = BrokerManager()
        await _broker_manager.initialize()
    
    return _broker_manager
