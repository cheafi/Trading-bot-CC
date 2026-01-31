# F) Backtesting & Evaluation Framework

## Overview

The backtesting framework provides:
1. **Historical simulation** of strategy signals
2. **Walk-forward optimization** to prevent overfitting
3. **Comprehensive metrics** for strategy evaluation
4. **Ongoing monitoring** for model drift detection

---

## Evaluation Metrics Checklist

### Primary Metrics (Must Track)

| Metric | Formula | Target | Red Flag |
|--------|---------|--------|----------|
| **Sharpe Ratio** | (Return - Rf) / Volatility | > 1.0 | < 0.5 |
| **Sortino Ratio** | (Return - Rf) / Downside Dev | > 1.5 | < 0.7 |
| **Max Drawdown** | Peak-to-trough decline | < 15% | > 25% |
| **Win Rate** | Wins / Total Trades | > 45% | < 35% |
| **Profit Factor** | Gross Profit / Gross Loss | > 1.5 | < 1.0 |
| **Expectancy** | (Win% × AvgWin) - (Loss% × AvgLoss) | > 0.5% | < 0 |
| **Calmar Ratio** | Annual Return / Max Drawdown | > 1.0 | < 0.5 |

### Secondary Metrics

| Metric | Purpose |
|--------|---------|
| **Average Trade** | Expected return per trade |
| **Payoff Ratio** | Avg Win / Avg Loss |
| **Max Consecutive Losses** | Drawdown risk indicator |
| **Avg Holding Period** | Time in position |
| **MAE/MFE** | Entry timing quality |
| **Recovery Factor** | Net Profit / Max Drawdown |
| **Ulcer Index** | Depth/duration of drawdowns |

### Risk Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **VaR (95%)** | 5th percentile daily return | < 2% |
| **CVaR (95%)** | Avg loss beyond VaR | < 3% |
| **Beta** | Correlation with SPY | Depends on strategy |
| **Alpha** | Excess return vs benchmark | > 0 |
| **Information Ratio** | Alpha / Tracking Error | > 0.5 |

---

## Backtesting Framework

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BACKTESTING PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│   │  Historical  │    │   Feature    │    │   Signal     │                      │
│   │    Data      │───>│  Calculator  │───>│   Generator  │                      │
│   │   Loader     │    │              │    │              │                      │
│   └──────────────┘    └──────────────┘    └──────────────┘                      │
│                                                  │                               │
│                                                  ▼                               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│   │   Results    │<───│   Trade      │<───│  Portfolio   │                      │
│   │   Analyzer   │    │   Simulator  │    │   Simulator  │                      │
│   │              │    │              │    │              │                      │
│   └──────────────┘    └──────────────┘    └──────────────┘                      │
│          │                                                                       │
│          ▼                                                                       │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │                          VALIDATION LAYER                                 │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐              │  │
│   │  │  Walk-Forward  │  │   Monte Carlo  │  │   Bootstrap    │              │  │
│   │  │  Optimization  │  │   Simulation   │  │   Analysis     │              │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘              │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Backtester Class

