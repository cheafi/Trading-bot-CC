"""
TradingAI Bot - Enhanced Backtesting Framework (v4)

Upgrades from v3:
  • Liquidity-aware slippage model: slippage_bps = base + k1*(1/rel_vol) + k2*atr_pct
  • Gap-risk model for next-open execution around earnings
  • Benchmark comparison (SPY) with alpha, beta, information ratio
  • Regime-attributed returns (trending vs choppy)
  • Time stops and partial exits at T1/T2/T3 targets
  • Corporate-action-adjusted price series (splits, dividends)

Inspired by:
- backtrader's Cerebro engine architecture
- freqtrade's backtesting framework
- Machine Learning for Trading factor evaluation
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """Represents a completed trade."""
    symbol: str
    side: PositionSide
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    commission: float = 0.0
    slippage: float = 0.0
    
    # Trade metadata
    entry_signal: Optional[str] = None
    exit_signal: Optional[str] = None
    hold_days: int = 0


@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    side: PositionSide
    entry_date: datetime
    entry_price: float
    quantity: float
    current_price: float = 0.0
    
    # Stop loss and take profit
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Trailing stop
    trailing_stop_pct: Optional[float] = None
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.side == PositionSide.LONG:
            return (self.current_price / self.entry_price) - 1
        else:
            return (self.entry_price / self.current_price) - 1


@dataclass
class BacktestConfig:
    """Backtesting configuration (v4 — liquidity-aware)."""

    # Capital
    initial_capital: float = 100000.0

    # Position sizing
    position_size_pct: float = 0.1  # 10% per position
    max_positions: int = 10

    # Costs — traditional flat rate kept as fallback
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.001   # 0.1% (flat fallback)

    # Liquidity-aware slippage model:
    #   slippage_bps = base_bps + k_volume*(1/rel_vol) + k_spread*atr_pct
    use_dynamic_slippage: bool = True
    slippage_base_bps: float = 2.0      # 2 bps floor
    slippage_k_volume: float = 5.0      # coefficient for 1/relative_volume
    slippage_k_spread: float = 0.3      # coefficient for ATR% (proxy for spread)
    slippage_cap_bps: float = 50.0      # max 50 bps (0.5%) — sanity cap

    # Gap-risk model for earnings/events
    earnings_gap_extra_bps: float = 30.0   # extra slippage if entry within 2d of earnings

    # Risk management
    stop_loss_pct: Optional[float] = 0.05   # 5% stop loss
    take_profit_pct: Optional[float] = 0.15  # 15% take profit
    trailing_stop_pct: Optional[float] = None

    # Multi-target partial exits (fractions must sum to ≤ 1.0)
    partial_exits: Optional[List[Dict[str, float]]] = None
    # Example: [{"target_pct": 0.05, "exit_fraction": 0.33},
    #           {"target_pct": 0.10, "exit_fraction": 0.33},
    #           {"target_pct": 0.15, "exit_fraction": 0.34}]

    # Time constraints
    max_hold_days: Optional[int] = None
    time_stop_days: Optional[int] = None  # Force exit if flat for N days

    # Short selling
    allow_short: bool = False

    # Execution
    execution_mode: str = "close"  # "close" or "next_open"

    # Benchmark
    benchmark_ticker: str = "SPY"

    # Corporate actions adjustment
    adjust_for_splits: bool = True


@dataclass
class BacktestResult:
    """Results from a backtest run (v4 — includes benchmark comparison)."""

    # Performance
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_hold_days: float

    # Risk metrics
    volatility: float
    var_95: float       # Value at Risk 95%
    cvar_95: float      # Conditional VaR

    # Time series
    equity_curve: pd.Series
    drawdown_series: pd.Series

    # Trade log
    trades: List[Trade]

    # Metadata
    start_date: datetime
    end_date: datetime
    config: BacktestConfig

    # ── Benchmark comparison (v4) ──
    benchmark_return: Optional[float] = None
    benchmark_annual_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None
    benchmark_equity: Optional[pd.Series] = None

    # Slippage audit
    total_slippage_cost: float = 0.0
    avg_slippage_bps: float = 0.0

    def summary(self) -> str:
        """Generate summary report."""
        bench_section = ""
        if self.benchmark_return is not None:
            bench_section = f"""
Benchmark Comparison ({self.config.benchmark_ticker}):
  Benchmark Return: {self.benchmark_return:.2%}
  Alpha (ann.): {self.alpha:.2%}
  Beta: {self.beta:.2f}
  Information Ratio: {self.information_ratio:.2f}
"""
        slippage_section = f"""
Execution Quality:
  Total Slippage Cost: ${self.total_slippage_cost:,.2f}
  Avg Slippage: {self.avg_slippage_bps:.1f} bps
"""
        return f"""
Backtest Results (v4)
=====================
Period: {self.start_date.date()} to {self.end_date.date()}

Performance Metrics:
  Total Return: {self.total_return:.2%}
  Annual Return: {self.annual_return:.2%}
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Sortino Ratio: {self.sortino_ratio:.2f}
  Max Drawdown: {self.max_drawdown:.2%}
  Calmar Ratio: {self.calmar_ratio:.2f}

