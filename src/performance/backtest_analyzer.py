"""
Backtest Analyzer - Analyze and report on backtest results.

Provides:
- Strategy validation
- Parameter optimization analysis
- Out-of-sample testing
- Monte Carlo simulation
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import random
import math

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Individual trade record from backtest."""
    entry_date: datetime
    exit_date: datetime
    ticker: str
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_absolute: float
    hold_days: int


@dataclass
class BacktestResult:
    """Complete backtest results."""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    # Performance
    total_return: float = 0.0
    annualized_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    
    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Trades
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade: float = 0.0
    
    # Trade records
    trades: List[TradeRecord] = field(default_factory=list)
    
    # Equity curve
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Monthly returns
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    
    # Parameter values (for optimization)
    parameters: Dict[str, any] = field(default_factory=dict)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results."""
    simulations: int
    original_return: float
    
    # Distribution statistics
    mean_return: float = 0.0
    median_return: float = 0.0
    std_dev: float = 0.0
    
    # Percentiles
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_75: float = 0.0
    percentile_95: float = 0.0
    
    # Risk metrics
    probability_of_loss: float = 0.0
    expected_max_drawdown: float = 0.0
    worst_case_return: float = 0.0
    best_case_return: float = 0.0
    
    # All simulated returns
    simulated_returns: List[float] = field(default_factory=list)


class BacktestAnalyzer:
    """
    Analyzes backtest results and provides insights.
    
    Features:
    - Result validation
    - Parameter sensitivity
    - Monte Carlo simulation
    - Walk-forward analysis
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
    
    def analyze_result(
        self,
        result: BacktestResult
    ) -> Dict[str, any]:
        """
        Comprehensive analysis of backtest result.
        
        Args:
            result: BacktestResult object
            
        Returns:
            Analysis dict with insights
        """
        analysis = {
            "summary": self._generate_summary(result),
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "quality_score": 0
        }
        
        # Analyze strengths
        if result.sharpe_ratio > 1.5:
            analysis["strengths"].append("Excellent risk-adjusted returns (Sharpe > 1.5)")
        elif result.sharpe_ratio > 1.0:
            analysis["strengths"].append("Good risk-adjusted returns (Sharpe > 1.0)")
        
        if result.win_rate > 55:
            analysis["strengths"].append(f"High win rate ({result.win_rate:.1f}%)")
        
        if result.profit_factor > 2:
            analysis["strengths"].append(f"Strong profit factor ({result.profit_factor:.2f})")
        
        if result.max_drawdown < 15:
            analysis["strengths"].append(f"Low max drawdown ({result.max_drawdown:.1f}%)")
        
        if result.alpha > 5:
            analysis["strengths"].append(f"Significant alpha over benchmark (+{result.alpha:.1f}%)")
        
        # Analyze weaknesses
        if result.sharpe_ratio < 0.5:
            analysis["weaknesses"].append("Poor risk-adjusted returns - consider adding filters")
        
        if result.max_drawdown > 30:
            analysis["weaknesses"].append("Large drawdowns - implement better risk management")
        
        if result.win_rate < 40:
            analysis["weaknesses"].append("Low win rate - review entry criteria")
        
        if result.profit_factor < 1.2:
            analysis["weaknesses"].append("Marginal edge - returns may not cover costs")
        
        if result.total_trades < 30:
            analysis["weaknesses"].append("Limited sample size - results may not be statistically significant")
        
        # Recommendations
        if result.max_drawdown > 20:
            analysis["recommendations"].append("Add position sizing based on volatility")
            analysis["recommendations"].append("Consider reducing position size during drawdowns")
        
        if result.win_rate < 45 and result.profit_factor > 1.5:
            analysis["recommendations"].append("Strategy relies on large winners - ensure you can hold through volatility")
        
        if result.total_trades > 500:
            analysis["recommendations"].append("High trade frequency - monitor slippage and commission impact")
        
        # Calculate quality score (0-100)
        score = 50
        score += min(20, result.sharpe_ratio * 10)
        score += min(10, (result.win_rate - 40) / 2) if result.win_rate > 40 else 0
        score -= min(20, result.max_drawdown / 2)
        score += min(10, (result.profit_factor - 1) * 5) if result.profit_factor > 1 else -10
        
        analysis["quality_score"] = max(0, min(100, score))
        
        return analysis
    
    def _generate_summary(self, result: BacktestResult) -> str:
        """Generate text summary of backtest."""
        years = (result.end_date - result.start_date).days / 365
        
        summary = f"""
Strategy: {result.strategy_name}
Period: {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')} ({years:.1f} years)
Capital: ${result.initial_capital:,.0f} → ${result.final_capital:,.0f} ({'+' if result.total_return > 0 else ''}{result.total_return:.1f}%)

Key Metrics:
- Annualized Return: {'+' if result.annualized_return > 0 else ''}{result.annualized_return:.1f}%
- Sharpe Ratio: {result.sharpe_ratio:.2f}
- Max Drawdown: -{result.max_drawdown:.1f}%
- Win Rate: {result.win_rate:.1f}%
- Profit Factor: {result.profit_factor:.2f}
- Total Trades: {result.total_trades}
""".strip()
        
        return summary
    
    def monte_carlo_simulation(
        self,
        trades: List[TradeRecord],
        simulations: int = 1000,
        initial_capital: float = 100000
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on trade sequence.
        
        Shuffles trade order to understand distribution of possible outcomes.
        
        Args:
            trades: List of historical trades
            simulations: Number of simulations to run
            initial_capital: Starting capital
            
        Returns:
            MonteCarloResult with distribution statistics
        """
        if not trades:
            return MonteCarloResult(simulations=0, original_return=0)
        
        # Calculate original return
        original_return = sum(t.pnl_pct for t in trades)
        
        result = MonteCarloResult(
            simulations=simulations,
            original_return=original_return
        )
        
        # Run simulations
        simulated_returns = []
        simulated_drawdowns = []
        
        for _ in range(simulations):
            # Shuffle trades
            shuffled = trades.copy()
            random.shuffle(shuffled)
            
            # Calculate equity curve
            equity = initial_capital
            peak = equity
            max_dd = 0
            
            for trade in shuffled:
                equity *= (1 + trade.pnl_pct / 100)
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100
                max_dd = max(max_dd, dd)
            
            total_return = (equity - initial_capital) / initial_capital * 100
            simulated_returns.append(total_return)
            simulated_drawdowns.append(max_dd)
        
        # Sort for percentile calculations
        sorted_returns = sorted(simulated_returns)
        
        # Statistics
        result.mean_return = sum(simulated_returns) / len(simulated_returns)
        result.median_return = sorted_returns[len(sorted_returns) // 2]
        
        mean = result.mean_return
        variance = sum((r - mean) ** 2 for r in simulated_returns) / len(simulated_returns)
        result.std_dev = math.sqrt(variance)
        
        # Percentiles
        n = len(sorted_returns)
        result.percentile_5 = sorted_returns[int(n * 0.05)]
        result.percentile_25 = sorted_returns[int(n * 0.25)]
        result.percentile_75 = sorted_returns[int(n * 0.75)]
        result.percentile_95 = sorted_returns[int(n * 0.95)]
        
        # Risk metrics
        result.probability_of_loss = len([r for r in simulated_returns if r < 0]) / n * 100
        result.expected_max_drawdown = sum(simulated_drawdowns) / len(simulated_drawdowns)
        result.worst_case_return = sorted_returns[0]
        result.best_case_return = sorted_returns[-1]
        
        result.simulated_returns = simulated_returns
        
        return result
    
    def walk_forward_analysis(
        self,
        trades: List[TradeRecord],
        in_sample_ratio: float = 0.7,
        num_folds: int = 5
    ) -> Dict[str, any]:
        """
        Perform walk-forward analysis.
        
        Tests strategy robustness by validating on out-of-sample periods.
        
        Args:
            trades: List of historical trades (sorted by date)
            in_sample_ratio: Ratio of in-sample to total window
            num_folds: Number of walk-forward periods
            
        Returns:
            Analysis results
        """
        if len(trades) < num_folds * 10:
            return {"error": "Insufficient trades for walk-forward analysis"}
        
        # Sort trades by date
        trades = sorted(trades, key=lambda t: t.entry_date)
        
        fold_size = len(trades) // num_folds
        in_sample_size = int(fold_size * in_sample_ratio)
        out_sample_size = fold_size - in_sample_size
        
        results = {
            "folds": [],
            "in_sample_returns": [],
            "out_sample_returns": [],
            "consistency": 0.0,
            "efficiency": 0.0
        }
        
        for i in range(num_folds):
            start_idx = i * fold_size
            mid_idx = start_idx + in_sample_size
            end_idx = start_idx + fold_size
            
            if end_idx > len(trades):
                break
            
            in_sample = trades[start_idx:mid_idx]
            out_sample = trades[mid_idx:end_idx]
            
            in_return = sum(t.pnl_pct for t in in_sample)
            out_return = sum(t.pnl_pct for t in out_sample)
            
            results["folds"].append({
                "period": i + 1,
                "in_sample_trades": len(in_sample),
                "out_sample_trades": len(out_sample),
                "in_sample_return": round(in_return, 2),
                "out_sample_return": round(out_return, 2),
                "degradation": round(((in_return - out_return) / abs(in_return) * 100) if in_return != 0 else 0, 1)
            })
            
            results["in_sample_returns"].append(in_return)
            results["out_sample_returns"].append(out_return)
        
        # Calculate consistency (% of OOS periods that are profitable)
        profitable_oos = len([r for r in results["out_sample_returns"] if r > 0])
        results["consistency"] = profitable_oos / len(results["out_sample_returns"]) * 100
        
        # Calculate efficiency (avg OOS return / avg IS return)
        avg_is = sum(results["in_sample_returns"]) / len(results["in_sample_returns"])
        avg_oos = sum(results["out_sample_returns"]) / len(results["out_sample_returns"])
        results["efficiency"] = (avg_oos / avg_is * 100) if avg_is != 0 else 0
        
        return results
    
    def parameter_sensitivity(
        self,
        results: List[BacktestResult],
        parameter: str
    ) -> Dict[str, any]:
        """
        Analyze parameter sensitivity.
        
        Args:
            results: List of backtest results with different parameter values
            parameter: Parameter name to analyze
            
        Returns:
            Sensitivity analysis
        """
        if not results:
            return {}
        
        # Sort by parameter value
        sorted_results = sorted(results, key=lambda r: r.parameters.get(parameter, 0))
        
        sensitivity = {
            "parameter": parameter,
            "values": [],
            "returns": [],
            "sharpe_ratios": [],
            "optimal_value": None,
            "stability": 0.0
        }
        
        for r in sorted_results:
            param_value = r.parameters.get(parameter)
            if param_value is not None:
                sensitivity["values"].append(param_value)
                sensitivity["returns"].append(r.total_return)
                sensitivity["sharpe_ratios"].append(r.sharpe_ratio)
        
        # Find optimal
        if sensitivity["sharpe_ratios"]:
            max_idx = sensitivity["sharpe_ratios"].index(max(sensitivity["sharpe_ratios"]))
            sensitivity["optimal_value"] = sensitivity["values"][max_idx]
        
        # Calculate stability (how much returns vary)
        if sensitivity["returns"]:
            mean_return = sum(sensitivity["returns"]) / len(sensitivity["returns"])
            variance = sum((r - mean_return) ** 2 for r in sensitivity["returns"]) / len(sensitivity["returns"])
            std = math.sqrt(variance)
            sensitivity["stability"] = 100 - min(100, std)  # Higher is more stable
        
        return sensitivity
    
    def format_backtest_report(self, result: BacktestResult) -> str:
        """Format backtest result as detailed report."""
        lines = []
        
        lines.append("=" * 50)
        lines.append(f"📊 BACKTEST REPORT: {result.strategy_name}")
        lines.append("=" * 50)
        lines.append("")
        
        # Period
        years = (result.end_date - result.start_date).days / 365
        lines.append(f"**Period:** {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')} ({years:.1f} years)")
        lines.append("")
        
        # Capital
        lines.append("**Capital:**")
        lines.append(f"  Initial: ${result.initial_capital:,.0f}")
        lines.append(f"  Final: ${result.final_capital:,.0f}")
        lines.append(f"  Net P&L: ${result.final_capital - result.initial_capital:,.0f}")
        lines.append("")
        
        # Returns
        lines.append("**Returns:**")
        lines.append(f"  Total: {'+' if result.total_return >= 0 else ''}{result.total_return:.2f}%")
        lines.append(f"  Annualized: {'+' if result.annualized_return >= 0 else ''}{result.annualized_return:.2f}%")
        if result.benchmark_return:
            lines.append(f"  Benchmark: {'+' if result.benchmark_return >= 0 else ''}{result.benchmark_return:.2f}%")
            lines.append(f"  Alpha: {'+' if result.alpha >= 0 else ''}{result.alpha:.2f}%")
        lines.append("")
        
        # Risk
        lines.append("**Risk Metrics:**")
        lines.append(f"  Volatility: {result.volatility:.2f}%")
        lines.append(f"  Max Drawdown: -{result.max_drawdown:.2f}%")
        lines.append(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        lines.append(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
        lines.append("")
        
        # Trades
        lines.append("**Trade Statistics:**")
        lines.append(f"  Total Trades: {result.total_trades}")
        lines.append(f"  Win Rate: {result.win_rate:.1f}%")
        lines.append(f"  Profit Factor: {result.profit_factor:.2f}")
        lines.append(f"  Avg Trade: {'+' if result.avg_trade >= 0 else ''}{result.avg_trade:.2f}%")
        lines.append("")
        
        # Monthly returns summary
        if result.monthly_returns:
            positive_months = len([r for r in result.monthly_returns.values() if r > 0])
            total_months = len(result.monthly_returns)
            lines.append(f"**Monthly Win Rate:** {positive_months}/{total_months} ({positive_months/total_months*100:.0f}%)")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def format_monte_carlo_report(self, result: MonteCarloResult) -> str:
        """Format Monte Carlo results."""
        lines = []
        
        lines.append("🎲 **Monte Carlo Analysis**")
        lines.append(f"Simulations: {result.simulations}")
        lines.append("")
        
        lines.append("**Return Distribution:**")
        lines.append(f"  Original: {'+' if result.original_return >= 0 else ''}{result.original_return:.2f}%")
        lines.append(f"  Mean: {'+' if result.mean_return >= 0 else ''}{result.mean_return:.2f}%")
        lines.append(f"  Median: {'+' if result.median_return >= 0 else ''}{result.median_return:.2f}%")
        lines.append(f"  Std Dev: {result.std_dev:.2f}%")
        lines.append("")
        
        lines.append("**Percentiles:**")
        lines.append(f"  5th: {result.percentile_5:.2f}%")
        lines.append(f"  25th: {result.percentile_25:.2f}%")
        lines.append(f"  75th: {result.percentile_75:.2f}%")
        lines.append(f"  95th: {result.percentile_95:.2f}%")
        lines.append("")
        
        lines.append("**Risk Analysis:**")
        lines.append(f"  Probability of Loss: {result.probability_of_loss:.1f}%")
        lines.append(f"  Expected Max DD: -{result.expected_max_drawdown:.1f}%")
        lines.append(f"  Worst Case: {result.worst_case_return:.2f}%")
        lines.append(f"  Best Case: {result.best_case_return:.2f}%")
        
        return "\n".join(lines)