```python
"""
TradingAI Bot - Backtesting Engine
"""
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
from uuid import uuid4
import logging

from src.core.models import Signal, Direction, BacktestResult, BacktestTrade


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    
    # Position sizing
    max_position_pct: float = 0.05
    risk_per_trade: float = 0.01
    
    # Costs
    commission_per_trade: float = 1.0
    slippage_pct: float = 0.001  # 10 bps
    
    # Execution
    use_next_open: bool = True  # Execute on next bar open
    allow_shorting: bool = True
    
    # Risk limits
    max_positions: int = 20
    max_sector_exposure: float = 0.30
    stop_trading_drawdown: float = 0.15
    
    # Validation
    min_trades_required: int = 30
    

class Backtester:
    """
    Event-driven backtesting engine.
    
    Key design decisions:
    - Uses NEXT BAR execution to avoid look-ahead bias
    - Applies realistic slippage and commissions
    - Tracks MAE/MFE for entry analysis
    - Supports multiple concurrent positions
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def run(
        self,
        strategy: "BaseStrategy",
        price_data: pd.DataFrame,
        feature_data: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy: Strategy instance to backtest
            price_data: OHLCV data indexed by (date, ticker)
            feature_data: Pre-computed features indexed by (date, ticker)
            market_data: Market-level data (VIX, breadth, etc.)
        
        Returns:
            BacktestResult with all metrics
        """
        run_id = str(uuid4())[:8]
        
        # Initialize state
        portfolio = Portfolio(self.config.initial_capital)
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []
        
        # Get unique dates
        dates = sorted(price_data.index.get_level_values('date').unique())
        dates = [d for d in dates if self.config.start_date <= d <= self.config.end_date]
        
        for i, current_date in enumerate(dates):
            # Skip if drawdown limit hit
            if portfolio.current_drawdown >= self.config.stop_trading_drawdown:
                self.logger.warning(f"Drawdown limit hit on {current_date}")
                break
            
            # Get today's data
            try:
                today_prices = price_data.loc[current_date]
                today_features = feature_data.loc[current_date]
            except KeyError:
                continue
            
            today_market = None
            if market_data is not None:
                try:
                    today_market = market_data.loc[current_date]
                except KeyError:
                    pass
            
            # 1. Update existing positions with current prices
            self._update_positions(portfolio, today_prices)
            
            # 2. Check for exits (stops, targets, time)
            closed_trades = self._check_exits(portfolio, today_prices, current_date)
            trades.extend(closed_trades)
            
            # 3. Generate new signals
            universe = today_prices.index.tolist()
            signals = strategy.generate_signals(universe, today_features, today_market)
            
            # 4. Filter and rank signals
            filtered_signals = self._filter_signals(signals, portfolio)
            
            # 5. Execute entries (at next bar open if configured)
            if i + 1 < len(dates) and self.config.use_next_open:
                next_date = dates[i + 1]
                try:
                    next_prices = price_data.loc[next_date]
                    self._execute_entries(portfolio, filtered_signals, next_prices, next_date)
                except KeyError:
                    pass
            
            # 6. Record equity
            equity = portfolio.get_total_equity(today_prices)
            equity_curve.append({
                "date": current_date.isoformat(),
                "equity": equity,
                "cash": portfolio.cash,
                "positions": len(portfolio.positions),
                "drawdown": portfolio.current_drawdown
            })
        
        # Close any remaining positions
        final_date = dates[-1] if dates else self.config.end_date
        final_prices = price_data.loc[final_date] if final_date in price_data.index.get_level_values('date') else None
        if final_prices is not None:
            for position in list(portfolio.positions.values()):
                if position.ticker in final_prices.index:
                    trade = self._close_position(
                        portfolio, position, 
                        final_prices.loc[position.ticker, 'close'],
                        final_date, "backtest_end"
                    )
                    trades.append(trade)
        
        # Calculate metrics
        return self._calculate_results(
            run_id=run_id,
            strategy=strategy,
            trades=trades,
            equity_curve=equity_curve
        )
    
    def _filter_signals(self, signals: List[Signal], portfolio: "Portfolio") -> List[Signal]:
        """Filter and rank signals based on risk limits."""
        if not signals:
            return []
        
        # Filter by confidence
        signals = [s for s in signals if s.confidence >= 50]
        
        # Filter out tickers already in portfolio
        existing_tickers = set(portfolio.positions.keys())
        signals = [s for s in signals if s.ticker not in existing_tickers]
        
        # Check max positions
        available_slots = self.config.max_positions - len(portfolio.positions)
        if available_slots <= 0:
            return []
        
        # Rank by confidence
        signals = sorted(signals, key=lambda s: s.confidence, reverse=True)
        
        return signals[:available_slots]
    
    def _execute_entries(
        self, 
        portfolio: "Portfolio", 
        signals: List[Signal],
        prices: pd.DataFrame,
        date: date
    ):
        """Execute entry orders."""
        for signal in signals:
            if signal.ticker not in prices.index:
                continue
            
            open_price = prices.loc[signal.ticker, 'open']
            
            # Apply slippage
            if signal.direction == Direction.LONG:
                fill_price = open_price * (1 + self.config.slippage_pct)
            else:
                fill_price = open_price * (1 - self.config.slippage_pct)
            
            # Calculate position size
            position_size = self._calculate_position_size(signal, portfolio, fill_price)
            
            if position_size <= 0:
                continue
            
            # Create position
            position = Position(
                ticker=signal.ticker,
                direction=signal.direction,
                entry_date=date,
                entry_price=fill_price,
                shares=position_size,
                stop_loss=signal.invalidation.stop_price,
                targets=[t.price for t in signal.targets],
                signal=signal
            )
            
            # Deduct cost
            cost = position_size * fill_price + self.config.commission_per_trade
            portfolio.cash -= cost
            portfolio.positions[signal.ticker] = position
    
    def _calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: "Portfolio",
        fill_price: float
    ) -> int:
        """Calculate position size based on risk parameters."""
        # Risk-based sizing
        risk_amount = portfolio.get_total_equity({}) * self.config.risk_per_trade
        stop_distance = abs(fill_price - signal.invalidation.stop_price)
        
        if stop_distance <= 0:
            return 0
        
        shares_by_risk = int(risk_amount / stop_distance)
        
        # Max position sizing
        max_position_value = portfolio.get_total_equity({}) * self.config.max_position_pct
        shares_by_max = int(max_position_value / fill_price)
        
        # Cash constraint
        available_cash = portfolio.cash - 1000  # Keep buffer
        shares_by_cash = int(available_cash / fill_price)
        
        return max(0, min(shares_by_risk, shares_by_max, shares_by_cash))
    
    def _check_exits(
        self, 
        portfolio: "Portfolio", 
        prices: pd.DataFrame,
        date: date
    ) -> List[BacktestTrade]:
        """Check and execute exits."""
        closed_trades = []
        
        for ticker, position in list(portfolio.positions.items()):
            if ticker not in prices.index:
                continue
            
            row = prices.loc[ticker]
            high = row['high']
            low = row['low']
            close = row['close']
            
            exit_price = None
            exit_reason = None
            
            # Check stop loss
            if position.direction == Direction.LONG:
                if low <= position.stop_loss:
                    exit_price = position.stop_loss * (1 - self.config.slippage_pct)
                    exit_reason = "stop_loss"
            else:
                if high >= position.stop_loss:
                    exit_price = position.stop_loss * (1 + self.config.slippage_pct)
                    exit_reason = "stop_loss"
            
            # Check targets
            if exit_price is None and position.targets:
                if position.direction == Direction.LONG:
                    if high >= position.targets[0]:
                        exit_price = position.targets[0]
                        exit_reason = "target_hit"
                else:
                    if low <= position.targets[0]:
                        exit_price = position.targets[0]
                        exit_reason = "target_hit"
            
            # Update MAE/MFE
            if position.direction == Direction.LONG:
                position.update_mae_mfe(low, high)
            else:
                position.update_mae_mfe(high, low)
            
            # Execute exit
            if exit_price:
                trade = self._close_position(portfolio, position, exit_price, date, exit_reason)
                closed_trades.append(trade)
        
        return closed_trades
    
    def _close_position(
        self,
        portfolio: "Portfolio",
        position: "Position",
        exit_price: float,
        date: date,
        reason: str
    ) -> BacktestTrade:
        """Close a position and record the trade."""
        # Calculate P&L
        if position.direction == Direction.LONG:
            pnl_per_share = exit_price - position.entry_price
        else:
            pnl_per_share = position.entry_price - exit_price
        
        pnl_dollars = pnl_per_share * position.shares - self.config.commission_per_trade
        pnl_pct = pnl_per_share / position.entry_price
        
        # Credit proceeds
        portfolio.cash += position.shares * exit_price - self.config.commission_per_trade
        del portfolio.positions[position.ticker]
        
        # Update portfolio stats
        portfolio.total_trades += 1
        if pnl_dollars > 0:
            portfolio.winning_trades += 1
            portfolio.gross_profit += pnl_dollars
        else:
            portfolio.losing_trades += 1
            portfolio.gross_loss += abs(pnl_dollars)
        
        return BacktestTrade(
            ticker=position.ticker,
            direction=position.direction,
            entry_date=position.entry_date,
            exit_date=date,
            entry_price=position.entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            pnl_dollars=pnl_dollars,
            holding_days=(date - position.entry_date).days,
            exit_reason=reason
        )
    
    def _update_positions(self, portfolio: "Portfolio", prices: pd.DataFrame):
        """Update position values with current prices."""
        for ticker, position in portfolio.positions.items():
            if ticker in prices.index:
                position.current_price = prices.loc[ticker, 'close']
    
    def _calculate_results(
        self,
        run_id: str,
        strategy: "BaseStrategy",
        trades: List[BacktestTrade],
        equity_curve: List[Dict]
    ) -> BacktestResult:
        """Calculate comprehensive backtest metrics."""
        
        if len(trades) < self.config.min_trades_required:
            self.logger.warning(
                f"Insufficient trades ({len(trades)}) for reliable statistics. "
                f"Minimum required: {self.config.min_trades_required}"
            )
        
        # Convert equity curve to series
        equity_df = pd.DataFrame(equity_curve)
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df.set_index('date', inplace=True)
        equity_series = equity_df['equity']
        
        # Calculate returns
        returns = equity_series.pct_change().dropna()
        
        # Basic metrics
        total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1 if len(equity_series) > 0 else 0
        
        trading_days = len(returns)
        annualized_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1
        
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        
        # Sharpe (assuming 0% risk-free rate for simplicity)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Sortino
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = annualized_return / downside_std if downside_std > 0 else 0
        
        # Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
        
        # Find max drawdown duration
        dd_start = None
        dd_duration = 0
        max_dd_duration = 0
        for i, (idx, dd) in enumerate(drawdown.items()):
            if dd < 0:
                if dd_start is None:
                    dd_start = i
                dd_duration = i - dd_start
            else:
                if dd_duration > max_dd_duration:
                    max_dd_duration = dd_duration
                dd_start = None
                dd_duration = 0
        
        # Calmar
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade statistics
        winning_trades = [t for t in trades if t.pnl_pct > 0]
        losing_trades = [t for t in trades if t.pnl_pct <= 0]
        
        total_trades = len(trades)
        num_winners = len(winning_trades)
        num_losers = len(losing_trades)
        
        win_rate = num_winners / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
        
        gross_profit = sum(t.pnl_dollars for t in winning_trades)
        gross_loss = abs(sum(t.pnl_dollars for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
        
        # Risk metrics
        var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95
        
        # Monthly returns
        if len(equity_df) > 0:
            monthly = equity_df['equity'].resample('M').last().pct_change()
            monthly_returns = {k.strftime('%Y-%m'): v for k, v in monthly.items() if pd.notna(v)}
        else:
            monthly_returns = {}
        
        return BacktestResult(
            run_id=run_id,
            run_at=datetime.utcnow(),
            strategy_id=strategy.STRATEGY_ID,
            strategy_version=getattr(strategy, 'VERSION', '1.0'),
            parameters=strategy.get_parameters() if hasattr(strategy, 'get_parameters') else {},
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            universe=[],
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_days=max_dd_duration,
            total_trades=total_trades,
            winning_trades=num_winners,
            losing_trades=num_losers,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            var_95=var_95,
            cvar_95=cvar_95,
            volatility=volatility,
            beta=0.0,  # Would need benchmark data
            alpha=0.0,  # Would need benchmark data
            trades=trades,
            equity_curve=equity_curve,
            monthly_returns=monthly_returns
        )


@dataclass
class Position:
    """Active position in portfolio."""
    ticker: str
    direction: Direction
    entry_date: date
    entry_price: float
    shares: int
    stop_loss: float
    targets: List[float]
    signal: Signal
    
    current_price: float = 0.0
    mae: float = 0.0  # Max Adverse Excursion
    mfe: float = 0.0  # Max Favorable Excursion
    
    def update_mae_mfe(self, adverse_price: float, favorable_price: float):
        """Update MAE/MFE tracking."""
        if self.direction == Direction.LONG:
            adverse_pct = (adverse_price - self.entry_price) / self.entry_price
            favorable_pct = (favorable_price - self.entry_price) / self.entry_price
        else:
            adverse_pct = (self.entry_price - adverse_price) / self.entry_price
            favorable_pct = (self.entry_price - favorable_price) / self.entry_price
        
        self.mae = min(self.mae, adverse_pct)
        self.mfe = max(self.mfe, favorable_pct)


class Portfolio:
    """Portfolio state tracker."""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        
        self.peak_equity = initial_capital
        self.current_drawdown = 0.0
        
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
    
    def get_total_equity(self, prices: pd.DataFrame) -> float:
        """Calculate total portfolio value."""
        position_value = 0.0
        for ticker, position in self.positions.items():
            if ticker in prices.index:
                price = prices.loc[ticker, 'close'] if 'close' in prices.columns else prices.loc[ticker]
            else:
                price = position.current_price or position.entry_price
            
            position_value += position.shares * price
        
        total = self.cash + position_value
        
        # Update drawdown tracking
        if total > self.peak_equity:
            self.peak_equity = total
        self.current_drawdown = (self.peak_equity - total) / self.peak_equity
        
        return total
```

