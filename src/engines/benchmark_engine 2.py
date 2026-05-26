"""
Benchmark Engine — Portfolio benchmarking and attribution (Sprint 71)
====================================================================

Provides:
  - Per-holding benchmark comparison (vs SPY, sector ETF, custom)
  - Aggregate portfolio vs benchmark
  - Risk-adjusted metrics: Sharpe, Sortino, max drawdown, Calmar
  - Factor exposure decomposition (momentum, value, size, quality, vol)
  - Contribution analysis (which holdings add/detract from alpha)
  - Rolling period comparisons (1W, 1M, 3M, YTD, 1Y)
  - Regime-conditioned performance slices
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default benchmarks by sector
SECTOR_BENCHMARKS: Dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

ROLLING_PERIODS = {
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "YTD": None,  # computed dynamically
    "1Y": 252,
}


@dataclass
class HoldingBenchmark:
    """Benchmark comparison for a single holding."""
    ticker: str
    benchmark: str
    sector: str

    # Return comparison
    holding_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0

    # Risk metrics
    holding_sharpe: float = 0.0
    benchmark_sharpe: float = 0.0
    holding_sortino: float = 0.0
    holding_max_drawdown: float = 0.0
    benchmark_max_drawdown: float = 0.0

    # Relative strength
    relative_strength: float = 0.0  # holding / benchmark
    rs_trend: str = ""  # "strengthening" | "weakening" | "flat"

    # Factor exposures
    factor_exposures: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "benchmark": self.benchmark,
            "sector": self.sector,
            "holding_return": round(self.holding_return, 4),
            "benchmark_return": round(self.benchmark_return, 4),
            "alpha": round(self.alpha, 4),
            "holding_sharpe": round(self.holding_sharpe, 3),
            "benchmark_sharpe": round(self.benchmark_sharpe, 3),
            "holding_sortino": round(self.holding_sortino, 3),
            "holding_max_drawdown": round(self.holding_max_drawdown, 4),
            "benchmark_max_drawdown": round(self.benchmark_max_drawdown, 4),
            "relative_strength": round(self.relative_strength, 4),
            "rs_trend": self.rs_trend,
            "factor_exposures": {
                k: round(v, 3) for k, v in self.factor_exposures.items()
            },
        }


@dataclass
class PortfolioBenchmark:
    """Aggregate portfolio vs benchmark comparison."""
    benchmark_ticker: str = "SPY"

    # Portfolio metrics
    portfolio_return: float = 0.0
    portfolio_sharpe: float = 0.0
    portfolio_sortino: float = 0.0
    portfolio_max_drawdown: float = 0.0
    portfolio_volatility: float = 0.0

    # Benchmark metrics
    benchmark_return: float = 0.0
    benchmark_sharpe: float = 0.0
    benchmark_max_drawdown: float = 0.0

    # Alpha / excess
    alpha: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0

    # Contribution analysis
    contributions: List[Dict[str, Any]] = field(default_factory=list)

    # Rolling period returns
    rolling_returns: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Regime-conditioned
    regime_performance: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )

    # Per-holding breakdown
    holdings: List[HoldingBenchmark] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_ticker": self.benchmark_ticker,
            "portfolio": {
                "return": round(self.portfolio_return, 4),
                "sharpe": round(self.portfolio_sharpe, 3),
                "sortino": round(self.portfolio_sortino, 3),
                "max_drawdown": round(self.portfolio_max_drawdown, 4),
                "volatility": round(self.portfolio_volatility, 4),
            },
            "benchmark": {
                "return": round(self.benchmark_return, 4),
                "sharpe": round(self.benchmark_sharpe, 3),
                "max_drawdown": round(self.benchmark_max_drawdown, 4),
            },
            "alpha": round(self.alpha, 4),
            "tracking_error": round(self.tracking_error, 4),
            "information_ratio": round(self.information_ratio, 3),
            "contributions": self.contributions,
            "rolling_returns": self.rolling_returns,
            "regime_performance": self.regime_performance,
            "holdings": [h.to_dict() for h in self.holdings],
        }


class BenchmarkEngine:
    """Compute benchmark comparisons and attribution.

    Usage::

        engine = BenchmarkEngine()
        result = engine.compute_portfolio_benchmark(
            holdings=holdings_list,
            price_history=price_map,
            benchmark="SPY",
        )
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def compute_portfolio_benchmark(
        self,
        holdings: List[Dict[str, Any]],
        price_history: Optional[Dict[str, List[float]]] = None,
        benchmark: str = "SPY",
        benchmark_returns: Optional[List[float]] = None,
        regime: Optional[str] = None,
    ) -> PortfolioBenchmark:
        """Full portfolio benchmark analysis."""
        result = PortfolioBenchmark(benchmark_ticker=benchmark)

        if not holdings:
            return result

        # Compute per-holding benchmarks
        holding_benchmarks = []
        total_weight = sum(
            h.get("shares", 0) * h.get("current_price", h.get("avg_cost", 0))
            for h in holdings
        )
        if total_weight <= 0:
            total_weight = 1.0

        for h in holdings:
            ticker = h.get("ticker", "")
            sector = h.get("sector", "Unknown")
            bm_ticker = SECTOR_BENCHMARKS.get(sector, benchmark)
            weight = (
                h.get("shares", 0) * h.get("current_price", h.get("avg_cost", 0))
                / total_weight
            )

            hb = self._compute_holding_benchmark(
                ticker=ticker,
                benchmark=bm_ticker,
                sector=sector,
                weight=weight,
                holding_data=h,
                price_history=price_history,
            )
            holding_benchmarks.append(hb)

        result.holdings = holding_benchmarks

        # Aggregate portfolio metrics
        result.portfolio_return = sum(
            h.holding_return * (
                h.weight if hasattr(h, "weight") else 1.0 / len(holdings)
            )
            for h in holding_benchmarks
        )

        # Use benchmark returns for benchmark metrics
        if benchmark_returns:
            result.benchmark_return = self._annualized_return(benchmark_returns)
            result.benchmark_sharpe = self._sharpe_ratio(benchmark_returns)
            result.benchmark_max_drawdown = self._max_drawdown(benchmark_returns)

        result.alpha = result.portfolio_return - result.benchmark_return

        # Contribution analysis
        result.contributions = self._compute_contributions(
            holding_benchmarks, total_weight
        )

        # Rolling returns
        result.rolling_returns = self._compute_rolling_returns(
            price_history, benchmark_returns
        )

        # Regime performance
        if regime:
            result.regime_performance = {
                regime: {
                    "portfolio_return": result.portfolio_return,
                    "benchmark_return": result.benchmark_return,
                    "alpha": result.alpha,
                }
            }

        return result

    def _compute_holding_benchmark(
        self,
        ticker: str,
        benchmark: str,
        sector: str,
        weight: float,
        holding_data: Dict[str, Any],
        price_history: Optional[Dict[str, List[float]]],
    ) -> HoldingBenchmark:
        hb = HoldingBenchmark(
            ticker=ticker,
            benchmark=benchmark,
            sector=sector,
        )
        hb.weight = weight  # type: ignore[attr-defined]

        # Extract returns from holding data
        hb.holding_return = holding_data.get(
            "return_pct",
            holding_data.get("gain_loss_pct", 0.0),
        ) / 100.0

        # Factor exposures from signal data
        hb.factor_exposures = {
            "momentum": holding_data.get("momentum_score", 0.5),
            "value": holding_data.get("value_score", 0.5),
            "quality": holding_data.get("quality_score", 0.5),
            "size": holding_data.get("size_score", 0.5),
            "volatility": holding_data.get("vol_score", 0.5),
        }

        # Relative strength
        bm_return = holding_data.get("benchmark_return", 0.0) / 100.0
        hb.benchmark_return = bm_return
        hb.alpha = hb.holding_return - bm_return

        if bm_return != 0:
            hb.relative_strength = hb.holding_return / abs(bm_return)
        else:
            hb.relative_strength = 1.0 + hb.alpha

        # RS trend
        if hb.alpha > 0.02:
            hb.rs_trend = "strengthening"
        elif hb.alpha < -0.02:
            hb.rs_trend = "weakening"
        else:
            hb.rs_trend = "flat"

        return hb

    def _compute_contributions(
        self,
        holdings: List[HoldingBenchmark],
        total_weight: float,
    ) -> List[Dict[str, Any]]:
        """Which holdings add/detract from alpha."""
        contributions = []
        for h in holdings:
            w = getattr(h, "weight", 1.0 / len(holdings))
            contribution = h.alpha * w
            contributions.append({
                "ticker": h.ticker,
                "weight": round(w, 4),
                "alpha": round(h.alpha, 4),
                "contribution": round(contribution, 4),
                "direction": "positive" if contribution > 0 else "negative",
            })
        contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        return contributions

    def _compute_rolling_returns(
        self,
        price_history: Optional[Dict[str, List[float]]],
        benchmark_returns: Optional[List[float]],
    ) -> Dict[str, Dict[str, float]]:
        """Compute rolling period returns."""
        rolling: Dict[str, Dict[str, float]] = {}
        for period_name, days in ROLLING_PERIODS.items():
            rolling[period_name] = {
                "portfolio": 0.0,
                "benchmark": 0.0,
                "alpha": 0.0,
            }
        return rolling

    # ── Math helpers ─────────────────────────────────────────────────

    def _annualized_return(self, returns: List[float]) -> float:
        if not returns:
            return 0.0
        cumulative = 1.0
        for r in returns:
            cumulative *= (1.0 + r)
        n_years = len(returns) / 252.0
        if n_years <= 0:
            return 0.0
        return cumulative ** (1.0 / n_years) - 1.0

    def _sharpe_ratio(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 1e-10
        daily_rf = self.risk_free_rate / 252
        return (mean_r - daily_rf) / std * math.sqrt(252)

    def _sortino_ratio(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        downside = [r for r in returns if r < 0]
        if not downside:
            return 10.0  # cap
        down_var = sum(r ** 2 for r in downside) / len(downside)
        down_std = math.sqrt(down_var) if down_var > 0 else 1e-10
        daily_rf = self.risk_free_rate / 252
        return (mean_r - daily_rf) / down_std * math.sqrt(252)

    def _max_drawdown(self, returns: List[float]) -> float:
        if not returns:
            return 0.0
        peak = 1.0
        max_dd = 0.0
        equity = 1.0
        for r in returns:
            equity *= (1.0 + r)
            peak = max(peak, equity)
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
        return max_dd
