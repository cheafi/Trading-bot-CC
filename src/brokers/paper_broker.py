"""
Paper Trading Broker

Simulated trading for testing and development.
No real money involved — all trades are simulated.

Sprint 25: adds realistic execution modelling:
- SlippageModel  — volatility-aware price impact
- Spread model   — fills at ask (buy) / bid (sell), not mid
- Commission     — configurable per-order + per-share fees
- Latency        — configurable async delay before fill
"""
import asyncio
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

from src.brokers.base import (
    BaseBroker, OrderRequest, OrderResult, Position,
    AccountInfo, Quote, OrderType, OrderSide, OrderStatus, Market,
)

logger = logging.getLogger(__name__)

try:
    from src.core.errors import BrokerError
except ImportError:
    class BrokerError(Exception):
        pass


# ---------------------------------------------------------------------------
# Sprint 25: execution-realism models
# ---------------------------------------------------------------------------

@dataclass
class SlippageModel:
    """
    Models market-impact slippage.

    ``base_bps`` is a fixed cost in basis points (1 bp = 0.01%).
    ``vol_multiplier`` scales slippage by the quote's implied
    volatility (approximated from bid-ask spread width).
    ``max_bps`` caps slippage to avoid absurd outliers.
    """
    base_bps: float = 2.0         # 0.02 %
    vol_multiplier: float = 1.0   # scale with spread width
    max_bps: float = 20.0         # 0.20 % hard cap
    random_seed: Optional[int] = None  # for reproducible tests

    def _rng(self) -> random.Random:
        return random.Random(self.random_seed)

    def apply(self, price: float, side: str, spread_pct: float = 0.0) -> float:
        """Return the slippage-adjusted fill price.

        Args:
            price:      raw fill price (typically ask for buys, bid for sells)
            side:       "buy" or "sell"
            spread_pct: bid-ask spread as a fraction of mid (0-1)
        """
        # Base + vol component (wider spread => more slippage)
        slip_bps = self.base_bps + self.vol_multiplier * spread_pct * 10_000
        slip_bps = min(slip_bps, self.max_bps)
        # Add small random jitter (+/- 30% of computed slippage)
        jitter = self._rng().uniform(-0.3, 0.3) * slip_bps
        slip_bps = max(0.0, slip_bps + jitter)
        slip_frac = slip_bps / 10_000

        if side == "buy":
            return price * (1 + slip_frac)
        else:
            return price * (1 - slip_frac)


@dataclass
class CommissionModel:
    """
    Configurable commission schedule.

    Default mirrors the Alpaca / IBKR Lite zero-commission
    model for equities but charges $0.65/contract for options.
    Crypto typically has a flat 0.10% taker fee.
    """
    per_order: float = 0.0          # flat fee per order
    per_share: float = 0.0          # per-share fee
    min_per_order: float = 0.0      # minimum charge
    pct_of_value: float = 0.0       # percentage of notional (e.g. 0.001 = 0.1%)

    def calculate(self, quantity: int, fill_price: float) -> float:
        """Return total commission for an order fill."""
        notional = quantity * fill_price
        comm = self.per_order + self.per_share * quantity + self.pct_of_value * notional
        return max(comm, self.min_per_order)


# ---------------------------------------------------------------------------
# Preset commission schedules
# ---------------------------------------------------------------------------
COMMISSION_PRESETS: Dict[str, CommissionModel] = {
    "zero":   CommissionModel(),                                        # Alpaca / Robinhood
    "ibkr":   CommissionModel(per_share=0.005, min_per_order=1.0),      # IBKR Pro
    "crypto": CommissionModel(pct_of_value=0.001),                      # 0.10% taker
    "hk":     CommissionModel(pct_of_value=0.0008, min_per_order=18.0), # HK brokerage
}


