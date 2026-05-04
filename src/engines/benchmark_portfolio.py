"""
Benchmark-Aware Portfolio Intelligence Engine.

Provides:
  1. Portfolio vs benchmark attribution (what drove alpha/drag)
  2. Sector contribution analysis
  3. Factor exposure decomposition (momentum, value, size, vol)
  4. Risk-adjusted metrics vs benchmark (Sharpe, Sortino, Information Ratio)
  5. Drawdown analysis relative to benchmark
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PositionSnapshot:
    """Single position for portfolio analysis."""
    ticker: str
    weight: float  # 0-1, fraction of portfolio
    return_pct: float  # period return %
    sector: str = ""
    beta: float = 1.0
    contribution: float = 0.0  # weight * return


@dataclass
class BenchmarkAttribution:
    """Portfolio vs benchmark attribution result."""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0  # portfolio - benchmark
    tracking_error: float = 0.0
    information_ratio: float = 0.0

    # Decomposition
    allocation_effect: float = 0.0  # from overweighting/underweighting
    selection_effect: float = 0.0  # from stock picking within sectors
    interaction_effect: float = 0.0  # cross-term

    # Risk metrics
    portfolio_sharpe: float = 0.0
    benchmark_sharpe: float = 0.0
    portfolio_sortino: float = 0.0
    benchmark_sortino: float = 0.0
    portfolio_max_dd: float = 0.0
    benchmark_max_dd: float = 0.0
    beta: float = 1.0
    alpha: float = 0.0
    treynor_ratio: float = 0.0

    # Sector breakdown
    sector_contributions: Dict[str, float] = field(default_factory=dict)
    sector_weights: Dict[str, float] = field(default_factory=dict)

    # Factor exposures
    factor_exposures: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_return": round(self.portfolio_return, 2),
            "benchmark_return": round(self.benchmark_return, 2),
            "active_return": round(self.active_return, 2),
            "tracking_error": round(self.tracking_error, 2),
            "information_ratio": round(self.information_ratio, 2),
            "allocation_effect": round(self.allocation_effect, 2),
            "selection_effect": round(self.selection_effect, 2),
            "interaction_effect": round(self.interaction_effect, 2),
            "portfolio_sharpe": round(self.portfolio_sharpe, 2),
            "benchmark_sharpe": round(self.benchmark_sharpe, 2),
            "portfolio_sortino": round(self.portfolio_sortino, 2),
            "benchmark_sortino": round(self.benchmark_sortino, 2),
            "portfolio_max_dd": round(self.portfolio_max_dd, 2),
            "benchmark_max_dd": round(self.benchmark_max_dd, 2),
            "beta": round(self.beta, 2),
            "alpha": round(self.alpha, 2),
            "treynor_ratio": round(self.treynor_ratio, 2),
            "sector_contributions": {k: round(v, 2) for k, v in self.sector_contributions.items()},
            "sector_weights": {k: round(v, 2) for k, v in self.sector_weights.items()},
            "factor_exposures": {k: round(v, 3) for k, v in self.factor_exposures.items()},
        }


class BenchmarkPortfolioEngine:
    """
    Benchmark-aware portfolio intelligence.

    Computes attribution, factor exposure, and risk metrics
    relative to a benchmark (default: SPY).
    """

    # Simple factor loadings by sector (for decomposition)
    SECTOR_FACTOR_LOADINGS: Dict[str, Dict[str, float]] = {
        "Technology": {"momentum": 0.8, "growth": 0.9, "size": -0.3, "vol": 0.6},
        "Financials": {"momentum": 0.4, "growth": 0.3, "size": 0.2, "vol": 0.5},
        "Healthcare": {"momentum": 0.3, "growth": 0.5, "size": -0.1, "vol": 0.3},
        "Energy": {"momentum": 0.5, "growth": -0.2, "size": 0.3, "vol": 0.8},
        "Consumer": {"momentum": 0.4, "growth": 0.4, "size": 0.0, "vol": 0.4},
        "Industrials": {"momentum": 0.5, "growth": 0.3, "size": 0.1, "vol": 0.5},
        "Utilities": {"momentum": -0.2, "growth": -0.3, "size": 0.2, "vol": -0.3},
        "Staples": {"momentum": -0.1, "growth": -0.2, "size": 0.1, "vol": -0.2},
        "REITs": {"momentum": 0.2, "growth": 0.1, "size": 0.3, "vol": 0.4},
        "Crypto": {"momentum": 0.9, "growth": 0.8, "size": -0.5, "vol": 1.0},
    }

    def __init__(self, benchmark: str = "SPY"):
        self.benchmark = benchmark

    def compute_attribution(
        self,
        positions: List[PositionSnapshot],
        benchmark_return: float,
        benchmark_returns_series: Optional[List[float]] = None,
        portfolio_returns_series: Optional[List[float]] = None,
        risk_free_rate: float = 0.04,
    ) -> BenchmarkAttribution:
        """
        Full benchmark attribution analysis.

        Args:
            positions: current portfolio positions with weights and returns
            benchmark_return: benchmark period return (%)
            benchmark_returns_series: daily benchmark returns for Sharpe/Sortino
            portfolio_returns_series: daily portfolio returns for Sharpe/Sortino
            risk_free_rate: annualized risk-free rate
        """
        result = BenchmarkAttribution()
        result.benchmark_return = benchmark_return

        if not positions:
            return result

        # Portfolio return = sum(weight * return)
        result.portfolio_return = sum(p.weight * p.return_pct for p in positions)
        result.active_return = result.portfolio_return - benchmark_return

        # Sector contributions
        sector_returns: Dict[str, List[float]] = {}
        sector_weights: Dict[str, float] = {}
        for p in positions:
            sector = p.sector or "Unknown"
            sector_returns.setdefault(sector, []).append(p.return_pct)
            sector_weights[sector] = sector_weights.get(sector, 0) + p.weight

        result.sector_weights = sector_weights
        for sector, rets in sector_returns.items():
            avg_ret = np.mean(rets)
            w = sector_weights[sector]
            result.sector_contributions[sector] = round(w * avg_ret, 2)

        # Factor exposures
        result.factor_exposures = self._compute_factor_exposures(positions)

        # Sharpe ratio
        if portfolio_returns_series and len(portfolio_returns_series) > 5:
            result.portfolio_sharpe = self._sharpe_ratio(
                portfolio_returns_series, risk_free_rate
            )
            result.portfolio_sortino = self._sortino_ratio(
                portfolio_returns_series, risk_free_rate
            )
            result.portfolio_max_dd = self._max_drawdown(portfolio_returns_series)

        if benchmark_returns_series and len(benchmark_returns_series) > 5:
            result.benchmark_sharpe = self._sharpe_ratio(
                benchmark_returns_series, risk_free_rate
            )
            result.benchmark_sortino = self._sortino_ratio(
                benchmark_returns_series, risk_free_rate
            )
            result.benchmark_max_dd = self._max_drawdown(benchmark_returns_series)

            # Beta and alpha
            result.beta = self._compute_beta(
                portfolio_returns_series, benchmark_returns_series
            )
            daily_rf = risk_free_rate / 252
            port_mean = np.mean(portfolio_returns_series)
            bench_mean = np.mean(benchmark_returns_series)
            result.alpha = (port_mean - daily_rf - result.beta * (bench_mean - daily_rf)) * 252 * 100

            # Information ratio
            active_returns = [
                p - b for p, b in zip(portfolio_returns_series, benchmark_returns_series)
            ]
            if len(active_returns) > 1:
                te = np.std(active_returns) * np.sqrt(252)
                result.tracking_error = te * 100
                if te > 0:
                    result.information_ratio = (
                        np.mean(active_returns) * 252 / te
                    )

            # Treynor ratio
            if result.beta != 0:
                result.treynor_ratio = (
                    (result.portfolio_return - risk_free_rate * 100) / result.beta
                )

        # Brinson attribution (simplified)
        result.allocation_effect, result.selection_effect = self._brinson_attribution(
            positions, benchmark_return
        )

        return result

    def _compute_factor_exposures(
        self, positions: List[PositionSnapshot]
    ) -> Dict[str, float]:
        """Compute weighted factor exposures from sector loadings."""
        factors: Dict[str, float] = {"momentum": 0, "growth": 0, "size": 0, "vol": 0}
        total_weight = sum(p.weight for p in positions)
        if total_weight == 0:
            return factors

        for p in positions:
            sector = p.sector or "Unknown"
            loadings = self.SECTOR_FACTOR_LOADINGS.get(sector, {})
            for f in factors:
                factors[f] += (p.weight / total_weight) * loadings.get(f, 0) * p.beta

        return factors

    def _brinson_attribution(
        self,
        positions: List[PositionSnapshot],
        benchmark_return: float,
    ) -> Tuple[float, float]:
        """Simplified Brinson attribution: allocation + selection effects."""
        # Group by sector
        sector_data: Dict[str, Dict] = {}
        for p in positions:
            sector = p.sector or "Unknown"
            if sector not in sector_data:
                sector_data[sector] = {"weight": 0, "returns": []}
            sector_data[sector]["weight"] += p.weight
            sector_data[sector]["returns"].append(p.return_pct)

        # Equal-weight benchmark sector assumption
        n_sectors = max(len(sector_data), 1)
        bench_sector_weight = 1.0 / n_sectors

        allocation = 0.0
        selection = 0.0
        for sector, data in sector_data.items():
            port_w = data["weight"]
            port_r = np.mean(data["returns"])
            # Allocation: overweight sectors that outperform
            allocation += (port_w - bench_sector_weight) * (port_r - benchmark_return / 100)
            # Selection: pick better stocks within sectors
            selection += bench_sector_weight * (port_r - benchmark_return / 100)

        return allocation * 100, selection * 100

    @staticmethod
    def _sharpe_ratio(returns: List[float], risk_free_rate: float = 0.04) -> float:
        """Annualized Sharpe ratio."""
        arr = np.array(returns)
        if len(arr) < 2 or np.std(arr) == 0:
            return 0.0
        daily_rf = risk_free_rate / 252
        excess = arr - daily_rf
        return float(np.mean(excess) / np.std(excess) * np.sqrt(252))

    @staticmethod
    def _sortino_ratio(returns: List[float], risk_free_rate: float = 0.04) -> float:
        """Annualized Sortino ratio (downside deviation only)."""
        arr = np.array(returns)
        if len(arr) < 2:
            return 0.0
        daily_rf = risk_free_rate / 252
        excess = arr - daily_rf
        downside = excess[excess < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(downside) * np.sqrt(252))

    @staticmethod
    def _max_drawdown(returns: List[float]) -> float:
        """Maximum drawdown from return series (%)."""
        arr = np.array(returns)
        cumulative = np.cumprod(1 + arr / 100)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak * 100
        return float(np.min(drawdown))

    @staticmethod
    def _compute_beta(
        portfolio_returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Portfolio beta vs benchmark."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 5:
            return 1.0
        p = np.array(portfolio_returns[-n:])
        b = np.array(benchmark_returns[-n:])
        cov = np.cov(p, b)
        if cov[1, 1] == 0:
            return 1.0
        return float(cov[0, 1] / cov[1, 1])