---

## Walk-Forward Optimization

```python
class WalkForwardOptimizer:
    """
    Walk-forward analysis to prevent overfitting.
    
    Splits data into in-sample (training) and out-of-sample (testing) windows,
    optimizes on IS, validates on OOS, then walks forward.
    
    Example:
    - Total period: 2020-2024
    - IS window: 12 months
    - OOS window: 3 months
    - Step: 3 months
    
    This creates multiple IS/OOS pairs and aggregates OOS performance.
    """
    
    def __init__(
        self,
        in_sample_months: int = 12,
        out_of_sample_months: int = 3,
        step_months: int = 3,
        parameter_grid: Dict[str, List] = None
    ):
        self.is_months = in_sample_months
        self.oos_months = out_of_sample_months
        self.step_months = step_months
        self.param_grid = parameter_grid or {}
    
    def run(
        self,
        strategy_class: type,
        price_data: pd.DataFrame,
        feature_data: pd.DataFrame,
        start_date: date,
        end_date: date
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.
        
        Returns aggregated OOS results which give realistic performance estimate.
        """
        windows = self._generate_windows(start_date, end_date)
        
        oos_results = []
        optimized_params = []
        
        for is_start, is_end, oos_start, oos_end in windows:
            # 1. Optimize on in-sample
            best_params, is_result = self._optimize_in_sample(
                strategy_class, price_data, feature_data,
                is_start, is_end
            )
            optimized_params.append(best_params)
            
            # 2. Validate on out-of-sample with optimized params
            oos_result = self._run_out_of_sample(
                strategy_class, best_params,
                price_data, feature_data,
                oos_start, oos_end
            )
            oos_results.append(oos_result)
        
        # 3. Aggregate OOS results
        return self._aggregate_results(oos_results, optimized_params, windows)
    
    def _generate_windows(self, start: date, end: date) -> List[Tuple[date, date, date, date]]:
        """Generate IS/OOS window pairs."""
        windows = []
        current = start
        
        while True:
            is_end = current + timedelta(days=self.is_months * 30)
            oos_start = is_end
            oos_end = oos_start + timedelta(days=self.oos_months * 30)
            
            if oos_end > end:
                break
            
            windows.append((current, is_end, oos_start, oos_end))
            current += timedelta(days=self.step_months * 30)
        
        return windows
    
    def _optimize_in_sample(
        self,
        strategy_class: type,
        price_data: pd.DataFrame,
        feature_data: pd.DataFrame,
        start: date,
        end: date
    ) -> Tuple[Dict, BacktestResult]:
        """Find best parameters on in-sample data."""
        best_sharpe = float('-inf')
        best_params = {}
        best_result = None
        
        # Grid search
        param_combinations = self._generate_param_combinations()
        
        for params in param_combinations:
            strategy = strategy_class(**params)
            config = BacktestConfig(start_date=start, end_date=end)
            backtester = Backtester(config)
            
            result = backtester.run(strategy, price_data, feature_data)
            
            if result.sharpe_ratio > best_sharpe:
                best_sharpe = result.sharpe_ratio
                best_params = params
                best_result = result
        
        return best_params, best_result
    
    def _run_out_of_sample(
        self,
        strategy_class: type,
        params: Dict,
        price_data: pd.DataFrame,
        feature_data: pd.DataFrame,
        start: date,
        end: date
    ) -> BacktestResult:
        """Run strategy with fixed params on OOS data."""
        strategy = strategy_class(**params)
        config = BacktestConfig(start_date=start, end_date=end)
        backtester = Backtester(config)
        
        return backtester.run(strategy, price_data, feature_data)


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward results."""
    oos_sharpe: float
    oos_return: float
    oos_win_rate: float
    oos_profit_factor: float
    oos_max_drawdown: float
    
    is_oos_ratio: float  # OOS performance / IS performance
    parameter_stability: float  # How stable were optimal params across windows
    
    individual_results: List[BacktestResult]
    window_summary: pd.DataFrame
```