class PaperBroker(BaseBroker):
    """
    Paper Trading Broker for simulation.

    Sprint 25 features:
    - **Spread-aware fills**: buys fill at ask, sells at bid (not mid)
    - **Slippage model**: volatility-scaled market impact
    - **Commission model**: configurable per-share / flat / pct fees
    - **Latency simulation**: async delay before fill
    - **Cumulative commission tracking** for performance reports

    Configuration:
        initial_cash: starting cash balance (default $100 000)
        slippage:     SlippageModel instance (or None to disable)
        commission:   CommissionModel instance, or a preset name
        latency_ms:   simulated order-to-fill latency in ms (0 = instant)
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        slippage: Optional[SlippageModel] = None,
        commission: Optional[CommissionModel] = None,
        commission_preset: str = "zero",
        latency_ms: float = 0.0,
    ):
        super().__init__("PaperTrading")
        self.initial_cash = initial_cash

        # Execution-realism knobs (Sprint 25)
        self.slippage_model = slippage or SlippageModel()
        if commission is not None:
            self.commission_model = commission
        else:
            self.commission_model = COMMISSION_PRESETS.get(
                commission_preset, CommissionModel(),
            )
        self.latency_ms = latency_ms

        # Account state
        self._cash = initial_cash
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Dict] = {}
        self._order_history: List[Dict] = []
        self._trades: List[Dict] = []
        self._total_commissions: float = 0.0
        self._total_slippage_cost: float = 0.0

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
            realized_pnl_today=realized_pnl,
        )

    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
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

            url = f"https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest"
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
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

    # ------------------------------------------------------------------
    # Sprint 25: spread + slippage aware fill-price calculation
    # ------------------------------------------------------------------

    def _realistic_fill_price(
        self,
        quote: Quote,
        side: OrderSide,
        order_type: OrderType,
        limit_price: Optional[float] = None,
    ) -> float:
        """Compute a realistic fill price using spread + slippage.

        Market orders:
          - Buys  fill at ask (+ slippage)
          - Sells fill at bid (- slippage)
        Limit orders: fill at the limit price (slippage still applied).
        """
        bid = quote.bid if quote.bid and quote.bid > 0 else quote.price
        ask = quote.ask if quote.ask and quote.ask > 0 else quote.price
        mid = quote.price if quote.price > 0 else (bid + ask) / 2

        # Spread as fraction of mid
        spread_pct = (ask - bid) / mid if mid > 0 else 0.0

        if order_type == OrderType.MARKET:
            raw = ask if side == OrderSide.BUY else bid
        elif order_type == OrderType.LIMIT and limit_price:
            raw = limit_price
        else:
            raw = mid

        # Apply slippage on top
        fill = self.slippage_model.apply(raw, side.value, spread_pct)

        # Track cumulative slippage cost (vs mid)
        self._total_slippage_cost += abs(fill - mid)

        return round(fill, 4)

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a simulated trading order with realistic fills."""
        order_id = str(uuid.uuid4())[:8]

        # Simulate latency (Sprint 25)
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        quote = await self.get_quote(order.ticker, order.market)

        if not quote:
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Unable to get quote for {order.ticker}",
            )

        # Market order — fill immediately
        if order.order_type == OrderType.MARKET:
            fill_price = self._realistic_fill_price(
                quote, order.side, OrderType.MARKET,
            )
            return await self._execute_order(order_id, order, fill_price)

        # Limit order
        elif order.order_type == OrderType.LIMIT:
            current_price = quote.price
            if order.side == OrderSide.BUY:
                if current_price <= order.limit_price:
                    fill_price = self._realistic_fill_price(
                        quote, order.side, OrderType.LIMIT, order.limit_price,
                    )
                    return await self._execute_order(order_id, order, fill_price)
            else:
                if current_price >= order.limit_price:
                    fill_price = self._realistic_fill_price(
                        quote, order.side, OrderType.LIMIT, order.limit_price,
                    )
                    return await self._execute_order(order_id, order, fill_price)

            self._orders[order_id] = {
                'order_id': order_id,
                'order': order,
                'status': OrderStatus.SUBMITTED,
                'created': datetime.now(),
            }
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.SUBMITTED,
                message="Limit order submitted",
            )

        # Stop order
        elif order.order_type == OrderType.STOP:
            current_price = quote.price
            if order.side == OrderSide.BUY:
                if current_price >= order.stop_price:
                    fill_price = self._realistic_fill_price(
                        quote, order.side, OrderType.MARKET,
                    )
                    return await self._execute_order(order_id, order, fill_price)
            else:
                if current_price <= order.stop_price:
                    fill_price = self._realistic_fill_price(
                        quote, order.side, OrderType.MARKET,
                    )
                    return await self._execute_order(order_id, order, fill_price)

            self._orders[order_id] = {
                'order_id': order_id,
                'order': order,
                'status': OrderStatus.SUBMITTED,
                'created': datetime.now(),
            }
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.SUBMITTED,
                message="Stop order submitted",
            )

        return OrderResult(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message=f"Unsupported order type: {order.order_type}",
        )

    async def _execute_order(
        self,
        order_id: str,
        order: OrderRequest,
        fill_price: float,
    ) -> OrderResult:
        """Execute an order at the given (realistic) fill price."""
        total_cost = fill_price * order.quantity

        # Calculate commission (Sprint 25)
        commission = self.commission_model.calculate(order.quantity, fill_price)
        self._total_commissions += commission

        if order.side == OrderSide.BUY:
            required = total_cost + commission
            if required > self._cash:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=(
                        f"Insufficient funds. "
                        f"Need ${required:.2f} (incl ${commission:.2f} commission), "
                        f"have ${self._cash:.2f}"
                    ),
                )

            self._cash -= (total_cost + commission)

            if order.ticker in self._positions:
                pos = self._positions[order.ticker]
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
                    market=order.market,
                )

        else:  # SELL
            if order.ticker not in self._positions:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"No position in {order.ticker}",
                )

            pos = self._positions[order.ticker]

            if order.quantity > pos.quantity:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"Insufficient shares. Have {pos.quantity}, selling {order.quantity}",
                )

            # P&L net of commission
            pnl = (fill_price - pos.avg_price) * order.quantity - commission

            self._cash += (total_cost - commission)

            pos.quantity -= order.quantity
            pos.realized_pnl += pnl

            if pos.quantity == 0:
                del self._positions[order.ticker]

            self._trades.append({
                'ticker': order.ticker,
                'side': order.side.value,
                'quantity': order.quantity,
                'price': fill_price,
                'pnl': pnl,
                'commission': commission,
                'timestamp': datetime.now(),
            })

        self._order_history.append({
            'order_id': order_id,
            'ticker': order.ticker,
            'side': order.side.value,
            'quantity': order.quantity,
            'fill_price': fill_price,
            'commission': commission,
            'status': OrderStatus.FILLED.value,
            'timestamp': datetime.now(),
        })

        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_qty=order.quantity,
            avg_fill_price=fill_price,
            message=f"Order filled at ${fill_price:.4f} (comm=${commission:.2f})",
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self._orders:
            self._orders[order_id]['status'] = OrderStatus.CANCELLED
            del self._orders[order_id]

            self._order_history.append({
                'order_id': order_id,
                'status': OrderStatus.CANCELLED.value,
                'timestamp': datetime.now(),
            })
            return True
        return False

    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Dict]:
        """Get orders with optional status filter."""
        orders = []

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
                    'created': order_data['created'].isoformat(),
                })

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
        self._total_commissions = 0.0
        self._total_slippage_cost = 0.0
        logger.info("Paper trading account reset")

    def get_trade_history(self) -> List[Dict]:
        """Get all completed trades."""
        return self._trades.copy()

    def get_performance_summary(self) -> Dict:
        """Get performance summary including commission & slippage impact."""
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in self._trades if t.get('pnl', 0) < 0)

        total_pnl = sum(t.get('pnl', 0) for t in self._trades)

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
            # Sprint 25: execution cost transparency
            'total_commissions': self._total_commissions,
            'total_slippage_cost': self._total_slippage_cost,
            'total_execution_cost': self._total_commissions + self._total_slippage_cost,
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

            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and current_price <= order.limit_price:
                    should_fill = True
                elif order.side == OrderSide.SELL and current_price >= order.limit_price:
                    should_fill = True

            elif order.order_type == OrderType.STOP:
                if order.side == OrderSide.BUY and current_price >= order.stop_price:
                    should_fill = True
                elif order.side == OrderSide.SELL and current_price <= order.stop_price:
                    should_fill = True

            if should_fill:
                fill_price = self._realistic_fill_price(
                    quote, order.side,
                    order.order_type if order.order_type == OrderType.LIMIT else OrderType.MARKET,
                    order.limit_price if order.order_type == OrderType.LIMIT else None,
                )
                result = await self._execute_order(order_id, order, fill_price)
                if result.success:
                    to_remove.append(order_id)

        for order_id in to_remove:
            del self._orders[order_id]
