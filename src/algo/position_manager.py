"""
TradingAI Bot - Position Manager

Comprehensive position sizing and risk management for short-term trading.

Features:
- Risk-based position sizing (0.25-1% per trade)
- Maximum exposure limits
- Sector correlation tracking
- Drawdown monitoring
- Time-based exit rules
- Trailing stop management

Based on proven swing trading risk management principles.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class PositionStatus(str, Enum):
    """Status of a position."""
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    STOPPED_OUT = "stopped_out"
    TARGET_HIT = "target_hit"
    TIME_EXIT = "time_exit"


@dataclass
class Position:
    """Represents an open or closed trading position."""
    
    # Identification
    ticker: str
    strategy_id: str
    position_id: str = ""
    
    # Entry
    entry_price: float = 0.0
    entry_date: Optional[datetime] = None
    entry_reason: str = ""
    
    # Size
    shares: int = 0
    position_value: float = 0.0
    risk_amount: float = 0.0
    
    # Stops and targets
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_price: float = 0.0
    atr_at_entry: float = 0.0
    
    # Multi-target exits (scale out)
    target_1r_price: float = 0.0    # First target at 1R
    target_2r_price: float = 0.0    # Second target at 2R
    target_3r_price: float = 0.0    # Third target at 3R
    partial_exit_1r: bool = False   # Has taken profit at 1R?
    partial_exit_2r: bool = False   # Has taken profit at 2R?
    original_shares: int = 0        # Track original size for partial exits
    
    # Time limits
    max_hold_days: int = 40
    min_hold_days: int = 3
    
    # Current status
    status: PositionStatus = PositionStatus.OPEN
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    # Exit
    exit_price: float = 0.0
    exit_date: Optional[datetime] = None
    exit_reason: str = ""
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    
    # Metadata
    sector: str = ""
    notes: str = ""
    
    def __post_init__(self):
        if not self.position_id:
            self.position_id = f"{self.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    @property
    def days_held(self) -> int:
        """Calculate trading days held."""
        if not self.entry_date:
            return 0
        end_date = self.exit_date or datetime.now()
        # Rough approximation: 5 trading days per week
        days = (end_date - self.entry_date).days
        return int(days * 5 / 7)
    
    @property
    def reward_risk_ratio(self) -> float:
        """Calculate reward/risk ratio."""
        if self.risk_amount == 0:
            return 0.0
        return self.unrealized_pnl / self.risk_amount if self.status == PositionStatus.OPEN else self.realized_pnl / self.risk_amount
    
    def update_price(self, current_price: float):
        """Update position with current price."""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.entry_price) * self.shares
        self.unrealized_pnl_pct = (current_price - self.entry_price) / self.entry_price * 100 if self.entry_price > 0 else 0
    
    def update_trailing_stop(self, current_price: float, trail_pct: float = 0.02, activation_pct: float = 0.03):
        """Update trailing stop with tiered tightening at higher profits."""
        if self.entry_price <= 0:
            return
        
        current_gain = (current_price - self.entry_price) / self.entry_price
        
        # Tiered trailing: tighter trail at higher profits to lock in gains
        if current_gain >= 0.15:       # 15%+ profit: trail at 4%
            effective_trail = 0.04
        elif current_gain >= 0.10:     # 10%+ profit: trail at 3%
            effective_trail = 0.03
        elif current_gain >= activation_pct:  # Activation threshold: use default
            effective_trail = trail_pct
        else:
            return  # Not yet activated
        
        new_trail_stop = current_price * (1 - effective_trail)
        if new_trail_stop > self.trailing_stop_price:
            self.trailing_stop_price = new_trail_stop
    
    def check_exit_conditions(self, current_price: float, current_date: datetime) -> Tuple[bool, str]:
        """
        Check if position should be exited (full or partial).
        
        Returns:
            (should_exit, reason)
            Partial exits use reason prefix 'partial_'
        """
        self.update_price(current_price)
        
        # 1. Stop loss hit
        if current_price <= self.stop_loss_price:
            return True, "stop_loss"
        
        # 2. Trailing stop hit
        if self.trailing_stop_price > 0 and current_price <= self.trailing_stop_price:
            return True, "trailing_stop"
        
        # 3. Partial exit at 1R (sell 1/3)
        if self.target_1r_price > 0 and current_price >= self.target_1r_price and not self.partial_exit_1r:
            self.partial_exit_1r = True
            # Move stop to breakeven after 1R hit
            if self.entry_price > self.stop_loss_price:
                self.stop_loss_price = self.entry_price
            return True, "partial_1r"
        
        # 4. Partial exit at 2R (sell another 1/3)
        if self.target_2r_price > 0 and current_price >= self.target_2r_price and not self.partial_exit_2r:
            self.partial_exit_2r = True
            return True, "partial_2r"
        
        # 5. Full take profit at 3R
        if self.target_3r_price > 0 and current_price >= self.target_3r_price:
            return True, "take_profit_3r"
        
        # 6. Legacy take profit
        if self.take_profit_price > 0 and current_price >= self.take_profit_price:
            return True, "take_profit"
        
        # 7. Max hold time exceeded
        if self.entry_date:
            days_held = (current_date - self.entry_date).days
            if days_held >= self.max_hold_days:
                return True, "max_hold_time"
        
        return False, ""
    
    def close_position(self, exit_price: float, exit_date: datetime, reason: str):
        """Close the position."""
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_reason = reason
        self.realized_pnl = (exit_price - self.entry_price) * self.shares
        self.realized_pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100 if self.entry_price > 0 else 0
        
        # Set status based on reason
        if reason == "stop_loss" or reason == "trailing_stop":
            self.status = PositionStatus.STOPPED_OUT
        elif reason == "take_profit":
            self.status = PositionStatus.TARGET_HIT
        elif reason == "max_hold_time":
            self.status = PositionStatus.TIME_EXIT
        else:
            self.status = PositionStatus.CLOSED


@dataclass
class RiskParameters:
    """Risk management parameters for position sizing."""
    
    # Account parameters
    account_size: float = 100000.0
    
    # Risk per trade
    risk_per_trade_pct: float = 1.0       # 1% risk per trade
    max_risk_per_trade_pct: float = 2.0   # Hard cap at 2%
    
    # Position limits
    max_position_size_pct: float = 10.0   # Max 10% in one position
    max_open_positions: int = 5
    max_total_exposure_pct: float = 80.0  # Max 80% invested
    
    # Sector limits
    max_sector_exposure_pct: float = 30.0  # Max 30% in one sector
    max_correlated_positions: int = 3      # Max correlated positions
    
    # Drawdown limits
    max_daily_loss_pct: float = 3.0       # Stop trading after 3% daily loss
    max_weekly_loss_pct: float = 7.0      # Stop trading after 7% weekly loss
    max_total_drawdown_pct: float = 15.0  # Stop trading after 15% drawdown
    
    # Scaling
    scale_down_after_losses: int = 3      # Reduce size after 3 consecutive losses
    scale_factor: float = 0.5             # Scale to 50% after losses


class PositionManager:
    """
    Manages positions and calculates optimal position sizes.
    
    Key responsibilities:
    1. Calculate position sizes based on risk
    2. Track open positions
    3. Monitor exposure limits
    4. Enforce risk rules
    5. Track performance metrics
    """
    
    def __init__(self, params: Optional[RiskParameters] = None):
        """Initialize position manager."""
        self.params = params or RiskParameters()
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        
        # Performance tracking
        self.daily_pnl: Dict[str, float] = {}
        self.consecutive_losses: int = 0
        self.peak_equity: float = self.params.account_size
        self.current_equity: float = self.params.account_size
        
        self.logger = logging.getLogger(__name__)
    
    # ========== Position Sizing ==========
    
    def calculate_position_size(
        self,
        ticker: str,
        entry_price: float,
        stop_loss_price: float,
        atr: Optional[float] = None,
        sector: str = ""
    ) -> Dict[str, Any]:
        """
        Calculate optimal position size based on risk.
        
        Uses the formula:
        Shares = (Account * Risk%) / (Entry - Stop)
        
        Args:
            ticker: Stock ticker
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            atr: Average True Range (optional, for ATR-based stops)
            sector: Stock sector for exposure checks
        
        Returns:
            Dict with shares, position_value, risk_amount, etc.
        """
        # Check if we can take a new position
        can_trade, reason = self.can_open_position(ticker, sector)
        if not can_trade:
            return {
                'shares': 0,
                'can_trade': False,
                'reason': reason
            }
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 0:
            return {
                'shares': 0,
                'can_trade': False,
                'reason': 'Invalid stop loss (must be below entry)'
            }
        
        # Adjust risk % based on consecutive losses
        risk_pct = self.params.risk_per_trade_pct
        if self.consecutive_losses >= self.params.scale_down_after_losses:
            risk_pct *= self.params.scale_factor
            self.logger.info(f"Scaling down risk to {risk_pct}% after {self.consecutive_losses} consecutive losses")
        
        # Calculate risk amount
        risk_amount = self.current_equity * (risk_pct / 100)
        
        # Calculate shares
        shares = int(risk_amount / risk_per_share)
        
        # Check position size limits
        position_value = shares * entry_price
        max_position_value = self.current_equity * (self.params.max_position_size_pct / 100)
        
        if position_value > max_position_value:
            shares = int(max_position_value / entry_price)
            position_value = shares * entry_price
            self.logger.info(f"Position size capped at {self.params.max_position_size_pct}% of equity")
        
        # Check total exposure
        current_exposure = self._get_total_exposure()
        max_additional = (self.params.max_total_exposure_pct / 100 * self.current_equity) - current_exposure
        
        if position_value > max_additional:
            shares = int(max_additional / entry_price)
            position_value = shares * entry_price
            self.logger.info("Position size reduced due to total exposure limit")
        
        if shares <= 0:
            return {
                'shares': 0,
                'can_trade': False,
                'reason': 'Position size too small after applying limits'
            }
        
        # Calculate R-based multi-target prices
        r_unit = risk_per_share  # 1R = risk per share
        target_1r = entry_price + (r_unit * 1.0)
        target_2r = entry_price + (r_unit * 2.0)
        target_3r = entry_price + (r_unit * 3.0)
        
        return {
            'can_trade': True,
            'shares': shares,
            'position_value': position_value,
            'risk_amount': shares * risk_per_share,
            'risk_pct': (shares * risk_per_share) / self.current_equity * 100,
            'entry_price': entry_price,
            'stop_loss_price': stop_loss_price,
            'target_1r': target_1r,
            'target_2r': target_2r,
            'target_3r': target_3r,
            'target_price': target_2r,  # Default full target at 2R
            'reward_risk_ratio': 2.0,
            'pct_of_account': position_value / self.current_equity * 100,
        }
    
    def calculate_atr_based_size(
        self,
        ticker: str,
        entry_price: float,
        atr: float,
        atr_multiplier: float = 2.0,
        sector: str = ""
    ) -> Dict[str, Any]:
        """
        Calculate position size using ATR-based stops.
        
        Stop is placed ATR * multiplier below entry.
        """
        stop_loss_price = entry_price - (atr * atr_multiplier)
        return self.calculate_position_size(ticker, entry_price, stop_loss_price, atr, sector)
    
    # ========== Position Management ==========
    
    def can_open_position(self, ticker: str, sector: str = "") -> Tuple[bool, str]:
        """
        Check if we can open a new position.
        
        Returns:
            (can_open, reason)
        """
        # Check if already have position in this ticker
        if ticker in self.positions:
            return False, f"Already have position in {ticker}"
        
        # Check max positions
        if len(self.positions) >= self.params.max_open_positions:
            return False, f"Max positions ({self.params.max_open_positions}) reached"
        
        # Check sector exposure
        if sector:
            sector_exposure = self._get_sector_exposure(sector)
            if sector_exposure >= self.params.max_sector_exposure_pct:
                return False, f"Max sector exposure ({self.params.max_sector_exposure_pct}%) reached for {sector}"
        
        # Check drawdown limits
        drawdown = self._get_current_drawdown()
        if drawdown >= self.params.max_total_drawdown_pct:
            return False, f"Max drawdown ({self.params.max_total_drawdown_pct}%) reached - trading paused"
        
        # Check daily loss limit
        daily_loss = self._get_daily_pnl()
        if daily_loss <= -self.params.max_daily_loss_pct:
            return False, (
                f"Daily loss limit "
                f"({self.params.max_daily_loss_pct}%) reached"
            )

        # Check weekly loss limit
        weekly_loss = self._get_weekly_pnl()
        if weekly_loss <= -self.params.max_weekly_loss_pct:
            return False, (
                f"Weekly loss limit "
                f"({self.params.max_weekly_loss_pct}%) reached"
            )

        return True, ""
    
    def open_position(
        self,
        ticker: str,
        strategy_id: str,
        entry_price: float,
        shares: int,
        stop_loss_price: float,
        take_profit_price: float = 0.0,
        atr: float = 0.0,
        max_hold_days: int = 40,
        sector: str = "",
        entry_reason: str = ""
    ) -> Position:
        """
        Open a new position.
        
        Returns:
            Position object
        """
        position = Position(
            ticker=ticker,
            strategy_id=strategy_id,
            entry_price=entry_price,
            entry_date=datetime.now(),
            entry_reason=entry_reason,
            shares=shares,
            original_shares=shares,
            position_value=shares * entry_price,
            risk_amount=shares * abs(entry_price - stop_loss_price),
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            atr_at_entry=atr,
            max_hold_days=max_hold_days,
            sector=sector,
        )
        
        # Set multi-target R levels
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share > 0:
            position.target_1r_price = entry_price + risk_per_share
            position.target_2r_price = entry_price + (risk_per_share * 2)
            position.target_3r_price = entry_price + (risk_per_share * 3)
        
        self.positions[ticker] = position
        self.logger.info(
            f"Opened position: {ticker} @ ${entry_price:.2f}, "
            f"{shares} shares, stop ${stop_loss_price:.2f}"
        )
        
        return position
    
    def close_position(
        self,
        ticker: str,
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[Position]:
        """
        Close an existing position.
        
        Returns:
            Closed Position object or None if not found
        """
        if ticker not in self.positions:
            self.logger.warning(f"No position found for {ticker}")
            return None
        
        position = self.positions[ticker]
        position.close_position(exit_price, datetime.now(), reason)

        # Update equity
        self.current_equity += position.realized_pnl
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        # --- FIX: update daily and weekly PnL ledgers ---
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_pnl[today] = (
            self.daily_pnl.get(today, 0.0)
            + position.realized_pnl_pct
        )
        try:
            week_key = datetime.now().strftime('%Y-W%W')
        except Exception:
            week_key = today[:7]
        if not hasattr(self, 'weekly_pnl'):
            self.weekly_pnl = {}
        self.weekly_pnl[week_key] = (
            self.weekly_pnl.get(week_key, 0.0)
            + position.realized_pnl_pct
        )

        # Track consecutive losses
        if position.realized_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[ticker]
        
        self.logger.info(
            f"Closed position: {ticker} @ ${exit_price:.2f}, "
            f"P/L: ${position.realized_pnl:.2f} ({position.realized_pnl_pct:.2f}%), "
            f"Reason: {reason}"
        )
        
        return position
    
    def update_all_positions(self, prices: Dict[str, float], current_date: datetime):
        """
        Update all positions with current prices and check exit conditions.
        
        Args:
            prices: Dict of ticker -> current price
            current_date: Current date for time-based exits
        
        Returns:
            List of positions that should be closed
        """
        positions_to_close = []
        
        for ticker, position in self.positions.items():
            if ticker in prices:
                current_price = prices[ticker]
                
                # Update trailing stop
                position.update_trailing_stop(
                    current_price,
                    trail_pct=0.02,
                    activation_pct=0.03
                )
                
                # Check exit conditions
                should_exit, reason = position.check_exit_conditions(current_price, current_date)
                
                if should_exit:
                    if reason.startswith("partial_"):
                        # Partial exit: sell 1/3 of position
                        partial_shares = max(
                            1, position.shares // 3
                        )
                        self.reduce_position(
                            ticker, partial_shares,
                            current_price, reason,
                        )
                    else:
                        positions_to_close.append({
                            'ticker': ticker,
                            'price': current_price,
                            'reason': reason,
                        })
        
        return positions_to_close
    
    # ========== Exposure Calculations ==========
    
    def _get_total_exposure(self) -> float:
        """Get total exposure (sum of position values)."""
        return sum(p.position_value for p in self.positions.values())
    
    def _get_sector_exposure(self, sector: str) -> float:
        """Get exposure to a specific sector as percentage of equity."""
        sector_value = sum(
            p.position_value for p in self.positions.values()
            if p.sector == sector
        )
        return (sector_value / self.current_equity * 100) if self.current_equity > 0 else 0
    
    def _get_current_drawdown(self) -> float:
        """Get current drawdown from peak as percentage."""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity * 100
    
    def _get_daily_pnl(self) -> float:
        """Get today P/L as percentage of equity."""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.daily_pnl.get(today, 0.0)

    def _get_weekly_pnl(self) -> float:
        """Get this week P/L as percentage of equity."""
        if not hasattr(self, 'weekly_pnl'):
            self.weekly_pnl = {}
        try:
            week_key = datetime.now().strftime('%Y-W%W')
        except Exception:
            week_key = datetime.now().strftime('%Y-%m-%d')[:7]
        return self.weekly_pnl.get(week_key, 0.0)

    def reduce_position(
        self,
        ticker: str,
        shares_to_sell: int,
        exit_price: float,
        reason: str = "partial",
    ):
        """
        Partial exit: reduce position by shares_to_sell.

        If shares_to_sell >= current shares, does a full close.
        Returns the realized PnL from the partial exit.
        """
        if ticker not in self.positions:
            self.logger.warning(f"No position for {ticker}")
            return None

        pos = self.positions[ticker]
        if shares_to_sell >= pos.shares:
            return self.close_position(ticker, exit_price, reason)

        # Partial exit
        pnl_per_share = exit_price - pos.entry_price
        partial_pnl = pnl_per_share * shares_to_sell
        partial_pnl_pct = (
            pnl_per_share / pos.entry_price * 100
        )

        # Update position
        pos.shares -= shares_to_sell
        pos.position_value = pos.shares * exit_price

        # Update equity
        self.current_equity += partial_pnl
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        # Update daily/weekly PnL
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_pnl[today] = (
            self.daily_pnl.get(today, 0.0) + partial_pnl_pct
        )
        if not hasattr(self, 'weekly_pnl'):
            self.weekly_pnl = {}
        try:
            wk = datetime.now().strftime('%Y-W%W')
        except Exception:
            wk = today[:7]
        self.weekly_pnl[wk] = (
            self.weekly_pnl.get(wk, 0.0) + partial_pnl_pct
        )

        self.logger.info(
            f"Partial exit: {ticker} sold {shares_to_sell} shares "
            f"@ ${exit_price:.2f}, PnL: ${partial_pnl:.2f} "
            f"({partial_pnl_pct:.2f}%), reason: {reason}, "
            f"{pos.shares} shares remaining"
        )
        return partial_pnl
    
    def get_exposure_report(self) -> Dict[str, Any]:
        """Get comprehensive exposure report."""
        total_exposure = self._get_total_exposure()
        
        # Sector breakdown
        sector_exposure = {}
        for p in self.positions.values():
            sector = p.sector or 'Unknown'
            if sector not in sector_exposure:
                sector_exposure[sector] = 0.0
            sector_exposure[sector] += p.position_value
        
        # Convert to percentages
        sector_pct = {
            sector: (value / self.current_equity * 100)
            for sector, value in sector_exposure.items()
        }
        
        # Unrealized P/L
        unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        
        return {
            'account_size': self.params.account_size,
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'current_drawdown_pct': self._get_current_drawdown(),
            'open_positions': len(self.positions),
            'max_positions': self.params.max_open_positions,
            'total_exposure': total_exposure,
            'total_exposure_pct': (total_exposure / self.current_equity * 100) if self.current_equity > 0 else 0,
            'cash_available': self.current_equity - total_exposure,
            'sector_exposure': sector_pct,
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pnl_pct': (unrealized_pnl / self.current_equity * 100) if self.current_equity > 0 else 0,
            'consecutive_losses': self.consecutive_losses,
            'risk_scaling': self.params.scale_factor if self.consecutive_losses >= self.params.scale_down_after_losses else 1.0,
        }
    
    # ========== Performance Tracking ==========
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for closed positions."""
        if not self.closed_positions:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'total_pnl': 0.0,
            }
        
        wins = [p for p in self.closed_positions if p.realized_pnl > 0]
        losses = [p for p in self.closed_positions if p.realized_pnl <= 0]
        
        total_wins = sum(p.realized_pnl for p in wins)
        total_losses = abs(sum(p.realized_pnl for p in losses))
        
        avg_win = total_wins / len(wins) if wins else 0.0
        avg_loss = total_losses / len(losses) if losses else 0.0
        
        return {
            'total_trades': len(self.closed_positions),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(self.closed_positions) * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': sum(p.realized_pnl_pct for p in wins) / len(wins) if wins else 0,
            'avg_loss_pct': sum(p.realized_pnl_pct for p in losses) / len(losses) if losses else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'total_pnl': sum(p.realized_pnl for p in self.closed_positions),
            'total_pnl_pct': (self.current_equity - self.params.account_size) / self.params.account_size * 100,
            'largest_win': max(p.realized_pnl for p in wins) if wins else 0,
            'largest_loss': min(p.realized_pnl for p in losses) if losses else 0,
            'avg_hold_days': sum(p.days_held for p in self.closed_positions) / len(self.closed_positions),
            'max_drawdown_pct': self._get_current_drawdown(),
        }
    
    def get_open_positions_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all open positions."""
        return [
            {
                'ticker': p.ticker,
                'strategy': p.strategy_id,
                'entry_price': p.entry_price,
                'current_price': p.current_price,
                'shares': p.shares,
                'position_value': p.shares * p.current_price if p.current_price else p.position_value,
                'unrealized_pnl': p.unrealized_pnl,
                'unrealized_pnl_pct': p.unrealized_pnl_pct,
                'stop_loss': p.stop_loss_price,
                'trailing_stop': p.trailing_stop_price,
                'target': p.take_profit_price,
                'days_held': p.days_held,
                'max_hold_days': p.max_hold_days,
                'sector': p.sector,
                'reward_risk': p.reward_risk_ratio,
            }
            for p in self.positions.values()
        ]


# ==============================================================================
# Helper Functions
# ==============================================================================

def calculate_risk_reward(
    entry_price: float,
    stop_loss: float,
    target: float
) -> float:
    """Calculate risk/reward ratio."""
    risk = abs(entry_price - stop_loss)
    reward = abs(target - entry_price)
    return reward / risk if risk > 0 else 0


def calculate_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.25
) -> float:
    """
    Calculate Kelly Criterion for optimal position sizing.
    
    Kelly % = W - [(1-W)/R]
    Where:
    - W = Win probability
    - R = Win/Loss ratio
    
    Uses quarter-Kelly by default (fraction=0.25) for safety.
    Half-Kelly (0.5) is more aggressive, full Kelly (1.0) is theoretical max.
    """
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    
    w = min(win_rate / 100, 0.99)  # Convert to decimal, cap at 99%
    r = avg_win / avg_loss
    
    kelly = w - ((1 - w) / r)
    
    # Apply fractional Kelly for safety (default quarter-Kelly)
    return max(0, min(kelly * fraction, 0.25))  # Cap at 25% of equity


def suggested_risk_parameters(account_size: float, style: str = "moderate") -> RiskParameters:
    """
    Get suggested risk parameters based on account size and style.
    
    Styles:
    - conservative: Lower risk, fewer trades
    - moderate: Balanced approach
    - aggressive: Higher risk, more trades
    """
    base_params = {
        'conservative': {
            'risk_per_trade_pct': 0.5,
            'max_position_size_pct': 5.0,
            'max_open_positions': 3,
            'max_total_exposure_pct': 50.0,
            'max_sector_exposure_pct': 20.0,
        },
        'moderate': {
            'risk_per_trade_pct': 1.0,
            'max_position_size_pct': 10.0,
            'max_open_positions': 5,
            'max_total_exposure_pct': 80.0,
            'max_sector_exposure_pct': 30.0,
        },
        'aggressive': {
            'risk_per_trade_pct': 2.0,
            'max_position_size_pct': 15.0,
            'max_open_positions': 8,
            'max_total_exposure_pct': 100.0,
            'max_sector_exposure_pct': 40.0,
        },
    }
    
    params_dict = base_params.get(style, base_params['moderate'])
    params_dict['account_size'] = account_size
    
    return RiskParameters(**params_dict)