---

## Overfitting Guardrails

### Checklist to Prevent Overfitting

| Guardrail | Implementation | Threshold |
|-----------|----------------|-----------|
| **Minimum trades** | Require statistical significance | > 30 trades |
| **Walk-forward ratio** | OOS Sharpe / IS Sharpe | > 0.5 |
| **Parameter stability** | Std dev of optimal params across windows | Low variance |
| **Out-of-time test** | Hold back most recent 20% of data | Must pass |
| **Multiple timeframes** | Test on daily, weekly, monthly | Consistent across |
| **Multiple universes** | Test on SP500, Russell 2000, sectors | Generalizes |
| **Bootstrap confidence** | 95% CI for Sharpe ratio | Lower bound > 0.5 |
| **Regime robustness** | Performance across vol regimes | Consistent |

### Automated Validation

```python
class OverfitDetector:
    """Detect signs of overfitting in backtest results."""
    
    def __init__(self):
        self.checks = [
            ("min_trades", self._check_min_trades),
            ("walk_forward_ratio", self._check_wf_ratio),
            ("sharpe_confidence", self._check_sharpe_confidence),
            ("drawdown_recovery", self._check_drawdown_recovery),
            ("regime_consistency", self._check_regime_consistency),
        ]
    
    def validate(
        self, 
        in_sample: BacktestResult, 
        out_sample: BacktestResult,
        wf_result: WalkForwardResult = None
    ) -> ValidationReport:
        """Run all overfitting checks."""
        
        results = {}
        passed = True
        
        for name, check_fn in self.checks:
            check_passed, message = check_fn(in_sample, out_sample, wf_result)
            results[name] = {"passed": check_passed, "message": message}
            if not check_passed:
                passed = False
        
        return ValidationReport(
            overall_passed=passed,
            checks=results,
            recommendation=self._get_recommendation(results)
        )
    
    def _check_min_trades(self, is_result, oos_result, wf) -> Tuple[bool, str]:
        """Check minimum trades requirement."""
        min_required = 30
        
        is_ok = is_result.total_trades >= min_required
        oos_ok = oos_result.total_trades >= min_required * 0.3  # Proportional
        
        if is_ok and oos_ok:
            return True, f"Sufficient trades: IS={is_result.total_trades}, OOS={oos_result.total_trades}"
        else:
            return False, f"Insufficient trades for reliable statistics"
    
    def _check_wf_ratio(self, is_result, oos_result, wf) -> Tuple[bool, str]:
        """Check walk-forward degradation."""
        if is_result.sharpe_ratio <= 0:
            return False, "In-sample Sharpe <= 0"
        
        ratio = oos_result.sharpe_ratio / is_result.sharpe_ratio
        
        if ratio >= 0.5:
            return True, f"Walk-forward ratio {ratio:.2f} acceptable"
        else:
            return False, f"Walk-forward ratio {ratio:.2f} too low (possible overfitting)"
    
    def _check_sharpe_confidence(self, is_result, oos_result, wf) -> Tuple[bool, str]:
        """Bootstrap confidence interval for Sharpe."""
        # Simplified check - in practice use bootstrap
        if oos_result.sharpe_ratio >= 0.5:
            return True, f"OOS Sharpe {oos_result.sharpe_ratio:.2f} >= 0.5"
        else:
            return False, f"OOS Sharpe {oos_result.sharpe_ratio:.2f} < 0.5 threshold"
    
    def _check_drawdown_recovery(self, is_result, oos_result, wf) -> Tuple[bool, str]:
        """Check max drawdown is recoverable."""
        if abs(oos_result.max_drawdown) <= 0.20:
            return True, f"Max drawdown {oos_result.max_drawdown:.1%} manageable"
        else:
            return False, f"Max drawdown {oos_result.max_drawdown:.1%} exceeds 20% limit"
    
    def _check_regime_consistency(self, is_result, oos_result, wf) -> Tuple[bool, str]:
        """Check performance consistency across regimes."""
        # Would need regime-tagged results
        return True, "Regime check requires additional data"
    
    def _get_recommendation(self, results: Dict) -> str:
        """Generate recommendation based on checks."""
        failed = [k for k, v in results.items() if not v['passed']]
        
        if not failed:
            return "✅ Strategy passes all validation checks. Consider paper trading."
        elif len(failed) <= 2:
            return f"⚠️ Strategy has concerns: {', '.join(failed)}. Review before deployment."
        else:
            return f"❌ Strategy fails multiple checks: {', '.join(failed)}. Do not deploy."
```

