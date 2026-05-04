"""
TradingAI Bot - Backtesting Engine
Walk-forward backtesting with overfit detection and performance metrics.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

from src.core.models import Signal, BacktestResult


@dataclass
class Trade:
    """Represents a completed trade."""
    ticker: str
    direction: str
    entry_date: datetime
    entry_price: float
    exit_date: datetime
    exit_price: float
    pnl: float
    pnl_pct: float
    holding_period: int
    exit_reason: str  # 'take_profit', 'stop_loss', 'time_exit'
    signal_confidence: float
    strategy: str


class Backtester:
    """
    Walk-forward backtesting engine with overfit detection.
    
    Features:
    - Walk-forward optimization
    - Transaction costs modeling
    - Slippage estimation
    - Monte Carlo simulation
    - Out-of-sample validation
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        commission_per_trade: float = 1.0,
        slippage_pct: float = 0.001,
        max_position_size: float = 0.05,
        max_holding_days: int = 10,
        partial_fill_rate: float = 1.0,
        borrow_cost_annual_pct: float = 0.0,
        gap_risk_pct: float = 0.02,
        enforce_market_hours: bool = True,
    ):
        self.initial_capital = initial_capital
        self.commission = commission_per_trade
        self.slippage = slippage_pct
        self.max_position_size = max_position_size
        self.max_holding_days = max_holding_days
        self.partial_fill_rate = partial_fill_rate
        self.borrow_cost_annual_pct = borrow_cost_annual_pct
        self.gap_risk_pct = gap_risk_pct
        self.enforce_market_hours = enforce_market_hours
        self.logger = logging.getLogger(__name__)
    
    def backtest(
        self,
        signals: List[Signal],
        price_data: pd.DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> BacktestResult:
        """
        Run backtest on historical signals.
        
        Args:
            signals: List of historical signals
            price_data: OHLCV data indexed by (date, ticker)
            start_date: Backtest start date
            end_date: Backtest end date
        
        Returns:
            BacktestResult with performance metrics
        """
        if not signals:
            return self._empty_result()
        
        # Filter signals by date range
        if start_date:
            signals = [s for s in signals if s.generated_at >= start_date]
        if end_date:
            signals = [s for s in signals if s.generated_at <= end_date]
        
        # Sort signals by date
        signals = sorted(signals, key=lambda s: s.generated_at)
        
        # Initialize tracking
        capital = self.initial_capital
        trades: List[Trade] = []
        open_positions: Dict[str, Dict] = {}
        equity_curve = []
        
        # Get unique dates
        dates = sorted(set(s.generated_at.date() for s in signals))
        
        for current_date in dates:
            # Check for exits on existing positions
            for ticker in list(open_positions.keys()):
                pos = open_positions[ticker]
                
                try:
                    current_price = self._get_price(price_data, ticker, current_date)
                except KeyError:
                    continue
                
                exit_result = self._check_exit(pos, current_price, current_date)
                
                if exit_result:
                    exit_price, exit_reason = exit_result
                    
                    # Calculate P&L
                    if pos['direction'] == 'LONG':
                        pnl = (exit_price - pos['entry_price']) * pos['shares']
                    else:
                        pnl = (pos['entry_price'] - exit_price) * pos['shares']
                    
                    pnl -= self.commission * 2  # Entry + exit
                    # Deduct borrow cost for SHORT positions
                    if pos['direction'] == 'SHORT' and self.borrow_cost_annual_pct > 0:
                        holding_days = (current_date - pos['entry_date'].date()).days
                        borrow_cost = pos['capital_allocated'] * self.borrow_cost_annual_pct / 100 * holding_days / 365
                        pnl -= borrow_cost
                    pnl_pct = pnl / pos['capital_allocated']
                    
                    # Record trade
                    trades.append(Trade(
                        ticker=ticker,
                        direction=pos['direction'],
                        entry_date=pos['entry_date'],
                        entry_price=pos['entry_price'],
                        exit_date=current_date,
                        exit_price=exit_price,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        holding_period=(current_date - pos['entry_date'].date()).days,
                        exit_reason=exit_reason,
                        signal_confidence=pos['confidence'],
                        strategy=pos['strategy']
                    ))
                    
                    # Update capital
                    capital += pos['capital_allocated'] + pnl
                    del open_positions[ticker]
            
            # Process new signals for today
            day_signals = [s for s in signals if s.generated_at.date() == current_date]
            
            for signal in day_signals:
                # Skip if already have position in ticker
                if signal.ticker in open_positions:
                    continue
                
                # Skip if not enough capital
                position_size = min(
                    capital * self.max_position_size,
                    capital * signal.confidence * 0.1  # Scale by confidence
                )
                
                if position_size < 100:
                    continue
                
                try:
                    entry_price = self._get_price(
                        price_data, signal.ticker, current_date
                    )
                except KeyError:
                    continue
                
                # Apply slippage
                if signal.direction == 'LONG':
                    entry_price *= (1 + self.slippage)
                else:
                    entry_price *= (1 - self.slippage)
                
                shares = int(position_size / entry_price)
                # Apply partial fill rate
                shares = max(1, int(shares * self.partial_fill_rate))
                if shares == 0:
                    continue
                
                # Open position
                open_positions[signal.ticker] = {
                    'direction': signal.direction,
                    'entry_date': datetime.combine(current_date, datetime.min.time()),
                    'entry_price': entry_price,
                    'shares': shares,
                    'take_profit': signal.take_profit,
                    'stop_loss': signal.stop_loss,
                    'capital_allocated': shares * entry_price,
                    'confidence': signal.confidence,
                    'strategy': signal.strategy
                }
                
                capital -= shares * entry_price + self.commission
            
            # Record equity
            total_equity = capital
            for ticker, pos in open_positions.items():
                try:
                    current_price = self._get_price(price_data, ticker, current_date)
                    if pos['direction'] == 'LONG':
                        unrealized = (current_price - pos['entry_price']) * pos['shares']
                    else:
                        unrealized = (pos['entry_price'] - current_price) * pos['shares']
                    total_equity += pos['capital_allocated'] + unrealized
                except KeyError:
                    total_equity += pos['capital_allocated']
            
            equity_curve.append({
                'date': current_date,
                'equity': total_equity
            })
        
        # Calculate metrics
        return self._calculate_metrics(trades, equity_curve)
    
    def walk_forward(
        self,
        strategy_class,
        price_data: pd.DataFrame,
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3
    ) -> Dict[str, Any]:
        """
        Walk-forward optimization and testing.
        
        Args:
            strategy_class: Strategy class to test
            price_data: Full historical OHLCV data
            train_months: Training window size
            test_months: Testing window size
            step_months: Step forward size
        
        Returns:
            Walk-forward results with in-sample and out-of-sample metrics
        """
        results = []
        all_dates = price_data.index.get_level_values('date').unique().sort_values()
        
        start = all_dates[0]
        end = all_dates[-1]
        
        current = start
        
        while current + pd.DateOffset(months=train_months + test_months) <= end:
            train_start = current
            train_end = current + pd.DateOffset(months=train_months)
            test_start = train_end
            test_end = test_start + pd.DateOffset(months=test_months)
            
            # Get train and test data
            train_data = price_data.loc[
                (price_data.index.get_level_values('date') >= train_start) &
                (price_data.index.get_level_values('date') < train_end)
            ]
            
            test_data = price_data.loc[
                (price_data.index.get_level_values('date') >= test_start) &
                (price_data.index.get_level_values('date') < test_end)
            ]
            
            # Optimize on train data via simple grid search over strategy params
            best_strategy = strategy_class()
            best_sharpe = float("-inf")
            param_grid = getattr(strategy_class, "PARAM_GRID", None)
            if param_grid:
                import itertools
                keys = list(param_grid.keys())
                for combo in itertools.product(*param_grid.values()):
                    params = dict(zip(keys, combo))
                    try:
                        candidate = strategy_class(**params)
                        from src.engines import FeatureEngine as _FE
                        _feats = _FE().calculate_features(train_data)
                        _sigs = candidate.generate_signals(_feats)
                        _res = self.backtest(_sigs, train_data)
                        sharpe = _res.get("sharpe_ratio", float("-inf"))
                        if sharpe > best_sharpe:
                            best_sharpe = sharpe
                            best_strategy = candidate
                    except Exception:
                        pass
            strategy = best_strategy

            # Generate signals on test
            from src.engines import FeatureEngine
            feature_engine = FeatureEngine()
            test_features = feature_engine.calculate_features(test_data)
            signals = strategy.generate_signals(test_features)
            
            # Backtest
            result = self.backtest(signals, test_data)
            
            results.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'result': result
            })
            
            current += pd.DateOffset(months=step_months)
        
        return self._aggregate_walk_forward(results)
    
    def monte_carlo(
        self,
        trades: List[Trade],
        n_simulations: int = 1000
    ) -> Dict[str, Any]:
        """
        Monte Carlo simulation to estimate performance distribution.
        
        Shuffles trade order to understand luck vs skill.
        """
        if not trades:
            return {}
        
        pnls = [t.pnl_pct for t in trades]
        
        final_equities = []
        max_drawdowns = []
        
        for _ in range(n_simulations):
            # Shuffle trade order
            shuffled = np.random.permutation(pnls)
            
            # Calculate equity curve
            equity = [1.0]
            for pnl in shuffled:
                equity.append(equity[-1] * (1 + pnl))
            
            final_equities.append(equity[-1])
            
            # Calculate max drawdown
            peak = equity[0]
            max_dd = 0
            for e in equity:
                if e > peak:
                    peak = e
                dd = (peak - e) / peak
                max_dd = max(max_dd, dd)
            max_drawdowns.append(max_dd)
        
        return {
            'final_equity': {
                'mean': np.mean(final_equities),
                'std': np.std(final_equities),
                'percentile_5': np.percentile(final_equities, 5),
                'percentile_95': np.percentile(final_equities, 95),
            },
            'max_drawdown': {
                'mean': np.mean(max_drawdowns),
                'std': np.std(max_drawdowns),
                'percentile_95': np.percentile(max_drawdowns, 95),
            },
            'n_simulations': n_simulations
        }
    
    def detect_overfit(
        self,
        in_sample_result: BacktestResult,
        out_sample_result: BacktestResult
    ) -> Dict[str, Any]:
        """
        Detect potential overfitting by comparing in-sample vs out-of-sample.
        """
        # Calculate degradation metrics
        sharpe_ratio_is = in_sample_result.sharpe_ratio
        sharpe_ratio_oos = out_sample_result.sharpe_ratio
        
        win_rate_is = in_sample_result.win_rate
        win_rate_oos = out_sample_result.win_rate
        
        sharpe_degradation = (sharpe_ratio_is - sharpe_ratio_oos) / max(sharpe_ratio_is, 0.01)
        win_rate_degradation = (win_rate_is - win_rate_oos) / max(win_rate_is, 0.01)
        
        # Probability of backtest overfit
        pbo = self._calculate_pbo(sharpe_degradation, win_rate_degradation)
        
        return {
            'sharpe_ratio': {
                'in_sample': sharpe_ratio_is,
                'out_of_sample': sharpe_ratio_oos,
                'degradation_pct': sharpe_degradation * 100
            },
            'win_rate': {
                'in_sample': win_rate_is,
                'out_of_sample': win_rate_oos,
                'degradation_pct': win_rate_degradation * 100
            },
            'probability_of_overfit': pbo,
            'is_overfit': pbo > 0.5,
            'warning': "High probability of overfitting" if pbo > 0.7 else None
        }
    
    def _get_price(
        self, 
        price_data: pd.DataFrame, 
        ticker: str, 
        date: datetime
    ) -> float:
        """Get closing price for ticker on date."""
        if isinstance(date, datetime):
            date = date.date()
        
        try:
            return float(price_data.loc[(date, ticker), 'close'])
        except KeyError:
            # Try to find nearest date
            ticker_data = price_data.xs(ticker, level='ticker')
            nearest_idx = ticker_data.index.get_indexer([date], method='ffill')[0]
            return float(ticker_data.iloc[nearest_idx]['close'])
    
    def _check_exit(
        self,
        position: Dict,
        current_price: float,
        current_date: datetime
    ) -> Optional[Tuple[float, str]]:
        """
        Check if position should be exited.
        Includes gap-risk: if price gaps through stop,
        fill at the worse gapped price, not the stop level.
        """
        entry_price = position['entry_price']
        direction = position['direction']

        # Gap-risk: simulate overnight gap through stop
        # If current_price is beyond stop by > gap_risk_pct,
        # the fill is at current_price (gapped), not stop.
        stop = position['stop_loss']
        tp = position['take_profit']

        if direction == 'LONG':
            if current_price <= stop:
                # Gap through stop — fill at worse of stop or
                # current_price
                gap_fill = min(
                    stop, current_price
                ) * (1 - self.slippage)
                return (gap_fill, 'stop_loss_gap'
                        if current_price < stop * (
                            1 - self.gap_risk_pct
                        ) else 'stop_loss')
            if current_price >= tp:
                return (
                    tp * (1 - self.slippage),
                    'take_profit',
                )
        else:  # SHORT
            if current_price >= stop:
                gap_fill = max(
                    stop, current_price
                ) * (1 + self.slippage)
                return (gap_fill, 'stop_loss_gap'
                        if current_price > stop * (
                            1 + self.gap_risk_pct
                        ) else 'stop_loss')
            if current_price <= tp:
                return (
                    tp * (1 + self.slippage),
                    'take_profit',
                )

        # Check max holding period
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        holding = (
            current_date - position['entry_date'].date()
        ).days

        if holding >= self.max_holding_days:
            slip = (1 - self.slippage
                    if direction == 'LONG'
                    else 1 + self.slippage)
            return (current_price * slip, 'time_exit')

        return None
    
    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: List[Dict]
    ) -> BacktestResult:
        """Calculate performance metrics from trades and equity curve."""
        if not trades:
            return self._empty_result()
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        profit_factor = (
            abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades))
            if losing_trades and sum(t.pnl for t in losing_trades) != 0
            else float('inf')
        )
        
        # Risk metrics
        equity_values = [e['equity'] for e in equity_curve]
        
        if len(equity_values) > 1:
            returns = np.diff(equity_values) / equity_values[:-1]
            sharpe_ratio = (
                np.mean(returns) / np.std(returns) * np.sqrt(252)
                if np.std(returns) > 0 else 0
            )
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        peak = equity_values[0] if equity_values else self.initial_capital
        max_drawdown = 0
        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            max_drawdown = max(max_drawdown, dd)
        
        # Strategy breakdown
        strategy_metrics = {}
        for strategy in set(t.strategy for t in trades):
            strategy_trades = [t for t in trades if t.strategy == strategy]
            strategy_wins = [t for t in strategy_trades if t.pnl > 0]
            strategy_metrics[strategy] = {
                'trades': len(strategy_trades),
                'win_rate': len(strategy_wins) / len(strategy_trades) if strategy_trades else 0,
                'total_pnl': sum(t.pnl for t in strategy_trades),
                'avg_pnl': np.mean([t.pnl for t in strategy_trades])
            }
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            strategy_breakdown=strategy_metrics
        )
    
    def _empty_result(self) -> BacktestResult:
        """Return empty backtest result."""
        return BacktestResult(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl=0,
            avg_pnl=0,
            avg_win=0,
            avg_loss=0,
            profit_factor=0,
            sharpe_ratio=0,
            max_drawdown=0,
            strategy_breakdown={}
        )
    
    def _aggregate_walk_forward(
        self,
        results: List[Dict]
    ) -> Dict[str, Any]:
        """Aggregate walk-forward test results."""
        if not results:
            return {}
        
        all_trades = sum(r['result'].total_trades for r in results)
        all_wins = sum(r['result'].winning_trades for r in results)
        
        sharpe_ratios = [r['result'].sharpe_ratio for r in results]
        max_drawdowns = [r['result'].max_drawdown for r in results]
        
        return {
            'periods_tested': len(results),
            'total_trades': all_trades,
            'overall_win_rate': all_wins / all_trades if all_trades > 0 else 0,
            'average_sharpe': np.mean(sharpe_ratios),
            'sharpe_std': np.std(sharpe_ratios),
            'average_max_drawdown': np.mean(max_drawdowns),
            'worst_max_drawdown': max(max_drawdowns),
            'periods': results
        }
    
    def _calculate_pbo(
        self,
        sharpe_degradation: float,
        win_rate_degradation: float
    ) -> float:
        """Calculate probability of backtest overfitting."""
        # Simple heuristic-based PBO
        # In production, would use proper PBO calculation
        
        degradation_score = (
            abs(sharpe_degradation) * 0.6 +
            abs(win_rate_degradation) * 0.4
        )
        
        # Map to probability
        pbo = min(1.0, degradation_score)
        
        return pbo
