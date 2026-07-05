"""
Performance Analytics - Advanced analytics for trading performance.

Provides:
- Risk-adjusted returns (Sharpe, Sortino)
- Drawdown analysis
- Strategy correlation
- Performance attribution
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    """Comprehensive strategy metrics."""
    strategy_name: str
    
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    avg_trade_return: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    
    # Timing
    avg_hold_time_hours: float = 0.0
    best_day: str = ""
    worst_day: str = ""
    
    # Risk management
    avg_risk_per_trade: float = 0.0
    max_consecutive_losses: int = 0


@dataclass
class DrawdownPeriod:
    """Drawdown period details."""
    start_date: datetime
    end_date: Optional[datetime]
    trough_date: datetime
    peak_value: float
    trough_value: float
    drawdown_pct: float
    recovery_days: Optional[int] = None
    is_recovered: bool = False


@dataclass
class CorrelationMatrix:
    """Strategy correlation matrix."""
    strategies: List[str]
    correlations: Dict[Tuple[str, str], float] = field(default_factory=dict)


class PerformanceAnalytics:
    """
    Advanced performance analytics.
    
    Features:
    - Risk-adjusted return calculations
    - Drawdown analysis
    - Strategy comparison
    - Performance attribution
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
    
    def calculate_strategy_metrics(
        self,
        returns: List[float],
        strategy_name: str,
        trades_per_year: int = 252
    ) -> StrategyMetrics:
        """
        Calculate comprehensive strategy metrics.
        
        Args:
            returns: List of trade returns (as percentages)
            strategy_name: Name of the strategy
            trades_per_year: Expected trades per year for annualization
            
        Returns:
            StrategyMetrics object
        """
        metrics = StrategyMetrics(strategy_name=strategy_name)
        
        if not returns:
            return metrics
        
        metrics.total_trades = len(returns)
        
        # Basic returns
        metrics.total_return = sum(returns)
        metrics.avg_trade_return = metrics.total_return / len(returns)
        
        # Win rate
        winners = [r for r in returns if r > 0]
        losers = [r for r in returns if r < 0]
        
        metrics.win_rate = len(winners) / len(returns) * 100 if returns else 0
        
        if winners:
            metrics.avg_winner = sum(winners) / len(winners)
        if losers:
            metrics.avg_loser = sum(losers) / len(losers)
        
        # Profit factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 0
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Volatility
        if len(returns) > 1:
            mean = metrics.avg_trade_return
            variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            metrics.volatility = math.sqrt(variance)
        
        # Annualized return (assuming trades_per_year trades)
        if metrics.avg_trade_return != 0:
            metrics.annualized_return = metrics.avg_trade_return * trades_per_year
        
        # Sharpe ratio
        if metrics.volatility > 0:
            excess_return = metrics.annualized_return - self.risk_free_rate
            annualized_vol = metrics.volatility * math.sqrt(trades_per_year)
            metrics.sharpe_ratio = excess_return / annualized_vol
        
        # Sortino ratio (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_deviation = math.sqrt(downside_variance)
            if downside_deviation > 0:
                annualized_downside = downside_deviation * math.sqrt(trades_per_year)
                excess_return = metrics.annualized_return - self.risk_free_rate
                metrics.sortino_ratio = excess_return / annualized_downside
        
        # Max drawdown
        metrics.max_drawdown = self._calculate_max_drawdown(returns)
        
        # Calmar ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / abs(metrics.max_drawdown)
        
        # Max consecutive losses
        metrics.max_consecutive_losses = self._max_consecutive_losses(returns)
        
        return metrics
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns series."""
        if not returns:
            return 0.0
        
        # Convert to cumulative equity curve
        equity = [100.0]  # Start with 100
        for r in returns:
            equity.append(equity[-1] * (1 + r / 100))
        
        # Calculate running max and drawdown
        running_max = equity[0]
        max_dd = 0
        
        for value in equity:
            running_max = max(running_max, value)
            dd = (running_max - value) / running_max * 100
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _max_consecutive_losses(self, returns: List[float]) -> int:
        """Calculate max consecutive losing trades."""
        max_streak = 0
        current_streak = 0
        
        for r in returns:
            if r < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def analyze_drawdowns(
        self,
        equity_curve: List[Tuple[datetime, float]]
    ) -> List[DrawdownPeriod]:
        """
        Analyze drawdown periods from equity curve.
        
        Args:
            equity_curve: List of (datetime, equity_value) tuples
            
        Returns:
            List of DrawdownPeriod objects
        """
        if not equity_curve:
            return []
        
        drawdowns = []
        peak = equity_curve[0][1]
        peak_date = equity_curve[0][0]
        in_drawdown = False
        current_dd = None
        
        for date, value in equity_curve:
            if value >= peak:
                # New peak
                if in_drawdown and current_dd:
                    # Recovery from drawdown
                    current_dd.end_date = date
                    current_dd.is_recovered = True
                    current_dd.recovery_days = (date - current_dd.trough_date).days
                    drawdowns.append(current_dd)
                    current_dd = None
                    in_drawdown = False
                
                peak = value
                peak_date = date
            else:
                # In drawdown
                dd_pct = (peak - value) / peak * 100
                
                if not in_drawdown:
                    # Start of new drawdown
                    in_drawdown = True
                    current_dd = DrawdownPeriod(
                        start_date=peak_date,
                        end_date=None,
                        trough_date=date,
                        peak_value=peak,
                        trough_value=value,
                        drawdown_pct=dd_pct
                    )
                else:
                    # Update if deeper drawdown
                    if dd_pct > current_dd.drawdown_pct:
                        current_dd.trough_date = date
                        current_dd.trough_value = value
                        current_dd.drawdown_pct = dd_pct
        
        # Add final drawdown if still in one
        if current_dd:
            drawdowns.append(current_dd)
        
        return sorted(drawdowns, key=lambda d: d.drawdown_pct, reverse=True)
    
    def compare_strategies(
        self,
        strategy_metrics: List[StrategyMetrics]
    ) -> Dict[str, Dict]:
        """
        Compare multiple strategies.
        
        Args:
            strategy_metrics: List of StrategyMetrics objects
            
        Returns:
            Comparison dict with rankings
        """
        if not strategy_metrics:
            return {}
        
        comparison = {
            "by_return": [],
            "by_sharpe": [],
            "by_win_rate": [],
            "by_drawdown": [],
            "overall_ranking": {}
        }
        
        # Rank by different metrics
        by_return = sorted(strategy_metrics, key=lambda m: m.total_return, reverse=True)
        by_sharpe = sorted(strategy_metrics, key=lambda m: m.sharpe_ratio, reverse=True)
        by_win_rate = sorted(strategy_metrics, key=lambda m: m.win_rate, reverse=True)
        by_dd = sorted(strategy_metrics, key=lambda m: m.max_drawdown)
        
        comparison["by_return"] = [m.strategy_name for m in by_return]
        comparison["by_sharpe"] = [m.strategy_name for m in by_sharpe]
        comparison["by_win_rate"] = [m.strategy_name for m in by_win_rate]
        comparison["by_drawdown"] = [m.strategy_name for m in by_dd]
        
        # Calculate overall ranking (weighted)
        scores = {}
        for i, m in enumerate(by_return):
            scores[m.strategy_name] = scores.get(m.strategy_name, 0) + (len(strategy_metrics) - i) * 2  # Weight: 2
        for i, m in enumerate(by_sharpe):
            scores[m.strategy_name] = scores.get(m.strategy_name, 0) + (len(strategy_metrics) - i) * 3  # Weight: 3
        for i, m in enumerate(by_dd):
            scores[m.strategy_name] = scores.get(m.strategy_name, 0) + (len(strategy_metrics) - i) * 1  # Weight: 1
        
        comparison["overall_ranking"] = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
        
        return comparison
    
    def calculate_rolling_metrics(
        self,
        returns: List[float],
        window: int = 20
    ) -> Dict[str, List[float]]:
        """
        Calculate rolling performance metrics.
        
        Args:
            returns: List of trade returns
            window: Rolling window size
            
        Returns:
            Dict with rolling metrics
        """
        if len(returns) < window:
            return {}
        
        rolling = {
            "dates": list(range(window, len(returns) + 1)),
            "cumulative_return": [],
            "rolling_sharpe": [],
            "rolling_win_rate": [],
            "rolling_volatility": []
        }
        
        cum_return = 0
        for i in range(window, len(returns) + 1):
            window_returns = returns[i - window:i]
            cum_return += returns[i - 1]
            
            # Cumulative
            rolling["cumulative_return"].append(cum_return)
            
            # Win rate
            winners = len([r for r in window_returns if r > 0])
            rolling["rolling_win_rate"].append(winners / window * 100)
            
            # Volatility
            mean = sum(window_returns) / window
            variance = sum((r - mean) ** 2 for r in window_returns) / (window - 1)
            vol = math.sqrt(variance) if variance > 0 else 0
            rolling["rolling_volatility"].append(vol)
            
            # Sharpe
            if vol > 0:
                sharpe = mean / vol * math.sqrt(252)
                rolling["rolling_sharpe"].append(sharpe)
            else:
                rolling["rolling_sharpe"].append(0)
        
        return rolling
    
    def format_metrics_report(self, metrics: StrategyMetrics) -> str:
        """Format strategy metrics as readable report."""
        lines = []
        
        lines.append(f"📈 **{metrics.strategy_name}** Performance Report")
        lines.append("")
        
        # Returns
        lines.append("**Returns:**")
        lines.append(f"  Total Return: {'+' if metrics.total_return >= 0 else ''}{metrics.total_return:.2f}%")
        lines.append(f"  Annualized: {'+' if metrics.annualized_return >= 0 else ''}{metrics.annualized_return:.2f}%")
        lines.append(f"  Avg per Trade: {'+' if metrics.avg_trade_return >= 0 else ''}{metrics.avg_trade_return:.2f}%")
        lines.append("")
        
        # Risk metrics
        lines.append("**Risk Metrics:**")
        lines.append(f"  Volatility: {metrics.volatility:.2f}%")
        lines.append(f"  Max Drawdown: -{metrics.max_drawdown:.2f}%")
        lines.append(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        lines.append(f"  Sortino Ratio: {metrics.sortino_ratio:.2f}")
        lines.append(f"  Calmar Ratio: {metrics.calmar_ratio:.2f}")
        lines.append("")
        
        # Trade stats
        lines.append("**Trade Statistics:**")
        lines.append(f"  Total Trades: {metrics.total_trades}")
        lines.append(f"  Win Rate: {metrics.win_rate:.1f}%")
        lines.append(f"  Profit Factor: {metrics.profit_factor:.2f}")
        lines.append(f"  Avg Winner: +{metrics.avg_winner:.2f}%")
        lines.append(f"  Avg Loser: {metrics.avg_loser:.2f}%")
        lines.append(f"  Max Consecutive Losses: {metrics.max_consecutive_losses}")
        
        return "\n".join(lines)