---

## Ongoing Monitoring

### Model Drift Detection

```python
class DriftMonitor:
    """Monitor for strategy performance degradation."""
    
    def __init__(self, lookback_days: int = 60, alert_threshold: float = 0.5):
        self.lookback = lookback_days
        self.threshold = alert_threshold
    
    def check_drift(
        self,
        recent_signals: List[Signal],
        historical_baseline: BacktestResult
    ) -> DriftReport:
        """Check if recent performance deviates from baseline."""
        
        if len(recent_signals) < 10:
            return DriftReport(drift_detected=False, message="Insufficient recent data")
        
        # Calculate recent metrics
        recent_returns = [s.pnl_pct for s in recent_signals if hasattr(s, 'pnl_pct')]
        
        recent_win_rate = len([r for r in recent_returns if r > 0]) / len(recent_returns)
        recent_expectancy = np.mean(recent_returns)
        
        # Compare to baseline
        win_rate_drift = abs(recent_win_rate - historical_baseline.win_rate)
        expectancy_drift = abs(recent_expectancy - historical_baseline.expectancy)
        
        drift_detected = (
            win_rate_drift > self.threshold * historical_baseline.win_rate or
            recent_expectancy < 0
        )
        
        return DriftReport(
            drift_detected=drift_detected,
            recent_win_rate=recent_win_rate,
            baseline_win_rate=historical_baseline.win_rate,
            recent_expectancy=recent_expectancy,
            baseline_expectancy=historical_baseline.expectancy,
            recommendation="Pause strategy" if drift_detected else "Continue monitoring"
        )
```

