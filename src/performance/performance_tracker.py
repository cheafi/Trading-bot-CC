"""
Performance Tracker - Track signal outcomes and success rates.

Records and analyzes:
- Signal entries and exits
- Target hits and stop losses
- Overall win rate
- Risk-adjusted returns
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class SignalStatus(str, Enum):
    """Signal status."""
    ACTIVE = "active"
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TradeDirection(str, Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"


@dataclass
class SignalOutcome:
    """Outcome of a trading signal."""
    signal_id: str
    ticker: str
    strategy: str
    direction: TradeDirection
    
    # Entry
    entry_time: datetime
    entry_price: float
    
    # Targets
    target_price: float
    stop_loss: float
    
    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    status: SignalStatus = SignalStatus.ACTIVE
    
    # Confidence
    initial_confidence: float = 0.0
    
    # Results
    pnl_pct: float = 0.0
    pnl_absolute: float = 0.0
    risk_reward_actual: float = 0.0
    max_favorable_excursion: float = 0.0  # Best unrealized gain
    max_adverse_excursion: float = 0.0    # Worst unrealized loss
    
    # Time analysis
    hold_time_hours: float = 0.0
    
    # Tags
    tags: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class PerformanceStats:
    """Performance statistics for a period or strategy."""
    period: str  # "daily", "weekly", "monthly", "all_time"
    start_date: datetime = None
    end_date: datetime = None
    
    # Trade counts
    total_signals: int = 0
    winners: int = 0
    losers: int = 0
    break_even: int = 0
    active: int = 0
    
    # Win rate
    win_rate: float = 0.0
    
    # P&L
    total_pnl_pct: float = 0.0
    avg_winner_pct: float = 0.0
    avg_loser_pct: float = 0.0
    largest_winner_pct: float = 0.0
    largest_loser_pct: float = 0.0
    
    # Risk metrics
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_risk_reward: float = 0.0
    
    # Time analysis
    avg_hold_time_hours: float = 0.0
    avg_winning_hold_time: float = 0.0
    avg_losing_hold_time: float = 0.0
    
    # Streaks
    current_streak: int = 0
    max_win_streak: int = 0
    max_lose_streak: int = 0
    
    # By strategy
    strategy_breakdown: Dict[str, Dict] = field(default_factory=dict)
    
    # By ticker
    ticker_breakdown: Dict[str, Dict] = field(default_factory=dict)


class PerformanceTracker:
    """
    Tracks and analyzes signal performance.
    
    Features:
    - Real-time signal tracking
    - Automatic outcome detection
    - Win rate analytics
    - Strategy comparison
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or {}
        self.active_signals: Dict[str, SignalOutcome] = {}
        self.completed_signals: List[SignalOutcome] = []
        
    async def record_signal(
        self,
        signal_id: str,
        ticker: str,
        strategy: str,
        direction: str,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        confidence: float = 0.0,
        tags: List[str] = None
    ) -> SignalOutcome:
        """
        Record a new signal.
        
        Args:
            signal_id: Unique signal identifier
            ticker: Stock ticker
            strategy: Strategy name
            direction: 'long' or 'short'
            entry_price: Entry price
            target_price: Target price
            stop_loss: Stop loss price
            confidence: Signal confidence (0-100)
            tags: Optional tags
            
        Returns:
            SignalOutcome object
        """
        outcome = SignalOutcome(
            signal_id=signal_id,
            ticker=ticker,
            strategy=strategy,
            direction=TradeDirection(direction.lower()),
            entry_time=datetime.now(),
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            initial_confidence=confidence,
            status=SignalStatus.ACTIVE,
            tags=tags or []
        )
        
        self.active_signals[signal_id] = outcome
        
        # Save to database if available
        if self.db:
            await self._save_signal(outcome)
        
        logger.info(f"Recorded signal {signal_id}: {ticker} {direction} @ {entry_price}")
        
        return outcome
    
    async def update_signal(
        self,
        signal_id: str,
        current_price: float,
        timestamp: datetime = None
    ) -> Optional[SignalOutcome]:
        """
        Update signal with current price.
        
        Checks if target or stop was hit and updates status.
        """
        if signal_id not in self.active_signals:
            logger.warning(f"Signal {signal_id} not found")
            return None
        
        outcome = self.active_signals[signal_id]
        timestamp = timestamp or datetime.now()
        
        # Update max excursions
        if outcome.direction == TradeDirection.LONG:
            pnl_pct = (current_price - outcome.entry_price) / outcome.entry_price * 100
            
            # Check target hit
            if current_price >= outcome.target_price:
                return await self._close_signal(
                    signal_id, 
                    outcome.target_price,
                    SignalStatus.TARGET_HIT,
                    timestamp
                )
            
            # Check stop hit
            if current_price <= outcome.stop_loss:
                return await self._close_signal(
                    signal_id,
                    outcome.stop_loss,
                    SignalStatus.STOP_HIT,
                    timestamp
                )
        else:
            pnl_pct = (outcome.entry_price - current_price) / outcome.entry_price * 100
            
            # Check target hit (for short)
            if current_price <= outcome.target_price:
                return await self._close_signal(
                    signal_id,
                    outcome.target_price,
                    SignalStatus.TARGET_HIT,
                    timestamp
                )
            
            # Check stop hit (for short)
            if current_price >= outcome.stop_loss:
                return await self._close_signal(
                    signal_id,
                    outcome.stop_loss,
                    SignalStatus.STOP_HIT,
                    timestamp
                )
        
        # Update excursions
        if pnl_pct > outcome.max_favorable_excursion:
            outcome.max_favorable_excursion = pnl_pct
        if pnl_pct < -outcome.max_adverse_excursion:
            outcome.max_adverse_excursion = -pnl_pct
        
        return outcome
    
    async def _close_signal(
        self,
        signal_id: str,
        exit_price: float,
        status: SignalStatus,
        timestamp: datetime
    ) -> SignalOutcome:
        """Close a signal with final outcome."""
        outcome = self.active_signals.pop(signal_id)
        
        outcome.exit_time = timestamp
        outcome.exit_price = exit_price
        outcome.status = status
        
        # Calculate P&L
        if outcome.direction == TradeDirection.LONG:
            outcome.pnl_pct = (exit_price - outcome.entry_price) / outcome.entry_price * 100
        else:
            outcome.pnl_pct = (outcome.entry_price - exit_price) / outcome.entry_price * 100
        
        # Calculate hold time
        outcome.hold_time_hours = (timestamp - outcome.entry_time).total_seconds() / 3600
        
        # Calculate actual risk/reward
        risk = abs(outcome.entry_price - outcome.stop_loss)
        if risk > 0:
            outcome.risk_reward_actual = outcome.pnl_pct / (risk / outcome.entry_price * 100)
        
        # Move to completed
        self.completed_signals.append(outcome)
        
        # Save to database
        if self.db:
            await self._update_signal(outcome)
        
        logger.info(f"Closed signal {signal_id}: {status.value} | P&L: {outcome.pnl_pct:.2f}%")
        
        return outcome
    
    async def close_signal_manual(
        self,
        signal_id: str,
        exit_price: float,
        status: SignalStatus = SignalStatus.CANCELLED
    ) -> Optional[SignalOutcome]:
        """Manually close a signal."""
        if signal_id not in self.active_signals:
            return None
        
        return await self._close_signal(
            signal_id,
            exit_price,
            status,
            datetime.now()
        )
    
    def get_performance_stats(
        self,
        period: str = "all_time",
        strategy: Optional[str] = None,
        ticker: Optional[str] = None
    ) -> PerformanceStats:
        """
        Calculate performance statistics.
        
        Args:
            period: "daily", "weekly", "monthly", "all_time"
            strategy: Filter by strategy
            ticker: Filter by ticker
            
        Returns:
            PerformanceStats object
        """
        # Filter signals
        signals = self.completed_signals.copy()
        
        # Time filter
        now = datetime.now()
        if period == "daily":
            cutoff = now - timedelta(days=1)
        elif period == "weekly":
            cutoff = now - timedelta(weeks=1)
        elif period == "monthly":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = datetime.min
        
        signals = [s for s in signals if s.entry_time >= cutoff]
        
        # Strategy filter
        if strategy:
            signals = [s for s in signals if s.strategy == strategy]
        
        # Ticker filter
        if ticker:
            signals = [s for s in signals if s.ticker == ticker]
        
        # Calculate stats
        stats = PerformanceStats(
            period=period,
            start_date=cutoff if period != "all_time" else None,
            end_date=now,
            total_signals=len(signals) + len(self.active_signals),
            active=len(self.active_signals)
        )
        
        if not signals:
            return stats
        
        # Winners and losers
        winners = [s for s in signals if s.pnl_pct > 0]
        losers = [s for s in signals if s.pnl_pct < 0]
        break_even = [s for s in signals if s.pnl_pct == 0]
        
        stats.winners = len(winners)
        stats.losers = len(losers)
        stats.break_even = len(break_even)
        
        closed = len(winners) + len(losers) + len(break_even)
        if closed > 0:
            stats.win_rate = len(winners) / closed * 100
        
        # P&L metrics
        stats.total_pnl_pct = sum(s.pnl_pct for s in signals)
        
        if winners:
            stats.avg_winner_pct = sum(s.pnl_pct for s in winners) / len(winners)
            stats.largest_winner_pct = max(s.pnl_pct for s in winners)
        
        if losers:
            stats.avg_loser_pct = sum(s.pnl_pct for s in losers) / len(losers)
            stats.largest_loser_pct = min(s.pnl_pct for s in losers)
        
        # Profit factor
        gross_profit = sum(s.pnl_pct for s in winners) if winners else 0
        gross_loss = abs(sum(s.pnl_pct for s in losers)) if losers else 0
        if gross_loss > 0:
            stats.profit_factor = gross_profit / gross_loss
        
        # Expectancy
        if closed > 0:
            stats.expectancy = stats.total_pnl_pct / closed
        
        # Time analysis
        all_hold_times = [s.hold_time_hours for s in signals if s.hold_time_hours > 0]
        if all_hold_times:
            stats.avg_hold_time_hours = sum(all_hold_times) / len(all_hold_times)
        
        if winners:
            stats.avg_winning_hold_time = sum(s.hold_time_hours for s in winners) / len(winners)
        if losers:
            stats.avg_losing_hold_time = sum(s.hold_time_hours for s in losers) / len(losers)
        
        # Streaks
        stats.current_streak, stats.max_win_streak, stats.max_lose_streak = self._calculate_streaks(signals)
        
        # Strategy breakdown
        stats.strategy_breakdown = self._get_strategy_breakdown(signals)
        
        # Ticker breakdown
        stats.ticker_breakdown = self._get_ticker_breakdown(signals)
        
        return stats
    
    def _calculate_streaks(self, signals: List[SignalOutcome]) -> tuple:
        """Calculate win/loss streaks."""
        if not signals:
            return 0, 0, 0
        
        # Sort by exit time
        sorted_signals = sorted(signals, key=lambda s: s.exit_time or datetime.min)
        
        current_streak = 0
        max_win_streak = 0
        max_lose_streak = 0
        current_win = 0
        current_lose = 0
        
        for s in sorted_signals:
            if s.pnl_pct > 0:
                current_win += 1
                current_lose = 0
                max_win_streak = max(max_win_streak, current_win)
            elif s.pnl_pct < 0:
                current_lose += 1
                current_win = 0
                max_lose_streak = max(max_lose_streak, current_lose)
            else:
                current_win = 0
                current_lose = 0
        
        # Current streak (positive for wins, negative for losses)
        if current_win > 0:
            current_streak = current_win
        elif current_lose > 0:
            current_streak = -current_lose
        
        return current_streak, max_win_streak, max_lose_streak
    
    def _get_strategy_breakdown(self, signals: List[SignalOutcome]) -> Dict[str, Dict]:
        """Get performance breakdown by strategy."""
        breakdown = {}
        
        strategies = set(s.strategy for s in signals)
        
        for strategy in strategies:
            strat_signals = [s for s in signals if s.strategy == strategy]
            winners = [s for s in strat_signals if s.pnl_pct > 0]
            
            total = len(strat_signals)
            win_rate = len(winners) / total * 100 if total > 0 else 0
            total_pnl = sum(s.pnl_pct for s in strat_signals)
            
            breakdown[strategy] = {
                "signals": total,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(total_pnl / total, 2) if total > 0 else 0
            }
        
        return breakdown
    
    def _get_ticker_breakdown(self, signals: List[SignalOutcome]) -> Dict[str, Dict]:
        """Get performance breakdown by ticker."""
        breakdown = {}
        
        tickers = set(s.ticker for s in signals)
        
        for ticker in list(tickers)[:20]:  # Limit to top 20
            ticker_signals = [s for s in signals if s.ticker == ticker]
            winners = [s for s in ticker_signals if s.pnl_pct > 0]
            
            total = len(ticker_signals)
            win_rate = len(winners) / total * 100 if total > 0 else 0
            total_pnl = sum(s.pnl_pct for s in ticker_signals)
            
            breakdown[ticker] = {
                "signals": total,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2)
            }
        
        return breakdown
    
    def format_stats_report(self, stats: PerformanceStats) -> str:
        """Format performance stats as readable report."""
        lines = []
        
        lines.append(f"📊 **Performance Report** - {stats.period.replace('_', ' ').title()}")
        lines.append("")
        
        # Summary
        win_emoji = "🟢" if stats.win_rate >= 50 else "🟡" if stats.win_rate >= 40 else "🔴"
        lines.append(f"**Win Rate:** {win_emoji} {stats.win_rate:.1f}%")
        lines.append(f"**Total P&L:** {'+' if stats.total_pnl_pct >= 0 else ''}{stats.total_pnl_pct:.2f}%")
        lines.append("")
        
        # Trade counts
        lines.append("**Trades:**")
        lines.append(f"  ✅ Winners: {stats.winners}")
        lines.append(f"  ❌ Losers: {stats.losers}")
        lines.append(f"  ➡️ Break-even: {stats.break_even}")
        lines.append(f"  🔵 Active: {stats.active}")
        lines.append("")
        
        # P&L details
        lines.append("**P&L Details:**")
        lines.append(f"  Avg Winner: +{stats.avg_winner_pct:.2f}%")
        lines.append(f"  Avg Loser: {stats.avg_loser_pct:.2f}%")
        lines.append(f"  Largest Win: +{stats.largest_winner_pct:.2f}%")
        lines.append(f"  Largest Loss: {stats.largest_loser_pct:.2f}%")
        lines.append("")
        
        # Risk metrics
        lines.append("**Risk Metrics:**")
        lines.append(f"  Profit Factor: {stats.profit_factor:.2f}")
        lines.append(f"  Expectancy: {'+' if stats.expectancy >= 0 else ''}{stats.expectancy:.2f}%")
        lines.append("")
        
        # Streaks
        streak_text = f"+{stats.current_streak} wins" if stats.current_streak > 0 else f"{stats.current_streak} losses" if stats.current_streak < 0 else "neutral"
        lines.append(f"**Current Streak:** {streak_text}")
        lines.append(f"**Best Win Streak:** {stats.max_win_streak}")
        lines.append("")
        
        # Strategy breakdown
        if stats.strategy_breakdown:
            lines.append("**By Strategy:**")
            for strat, data in sorted(stats.strategy_breakdown.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
                emoji = "📈" if data['total_pnl'] > 0 else "📉"
                lines.append(f"  {emoji} {strat}: {data['win_rate']}% WR, {'+' if data['total_pnl'] >= 0 else ''}{data['total_pnl']}%")
        
        return "\n".join(lines)
    
    async def _save_signal(self, outcome: SignalOutcome):
        """Save signal to database."""
        # Implementation depends on database structure
        pass
    
    async def _update_signal(self, outcome: SignalOutcome):
        """Update signal in database."""
        # Implementation depends on database structure
        pass
    
    async def load_from_db(self):
        """Load historical signals from database."""
        # Implementation depends on database structure
        pass