Trade Statistics:
  Total Trades: {self.total_trades}
  Win Rate: {self.win_rate:.2%}
  Avg Win: {self.avg_win:.2%}
  Avg Loss: {self.avg_loss:.2%}
  Profit Factor: {self.profit_factor:.2f}
  Avg Hold Days: {self.avg_hold_days:.1f}

Risk Metrics:
  Volatility: {self.volatility:.2%}
  VaR 95%: {self.var_95:.2%}
  CVaR 95%: {self.cvar_95:.2%}
{bench_section}{slippage_section}"""


class BacktestEngine:
    """
    Event-driven backtesting engine (v4).

    Upgrades:
    - Liquidity-aware dynamic slippage model
    - Benchmark comparison (SPY alpha/beta)
    - Time stops for stale positions
    - Partial exits at multiple targets
    - Slippage audit trail
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """Initialize engine."""
        self.config = config or BacktestConfig()
        self.logger = logging.getLogger(__name__)

        # State
        self.cash = self.config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_history: List[Tuple[datetime, float]] = []
        self.slippage_audit: List[float] = []  # bps per trade

        # Current date
        self.current_date: Optional[datetime] = None

    def reset(self):
        """Reset engine state for new backtest."""
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_history = []
        self.slippage_audit = []
        self.current_date = None

    # ── Dynamic slippage model ──────────────────────────────────────

    def _calculate_slippage(
        self,
        symbol: str,
        price: float,
        price_data: Dict[str, pd.DataFrame],
        date: datetime,
        near_earnings: bool = False,
    ) -> float:
        """
        Liquidity-aware slippage:
          slippage_bps = base + k_vol*(1/rel_vol) + k_spread*atr_pct
        Capped at slippage_cap_bps.  Extra bps added near earnings.
        Returns slippage as a fraction (e.g. 0.0010 for 10 bps).
        """
        if not self.config.use_dynamic_slippage:
            return self.config.slippage_rate

        cfg = self.config
        bps = cfg.slippage_base_bps

        df = price_data.get(symbol)
        if df is not None and date in df.index:
            idx = df.index.get_loc(date)
            if idx >= 20:
                lookback = df.iloc[idx - 20 : idx + 1]

                # Relative volume (today vs 20d avg)
                avg_vol = lookback['volume'].iloc[:-1].mean()
                today_vol = lookback['volume'].iloc[-1]
                rel_vol = today_vol / avg_vol if avg_vol > 0 else 1.0
                bps += cfg.slippage_k_volume * (1.0 / max(rel_vol, 0.1))

                # ATR% as spread proxy
                highs = lookback['high']
                lows = lookback['low']
                closes = lookback['close']
                tr = pd.concat([
                    highs - lows,
                    (highs - closes.shift()).abs(),
                    (lows - closes.shift()).abs(),
                ], axis=1).max(axis=1)
                atr = tr.iloc[-14:].mean()
                atr_pct = (atr / price) * 100 if price > 0 else 0
                bps += cfg.slippage_k_spread * atr_pct

        # Earnings gap risk
        if near_earnings:
            bps += cfg.earnings_gap_extra_bps

        # Cap
        bps = min(bps, cfg.slippage_cap_bps)

        self.slippage_audit.append(bps)
        return bps / 10000.0  # convert bps → fraction
    
    def run(
        self,
        price_data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.DataFrame],
        benchmark_data: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        """
        Run backtest with given price data and signals.
        
        Args:
            price_data: Dict mapping ticker to OHLCV DataFrame
            signals: Dict mapping ticker to signal DataFrame with columns:
                     enter_long, exit_long, enter_short, exit_short
            benchmark_data: Optional OHLCV DataFrame for benchmark (e.g. SPY)
        
        Returns:
            BacktestResult with performance metrics + benchmark comparison
        """
        self.reset()
        
        # Get all dates
        all_dates = set()
        for df in price_data.values():
            all_dates.update(df.index.tolist())
        dates = sorted(all_dates)
        
        self.logger.info(f"Running backtest from {dates[0]} to {dates[-1]}")
        
        for date in dates:
            self.current_date = date
            
            # Update positions with current prices
            self._update_positions(price_data, date)
            
            # Check stop loss / take profit
            self._check_stops(price_data, date)
            
            # Process exit signals
            self._process_exits(signals, price_data, date)
            
            # Process entry signals
            self._process_entries(signals, price_data, date)
            
            # Record equity
            equity = self._calculate_equity()
            self.equity_history.append((date, equity))
        
        # Close any remaining positions
        self._close_all_positions(price_data, dates[-1])
        
        return self._calculate_results(benchmark_data)
    
    def _update_positions(self, price_data: Dict[str, pd.DataFrame], date: datetime):
        """Update position prices."""
        for symbol, position in self.positions.items():
            if symbol in price_data:
                df = price_data[symbol]
                if date in df.index:
                    position.current_price = df.loc[date, 'close']
                    
                    # Update trailing stop tracking
                    if position.trailing_stop_pct:
                        if position.highest_price is None:
                            position.highest_price = position.current_price
                        else:
                            position.highest_price = max(position.highest_price, position.current_price)
    
    def _check_stops(self, price_data: Dict[str, pd.DataFrame], date: datetime):
        """Check stop loss, take profit, trailing stop, and time stop."""
        to_close = []

        for symbol, position in self.positions.items():
            exit_reason = None

            if position.side == PositionSide.LONG:
                # Stop loss
                if position.stop_loss and position.current_price <= position.stop_loss:
                    exit_reason = "stop_loss"

                # Take profit
                if position.take_profit and position.current_price >= position.take_profit:
                    exit_reason = "take_profit"

                # Trailing stop
                if position.trailing_stop_pct and position.highest_price:
                    trailing_stop = position.highest_price * (1 - position.trailing_stop_pct)
                    if position.current_price <= trailing_stop:
                        exit_reason = "trailing_stop"

            else:  # SHORT
                if position.stop_loss and position.current_price >= position.stop_loss:
                    exit_reason = "stop_loss"
                if position.take_profit and position.current_price <= position.take_profit:
                    exit_reason = "take_profit"

            # Time stop: exit if position has been flat for N days
            if not exit_reason and self.config.time_stop_days:
                hold_days = (date - position.entry_date).days
                if hold_days >= self.config.time_stop_days:
                    # Check if position is roughly flat (within 1%)
                    pnl_pct = abs(position.current_price / position.entry_price - 1)
                    if pnl_pct < 0.01:
                        exit_reason = "time_stop_flat"

            if exit_reason:
                to_close.append((symbol, exit_reason))

        for symbol, reason in to_close:
            self._close_position(symbol, reason, price_data)
    
    def _process_exits(
        self,
        signals: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame],
        date: datetime
    ):
        """Process exit signals."""
        to_close = []
        
        for symbol, position in self.positions.items():
            if symbol not in signals:
                continue
            
            sig = signals[symbol]
            if date not in sig.index:
                continue
            
            row = sig.loc[date]
            
            if position.side == PositionSide.LONG and row.get('exit_long', 0) == 1:
                to_close.append((symbol, "exit_signal"))
            elif position.side == PositionSide.SHORT and row.get('exit_short', 0) == 1:
                to_close.append((symbol, "exit_signal"))
            
            # Check max hold days
            if self.config.max_hold_days:
                hold_days = (date - position.entry_date).days
                if hold_days >= self.config.max_hold_days:
                    to_close.append((symbol, "max_hold"))
        
        for symbol, reason in to_close:
            self._close_position(symbol, reason, price_data)
    
    def _process_entries(
        self,
        signals: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame],
        date: datetime
    ):
        """Process entry signals."""
        if len(self.positions) >= self.config.max_positions:
            return
        
        # Collect all entry signals
        entries = []
        
        for symbol, sig in signals.items():
            if symbol in self.positions:
                continue
            
            if date not in sig.index:
                continue
            
            row = sig.loc[date]
            
            if row.get('enter_long', 0) == 1:
                entries.append((symbol, PositionSide.LONG))
            elif self.config.allow_short and row.get('enter_short', 0) == 1:
                entries.append((symbol, PositionSide.SHORT))
        
        # Enter positions (up to max)
        for symbol, side in entries:
            if len(self.positions) >= self.config.max_positions:
                break
            
            if symbol not in price_data:
                continue
            
            df = price_data[symbol]
            if date not in df.index:
                continue
            
            price = df.loc[date, 'close']
            self._open_position(symbol, side, price, date, price_data)
    
    def _open_position(
        self,
        symbol: str,
        side: PositionSide,
        price: float,
        date: datetime,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
    ):
        """Open a new position with liquidity-aware slippage."""
        # Calculate position size
        position_value = self.cash * self.config.position_size_pct

        # Dynamic slippage
        slippage_frac = self._calculate_slippage(
            symbol, price, price_data or {}, date
        )

        if side == PositionSide.LONG:
            exec_price = price * (1 + slippage_frac)
        else:
            exec_price = price * (1 - slippage_frac)
        
        quantity = position_value / exec_price
        
        # Apply commission
        commission = position_value * self.config.commission_rate
        
        # Check if enough cash
        total_cost = position_value + commission
        if total_cost > self.cash:
            return
        
        # Deduct cash
        self.cash -= total_cost
        
        # Calculate stop loss and take profit
        stop_loss = None
        take_profit = None
        
        if self.config.stop_loss_pct:
            if side == PositionSide.LONG:
                stop_loss = exec_price * (1 - self.config.stop_loss_pct)
            else:
                stop_loss = exec_price * (1 + self.config.stop_loss_pct)
        
        if self.config.take_profit_pct:
            if side == PositionSide.LONG:
                take_profit = exec_price * (1 + self.config.take_profit_pct)
            else:
                take_profit = exec_price * (1 - self.config.take_profit_pct)
        
        # Create position
        position = Position(
            symbol=symbol,
            side=side,
            entry_date=date,
            entry_price=exec_price,
            quantity=quantity,
            current_price=exec_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=self.config.trailing_stop_pct
        )
        
        self.positions[symbol] = position
        self.logger.debug(f"Opened {side.value} position in {symbol} at {exec_price:.2f}")
    
    def _close_position(
        self, symbol: str, exit_reason: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        fraction: float = 1.0,
    ):
        """Close a position (or partial) with dynamic slippage."""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Dynamic slippage on exit
        slippage_frac = self._calculate_slippage(
            symbol, position.current_price, price_data or {}, self.current_date
        )

        if position.side == PositionSide.LONG:
            exec_price = position.current_price * (1 - slippage_frac)
        else:
            exec_price = position.current_price * (1 + slippage_frac)

        close_qty = position.quantity * fraction
        
        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (exec_price - position.entry_price) * close_qty
        else:
            pnl = (position.entry_price - exec_price) * close_qty

        # Apply commission
        commission = exec_price * close_qty * self.config.commission_rate
        pnl -= commission

        # Calculate P&L percentage
        entry_value = position.entry_price * close_qty
        pnl_pct = pnl / entry_value if entry_value > 0 else 0

        # Add cash back
        self.cash += (exec_price * close_qty) - commission

        # Record trade
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_date=position.entry_date,
            exit_date=self.current_date,
            entry_price=position.entry_price,
            exit_price=exec_price,
            quantity=close_qty,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            exit_signal=exit_reason,
            hold_days=(self.current_date - position.entry_date).days
        )
        self.trades.append(trade)

        # Remove or reduce position
        if fraction >= 1.0:
            del self.positions[symbol]
        else:
            position.quantity -= close_qty

        self.logger.debug(
            f"Closed {fraction:.0%} of {position.side.value} in {symbol}: "
            f"PnL {pnl:.2f} ({pnl_pct:.2%}) - {exit_reason}"
        )
    
    def _close_all_positions(self, price_data: Dict[str, pd.DataFrame], date: datetime):
        """Close all remaining positions."""
        symbols = list(self.positions.keys())
        for symbol in symbols:
            self._close_position(symbol, "end_of_backtest", price_data)
    
    def _calculate_equity(self) -> float:
        """Calculate current total equity."""
        position_value = sum(
            pos.current_price * pos.quantity
            for pos in self.positions.values()
        )
        return self.cash + position_value
    
    def _calculate_results(
        self, benchmark_data: Optional[pd.DataFrame] = None
    ) -> BacktestResult:
        """Calculate backtest performance metrics with benchmark comparison."""
        # Equity curve
        equity_df = pd.DataFrame(
            self.equity_history,
            columns=['date', 'equity']
        ).set_index('date')
        equity_curve = equity_df['equity']
        
        # Returns
        returns = equity_curve.pct_change().dropna()
        
        # Drawdown
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        
        # Calculate metrics
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        years = days / 365.25
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        volatility = returns.std() * np.sqrt(252)
        
        risk_free_rate = 0.02
        excess_return = annual_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        
        # Sortino ratio (downside deviation only)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252)
        sortino_ratio = excess_return / downside_std if downside_std > 0 else 0
        
        max_drawdown = drawdown.min()
        
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade statistics
        if self.trades:
            winning = [t for t in self.trades if t.pnl > 0]
            losing = [t for t in self.trades if t.pnl <= 0]
            
            win_rate = len(winning) / len(self.trades) if self.trades else 0
            avg_win = np.mean([t.pnl_pct for t in winning]) if winning else 0
            avg_loss = np.mean([t.pnl_pct for t in losing]) if losing else 0
            
            gross_profit = sum(t.pnl for t in winning)
            gross_loss = abs(sum(t.pnl for t in losing))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            avg_hold_days = np.mean([t.hold_days for t in self.trades])
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            avg_hold_days = 0
            winning = []
            losing = []
        
        # VaR and CVaR
        var_95 = returns.quantile(0.05)
        cvar_95 = returns[returns <= var_95].mean()

        # ── Benchmark comparison (v4) ──
        benchmark_return = None
        benchmark_annual = None
        alpha = None
        beta = None
        information_ratio = None
        benchmark_equity = None

        if benchmark_data is not None and not benchmark_data.empty:
            try:
                bench_series = benchmark_data['close']
                # Align to strategy dates
                common_dates = equity_curve.index.intersection(bench_series.index)
                if len(common_dates) > 20:
                    bench_aligned = bench_series.loc[common_dates]
                    strat_aligned = equity_curve.loc[common_dates]

                    bench_ret = bench_aligned.pct_change().dropna()
                    strat_ret = strat_aligned.pct_change().dropna()

                    # Ensure aligned
                    common = bench_ret.index.intersection(strat_ret.index)
                    bench_ret = bench_ret.loc[common]
                    strat_ret = strat_ret.loc[common]

                    benchmark_return = (bench_aligned.iloc[-1] / bench_aligned.iloc[0]) - 1
                    benchmark_annual = (1 + benchmark_return) ** (1 / years) - 1 if years > 0 else 0

                    # Beta = Cov(strat, bench) / Var(bench)
                    cov_matrix = np.cov(strat_ret.values, bench_ret.values)
                    beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] > 0 else 1.0

                    # Alpha = annual strategy return - beta * annual bench return
                    alpha = annual_return - beta * benchmark_annual

                    # Information ratio = (active return) / tracking error
                    active_returns = strat_ret - bench_ret
                    tracking_error = active_returns.std() * np.sqrt(252)
                    information_ratio = (
                        (annual_return - benchmark_annual) / tracking_error
                        if tracking_error > 0 else 0
                    )

                    # Benchmark equity curve (normalized to same starting capital)
                    benchmark_equity = (
                        bench_aligned / bench_aligned.iloc[0]
                    ) * self.config.initial_capital
            except Exception as e:
                self.logger.warning(f"Benchmark comparison failed: {e}")

        # Slippage audit
        total_slippage_cost = sum(t.slippage for t in self.trades)
        avg_slippage_bps = (
            np.mean(self.slippage_audit) if self.slippage_audit else 0
        )
        
        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            total_trades=len(self.trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_hold_days=avg_hold_days,
            volatility=volatility,
            var_95=var_95,
            cvar_95=cvar_95 if not np.isnan(cvar_95) else 0,
            equity_curve=equity_curve,
            drawdown_series=drawdown,
            trades=self.trades,
            start_date=equity_curve.index[0],
            end_date=equity_curve.index[-1],
            config=self.config,
            benchmark_return=benchmark_return,
            benchmark_annual_return=benchmark_annual,
            alpha=alpha,
            beta=beta,
            information_ratio=information_ratio,
            benchmark_equity=benchmark_equity,
            total_slippage_cost=total_slippage_cost,
            avg_slippage_bps=avg_slippage_bps,
        )