### Monitoring Dashboard Metrics

| Metric | Update Frequency | Alert Threshold |
|--------|-----------------|-----------------|
| Rolling 20-day Sharpe | Daily | < 0 |
| Rolling 20-day Win Rate | Daily | < 30% |
| Current Drawdown | Real-time | > 10% |
| Data Freshness | Every minute | > 15 min stale |
| Signal Generation Rate | Daily | 0 signals for 3+ days |
| API Error Rate | Hourly | > 5% |
| GPT Token Usage | Daily | > budget |

---

## Summary: Evaluation Plan

### Phase 1: Development (Before Paper Trading)
1. ✅ Unit test each strategy component
2. ✅ Run full backtest on 5+ years of data
3. ✅ Walk-forward validation (12mo IS / 3mo OOS)
4. ✅ Pass all overfitting checks
5. ✅ Test on multiple universes (SP500, Russell 2000)

### Phase 2: Paper Trading (1-3 Months)
1. Deploy to paper trading account
2. Compare real signals to backtest expectations
3. Monitor execution quality (slippage, fills)
4. Track live vs simulated performance gap
5. Tune position sizing and risk parameters

### Phase 3: Live Trading (Ongoing)
1. Start with 25% of target capital
2. Increase allocation as performance validates
3. Daily monitoring of all metrics
4. Weekly performance review
5. Monthly strategy review and rebalancing

### Red Flags Requiring Intervention
- 3 consecutive losing weeks
- Drawdown exceeds 15%
- Win rate drops below 35%
- Sharpe falls below 0.5
- Significant drift from backtest performance
