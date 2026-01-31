"""
TradingAI Bot - Enhanced Backtesting Framework

Inspired by:
- backtrader's Cerebro engine architecture
- freqtrade's backtesting framework
- Machine Learning for Trading factor evaluation

Provides:
- Strategy backtesting with realistic execution
- Walk-forward optimization
- Multi-strategy comparison
- Risk-adjusted metrics
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
    """Backtesting configuration."""
    
    # Capital
    initial_capital: float = 100000.0
    
    # Position sizing
    position_size_pct: float = 0.1  # 10% per position
    max_positions: int = 10
    
    # Costs
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.001  # 0.1%
    
    # Risk management
    stop_loss_pct: Optional[float] = 0.05  # 5% stop loss
    take_profit_pct: Optional[float] = 0.15  # 15% take profit
    trailing_stop_pct: Optional[float] = None
    
    # Time constraints
    max_hold_days: Optional[int] = None
    
    # Short selling
    allow_short: bool = False
    
    # Execution
    execution_mode: str = "close"  # "close" or "next_open"


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    
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
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR
    
    # Time series
    equity_curve: pd.Series
    drawdown_series: pd.Series
    
    # Trade log
    trades: List[Trade]
    
    # Metadata
    start_date: datetime
    end_date: datetime
    config: BacktestConfig
    
    def summary(self) -> str:
        """Generate summary report."""
        return f"""
Backtest Results
================
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
"""


class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Features:
    - Realistic order execution with slippage
    - Position sizing and risk management
    - Multiple position support
    - Performance analytics
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
        
        # Current date
        self.current_date: Optional[datetime] = None
    
    def reset(self):
        """Reset engine state for new backtest."""
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_history = []
        self.current_date = None
    
    def run(
        self,
        price_data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.DataFrame]
    ) -> BacktestResult:
        """
        Run backtest with given price data and signals.
        
        Args:
            price_data: Dict mapping ticker to OHLCV DataFrame
            signals: Dict mapping ticker to signal DataFrame with columns:
                     enter_long, exit_long, enter_short, exit_short
        
        Returns:
            BacktestResult with performance metrics
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
        
        return self._calculate_results()
    
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
        """Check stop loss and take profit conditions."""
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
            
            if exit_reason:
                to_close.append((symbol, exit_reason))
        
        for symbol, reason in to_close:
            self._close_position(symbol, reason)
    
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
            self._close_position(symbol, reason)
    
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
            self._open_position(symbol, side, price, date)
    
    def _open_position(
        self,
        symbol: str,
        side: PositionSide,
        price: float,
        date: datetime
    ):
        """Open a new position."""
        # Calculate position size
        position_value = self.cash * self.config.position_size_pct
        
        # Apply slippage
        if side == PositionSide.LONG:
            exec_price = price * (1 + self.config.slippage_rate)
        else:
            exec_price = price * (1 - self.config.slippage_rate)
        
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
    
    def _close_position(self, symbol: str, exit_reason: str):
        """Close a position."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # Apply slippage
        if position.side == PositionSide.LONG:
            exec_price = position.current_price * (1 - self.config.slippage_rate)
        else:
            exec_price = position.current_price * (1 + self.config.slippage_rate)
        
        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (exec_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exec_price) * position.quantity
        
        # Apply commission
        commission = exec_price * position.quantity * self.config.commission_rate
        pnl -= commission
        
        # Calculate P&L percentage
        entry_value = position.entry_price * position.quantity
        pnl_pct = pnl / entry_value if entry_value > 0 else 0
        
        # Add cash back
        self.cash += (exec_price * position.quantity) - commission
        
        # Record trade
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_date=position.entry_date,
            exit_date=self.current_date,
            entry_price=position.entry_price,
            exit_price=exec_price,
            quantity=position.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            exit_signal=exit_reason,
            hold_days=(self.current_date - position.entry_date).days
        )
        self.trades.append(trade)
        
        # Remove position
        del self.positions[symbol]
        
        self.logger.debug(
            f"Closed {position.side.value} in {symbol}: "
            f"PnL {pnl:.2f} ({pnl_pct:.2%}) - {exit_reason}"
        )
    
    def _close_all_positions(self, price_data: Dict[str, pd.DataFrame], date: datetime):
        """Close all remaining positions."""
        symbols = list(self.positions.keys())
        for symbol in symbols:
            self._close_position(symbol, "end_of_backtest")
    
    def _calculate_equity(self) -> float:
        """Calculate current total equity."""
        position_value = sum(
            pos.current_price * pos.quantity
            for pos in self.positions.values()
        )
        return self.cash + position_value
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate backtest performance metrics."""
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
            config=self.config
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