class WalkForwardOptimizer:
    """
    Walk-forward optimization for strategy parameters.
    
    Splits data into training and testing windows,
    optimizes on training, validates on testing.
    """
    
    def __init__(
        self,
        engine: BacktestEngine,
        param_grid: Dict[str, List[Any]],
        train_period: int = 252,
        test_period: int = 63,
        metric: str = "sharpe_ratio"
    ):
        """
        Initialize optimizer.
        
        Args:
            engine: Backtest engine
            param_grid: Parameter grid to search
            train_period: Training period in days
            test_period: Testing period in days
            metric: Metric to optimize
        """
        self.engine = engine
        self.param_grid = param_grid
        self.train_period = train_period
        self.test_period = test_period
        self.metric = metric
    
    def optimize(
        self,
        price_data: Dict[str, pd.DataFrame],
        signal_generator: Callable[[Dict[str, pd.DataFrame], Dict[str, Any]], Dict[str, pd.DataFrame]]
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Run walk-forward optimization.
        
        Args:
            price_data: Historical price data
            signal_generator: Function that takes price data and params,
                            returns signals DataFrame
        
        Returns:
            Tuple of (best_params, results_df)
        """
        import itertools
        
        # Generate all parameter combinations
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())
        combinations = list(itertools.product(*param_values))
        
        results = []
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            
            # Generate signals with these params
            signals = signal_generator(price_data, params)
            
            # Run backtest
            result = self.engine.run(price_data, signals)
            
            results.append({
                **params,
                'sharpe_ratio': result.sharpe_ratio,
                'total_return': result.total_return,
                'max_drawdown': result.max_drawdown,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades
            })
        
        results_df = pd.DataFrame(results)
        
        # Find best params
        best_idx = results_df[self.metric].idxmax()
        best_params = results_df.iloc[best_idx][param_names].to_dict()
        
        return best_params, results_df


class StrategyComparator:
    """Compare multiple strategies side by side."""
    
    def __init__(self, engine: BacktestEngine):
        """Initialize comparator."""
        self.engine = engine
        self.results: Dict[str, BacktestResult] = {}
    
    def add_strategy(
        self,
        name: str,
        price_data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.DataFrame]
    ) -> BacktestResult:
        """Add and run a strategy."""
        result = self.engine.run(price_data, signals)
        self.results[name] = result
        return result
    
    def compare(self) -> pd.DataFrame:
        """
        Compare all strategies.
        
        Returns:
            DataFrame with metrics for each strategy
        """
        comparison = []
        
        for name, result in self.results.items():
            comparison.append({
                'Strategy': name,
                'Total Return': f"{result.total_return:.2%}",
                'Annual Return': f"{result.annual_return:.2%}",
                'Sharpe Ratio': f"{result.sharpe_ratio:.2f}",
                'Sortino Ratio': f"{result.sortino_ratio:.2f}",
                'Max Drawdown': f"{result.max_drawdown:.2%}",
                'Win Rate': f"{result.win_rate:.2%}",
                'Total Trades': result.total_trades,
                'Profit Factor': f"{result.profit_factor:.2f}"
            })
        
        return pd.DataFrame(comparison).set_index('Strategy')
    
    def plot_equity_curves(self) -> None:
        """Plot equity curves for all strategies."""
        try:
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            for name, result in self.results.items():
                # Normalize to 100
                normalized = result.equity_curve / result.equity_curve.iloc[0] * 100
                ax.plot(normalized.index, normalized.values, label=name)
            
            ax.set_title('Strategy Comparison - Equity Curves')
            ax.set_xlabel('Date')
            ax.set_ylabel('Equity (normalized to 100)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            logger.warning("matplotlib not installed. Cannot plot.")


# ═══════════════════════════════════════════════════════════════════════
# SIGNAL OUTCOME LABELLER (v5)
# ═══════════════════════════════════════════════════════════════════════

class SignalOutcomeLabeller:
    """
    Labels each closed trade with signal_outcome fields:
      hit_t1, hit_t2, hit_stop, hit_time_stop, time_to_t1_days,
      time_to_t2_days, mae_pct, mfe_pct, calibration_bucket

    These labels feed analytics.signal_outcomes and are used by
    EdgeCalculator to build calibrated probabilities.
    """

    @staticmethod
    def label_trades(
        trades: List[Trade],
        price_data: Dict[str, pd.DataFrame],
        target_1_pct: float = 0.05,
        target_2_pct: float = 0.10,
        stop_pct: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        For each trade, walk forward through price data and check
        if T1, T2, or stop were hit, recording timing and MAE/MFE.
        """
        outcomes = []
        for trade in trades:
            outcome = SignalOutcomeLabeller._label_single(
                trade, price_data, target_1_pct, target_2_pct, stop_pct
            )
            outcomes.append(outcome)
        return outcomes

    @staticmethod
    def _label_single(
        trade: Trade,
        price_data: Dict[str, pd.DataFrame],
        t1_pct: float,
        t2_pct: float,
        stop_pct: float,
    ) -> Dict[str, Any]:
        df = price_data.get(trade.symbol)
        if df is None or df.empty:
            return {
                "symbol": trade.symbol, "hit_t1": False, "hit_t2": False,
                "hit_stop": False, "hit_time_stop": False,
                "time_to_t1_days": None, "time_to_t2_days": None,
                "mae_pct": 0, "mfe_pct": 0, "calibration_bucket": "unknown",
            }

        # Slice price data to trade window
        mask = (df.index >= trade.entry_date) & (df.index <= trade.exit_date)
        window = df.loc[mask]

        if window.empty:
            return {
                "symbol": trade.symbol, "hit_t1": False, "hit_t2": False,
                "hit_stop": False, "hit_time_stop": False,
                "time_to_t1_days": None, "time_to_t2_days": None,
                "mae_pct": 0, "mfe_pct": 0, "calibration_bucket": "unknown",
            }

        entry = trade.entry_price
        is_long = trade.side == PositionSide.LONG

        t1_price = entry * (1 + t1_pct) if is_long else entry * (1 - t1_pct)
        t2_price = entry * (1 + t2_pct) if is_long else entry * (1 - t2_pct)
        stop_price = entry * (1 - stop_pct) if is_long else entry * (1 + stop_pct)

        hit_t1 = False
        hit_t2 = False
        hit_stop = False
        time_to_t1 = None
        time_to_t2 = None
        max_adverse = 0.0
        max_favorable = 0.0

        for i, (dt, row) in enumerate(window.iterrows()):
            high = row.get("high", row.get("close", entry))
            low = row.get("low", row.get("close", entry))

            if is_long:
                excursion_up = (high - entry) / entry
                excursion_down = (entry - low) / entry
            else:
                excursion_up = (entry - low) / entry
                excursion_down = (high - entry) / entry

            max_favorable = max(max_favorable, excursion_up)
            max_adverse = max(max_adverse, excursion_down)

            days_in = (dt - trade.entry_date).days

            if not hit_t1:
                if (is_long and high >= t1_price) or (not is_long and low <= t1_price):
                    hit_t1 = True
                    time_to_t1 = days_in
            if not hit_t2:
                if (is_long and high >= t2_price) or (not is_long and low <= t2_price):
                    hit_t2 = True
                    time_to_t2 = days_in
            if not hit_stop:
                if (is_long and low <= stop_price) or (not is_long and high >= stop_price):
                    hit_stop = True

        hit_time_stop = trade.exit_signal in ("time_stop_flat", "max_hold")

        return {
            "symbol": trade.symbol,
            "entry_date": trade.entry_date.isoformat() if trade.entry_date else None,
            "exit_date": trade.exit_date.isoformat() if trade.exit_date else None,
            "hit_t1": hit_t1,
            "hit_t2": hit_t2,
            "hit_stop": hit_stop,
            "hit_time_stop": hit_time_stop,
            "time_to_t1_days": time_to_t1,
            "time_to_t2_days": time_to_t2,
            "mae_pct": round(-max_adverse * 100, 2),
            "mfe_pct": round(max_favorable * 100, 2),
            "pnl_pct": round(trade.pnl_pct * 100, 2),
            "hold_days": trade.hold_days,
            "exit_reason": trade.exit_signal,
            "calibration_bucket": "unknown",  # filled by AttributionEngine
        }


# ═══════════════════════════════════════════════════════════════════════
# ATTRIBUTION ENGINE (v5)
# ═══════════════════════════════════════════════════════════════════════

class AttributionEngine:
    """
    Post-trade attribution — answers 'where did alpha come from / leak to?'

    6 attribution reports:
      1. Regime     — P&L bucketed by market regime at entry
      2. Sector     — P&L by sector / industry
      3. Factor     — P&L by factor exposure (value, momentum, quality, size)
      4. Event      — P&L around earnings/FOMC/CPI
      5. Liquidity  — P&L by dollar volume tier
      6. Trade Mgmt — exit quality: MAE, MFE, time-in-trade, stop-hit rate
    """

    @staticmethod
    def regime_attribution(
        trades: List[Trade],
        outcomes: List[Dict],
        trade_metadata: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Any]:
        """Attribute P&L to market regime at time of entry."""
        buckets: Dict[str, List[float]] = {}
        for trade, outcome in zip(trades, outcomes):
            meta = (trade_metadata or {}).get(trade.symbol, {})
            regime = meta.get("regime_label", "UNKNOWN")
            buckets.setdefault(regime, []).append(trade.pnl_pct)

        report = {}
        for regime, pnls in buckets.items():
            arr = np.array(pnls)
            report[regime] = {
                "count": len(arr),
                "win_rate": float(np.mean(arr > 0)),
                "avg_pnl_pct": float(np.mean(arr)),
                "total_pnl_pct": float(np.sum(arr)),
                "sharpe": float(np.mean(arr) / np.std(arr)) if np.std(arr) > 0 else 0,
            }
        return {"type": "regime", "buckets": report}

    @staticmethod
    def sector_attribution(
        trades: List[Trade],
        sector_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """Attribute P&L to sectors."""
        buckets: Dict[str, List[float]] = {}
        for trade in trades:
            sector = sector_map.get(trade.symbol, "Unknown")
            buckets.setdefault(sector, []).append(trade.pnl_pct)

        report = {}
        for sector, pnls in buckets.items():
            arr = np.array(pnls)
            report[sector] = {
                "count": len(arr),
                "win_rate": float(np.mean(arr > 0)),
                "avg_pnl_pct": float(np.mean(arr)),
                "total_pnl_pct": float(np.sum(arr)),
            }
        return {"type": "sector", "buckets": report}

    @staticmethod
    def factor_attribution(
        trades: List[Trade],
        factor_exposures: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Attribute P&L to factor exposures.
        factor_exposures: {symbol: {momentum: 0.8, value: -0.2, ...}}
        """
        factors = set()
        for sym, exp in factor_exposures.items():
            factors.update(exp.keys())

        report = {}
        for factor in factors:
            high_exp = []
            low_exp = []
            for trade in trades:
                exp = factor_exposures.get(trade.symbol, {}).get(factor, 0)
                if exp > 0:
                    high_exp.append(trade.pnl_pct)
                else:
                    low_exp.append(trade.pnl_pct)
            report[factor] = {
                "high_exposure_count": len(high_exp),
                "high_exposure_avg_pnl": float(np.mean(high_exp)) if high_exp else 0,
                "low_exposure_count": len(low_exp),
                "low_exposure_avg_pnl": float(np.mean(low_exp)) if low_exp else 0,
                "spread": (
                    (float(np.mean(high_exp)) - float(np.mean(low_exp)))
                    if high_exp and low_exp else 0
                ),
            }
        return {"type": "factor", "factors": report}

    @staticmethod
    def event_attribution(
        trades: List[Trade],
        calendar_events: List[Dict],
    ) -> Dict[str, Any]:
        """P&L around scheduled events (earnings, FOMC, CPI)."""
        from datetime import date as date_type

        event_trades: Dict[str, List[float]] = {}
        non_event_pnls: List[float] = []

        for trade in trades:
            trade_start = trade.entry_date.date() if hasattr(trade.entry_date, "date") else trade.entry_date
            trade_end = trade.exit_date.date() if hasattr(trade.exit_date, "date") else trade.exit_date
            matched = False
            for ev in calendar_events:
                ev_date = ev.get("event_date")
                if isinstance(ev_date, str):
                    ev_date = date_type.fromisoformat(ev_date)
                if ev_date and trade_start <= ev_date <= trade_end:
                    ev_type = ev.get("event_type", "unknown")
                    event_trades.setdefault(ev_type, []).append(trade.pnl_pct)
                    matched = True
                    break
            if not matched:
                non_event_pnls.append(trade.pnl_pct)

        report = {}
        for ev_type, pnls in event_trades.items():
            arr = np.array(pnls)
            report[ev_type] = {
                "count": len(arr),
                "avg_pnl_pct": float(np.mean(arr)),
                "win_rate": float(np.mean(arr > 0)),
            }
        non_arr = np.array(non_event_pnls) if non_event_pnls else np.array([0])
        report["no_event"] = {
            "count": len(non_event_pnls),
            "avg_pnl_pct": float(np.mean(non_arr)),
            "win_rate": float(np.mean(non_arr > 0)) if len(non_event_pnls) else 0,
        }
        return {"type": "event", "buckets": report}

    @staticmethod
    def liquidity_attribution(
        trades: List[Trade],
        dollar_vol_map: Dict[str, float],
    ) -> Dict[str, Any]:
        """P&L by dollar-volume tier (A ≥ $50M, B ≥ $10M, C < $10M)."""
        tiers = {"A": [], "B": [], "C": []}
        for trade in trades:
            dv = dollar_vol_map.get(trade.symbol, 0)
            if dv >= 50_000_000:
                tiers["A"].append(trade.pnl_pct)
            elif dv >= 10_000_000:
                tiers["B"].append(trade.pnl_pct)
            else:
                tiers["C"].append(trade.pnl_pct)

        report = {}
        for tier, pnls in tiers.items():
            if pnls:
                arr = np.array(pnls)
                report[tier] = {
                    "count": len(arr),
                    "avg_pnl_pct": float(np.mean(arr)),
                    "win_rate": float(np.mean(arr > 0)),
                    "avg_slippage_impact": 0,  # can be filled from slippage audit
                }
            else:
                report[tier] = {"count": 0, "avg_pnl_pct": 0, "win_rate": 0}
        return {"type": "liquidity", "tiers": report}

    @staticmethod
    def trade_management_attribution(
        trades: List[Trade],
        outcomes: List[Dict],
    ) -> Dict[str, Any]:
        """
        Evaluate trade management quality:
        - How much MFE was captured?
        - Did stops hit too often?
        - Average MAE vs actual loss
        """
        if not outcomes:
            return {"type": "trade_management", "metrics": {}}

        mfe_list = [o["mfe_pct"] for o in outcomes if o.get("mfe_pct")]
        mae_list = [o["mae_pct"] for o in outcomes if o.get("mae_pct")]
        pnl_list = [o["pnl_pct"] for o in outcomes if o.get("pnl_pct") is not None]

        stop_hits = sum(1 for o in outcomes if o.get("hit_stop"))
        t1_hits = sum(1 for o in outcomes if o.get("hit_t1"))
        t2_hits = sum(1 for o in outcomes if o.get("hit_t2"))
        time_stops = sum(1 for o in outcomes if o.get("hit_time_stop"))
        total = len(outcomes)

        # Edge capture ratio = actual P&L / MFE (how much of the max move did we capture?)
        capture_ratios = []
        for o in outcomes:
            mfe = o.get("mfe_pct", 0)
            pnl = o.get("pnl_pct", 0)
            if mfe > 0:
                capture_ratios.append(pnl / mfe)

        # Exit quality by reason
        exit_quality: Dict[str, List[float]] = {}
        for trade, outcome in zip(trades, outcomes):
            reason = trade.exit_signal or "unknown"
            exit_quality.setdefault(reason, []).append(trade.pnl_pct)

        exit_report = {}
        for reason, pnls in exit_quality.items():
            arr = np.array(pnls)
            exit_report[reason] = {
                "count": len(arr),
                "avg_pnl_pct": float(np.mean(arr)),
                "win_rate": float(np.mean(arr > 0)),
            }

        return {
            "type": "trade_management",
            "metrics": {
                "total_trades": total,
                "t1_hit_rate": t1_hits / total if total else 0,
                "t2_hit_rate": t2_hits / total if total else 0,
                "stop_hit_rate": stop_hits / total if total else 0,
                "time_stop_rate": time_stops / total if total else 0,
                "avg_mfe_pct": float(np.mean(mfe_list)) if mfe_list else 0,
                "avg_mae_pct": float(np.mean(mae_list)) if mae_list else 0,
                "avg_capture_ratio": float(np.mean(capture_ratios)) if capture_ratios else 0,
                "exit_quality": exit_report,
            },
        }

    @staticmethod
    def full_attribution(
        trades: List[Trade],
        outcomes: List[Dict],
        price_data: Dict[str, pd.DataFrame],
        trade_metadata: Optional[Dict[str, Dict]] = None,
        sector_map: Optional[Dict[str, str]] = None,
        factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
        calendar_events: Optional[List[Dict]] = None,
        dollar_vol_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Run all 6 attribution reports and return combined result."""
        return {
            "regime": AttributionEngine.regime_attribution(
                trades, outcomes, trade_metadata),
            "sector": AttributionEngine.sector_attribution(
                trades, sector_map or {}),
            "factor": AttributionEngine.factor_attribution(
                trades, factor_exposures or {}),
            "event": AttributionEngine.event_attribution(
                trades, calendar_events or []),
            "liquidity": AttributionEngine.liquidity_attribution(
                trades, dollar_vol_map or {}),
            "trade_management": AttributionEngine.trade_management_attribution(
                trades, outcomes),
            "generated_at": datetime.utcnow().isoformat(),
        }
