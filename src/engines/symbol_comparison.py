"""
Symbol Comparison Engine.

Compares a ticker against:
  1. Peers (same sector, similar market cap)
  2. Sector ETF
  3. Index (SPY)

Outputs relative strength, valuation, momentum, and quality metrics
in a structured format for API/dashboard consumption.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of symbol comparison against a benchmark."""
    ticker: str
    benchmark: str
    benchmark_type: str  # "peer", "sector", "index"

    # Relative performance
    rs_1m: float = 0.0  # relative strength 1 month
    rs_3m: float = 0.0
    rs_6m: float = 0.0
    rs_12m: float = 0.0
    rs_composite: float = 0.0  # weighted composite

    # Momentum
    momentum_rank: int = 0  # rank among peers (1 = best)
    momentum_percentile: float = 50.0  # 0-100

    # Volatility
    relative_volatility: float = 1.0  # stock vol / benchmark vol
    beta: float = 1.0

    # Valuation (if available)
    pe_ratio: Optional[float] = None
    pe_vs_benchmark: Optional[float] = None  # premium/discount %

    # Quality
    win_rate_vs_benchmark: float = 0.0  # % of periods outperforming
    max_drawdown_vs: float = 0.0  # drawdown difference

    # Summary
    verdict: str = "NEUTRAL"  # LEADER / STRONG / NEUTRAL / WEAK / LAGGARD
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "benchmark": self.benchmark,
            "benchmark_type": self.benchmark_type,
            "rs_1m": round(self.rs_1m, 1),
            "rs_3m": round(self.rs_3m, 1),
            "rs_6m": round(self.rs_6m, 1),
            "rs_12m": round(self.rs_12m, 1),
            "rs_composite": round(self.rs_composite, 1),
            "momentum_rank": self.momentum_rank,
            "momentum_percentile": round(self.momentum_percentile, 1),
            "relative_volatility": round(self.relative_volatility, 2),
            "beta": round(self.beta, 2),
            "pe_ratio": self.pe_ratio,
            "pe_vs_benchmark": round(self.pe_vs_benchmark, 1) if self.pe_vs_benchmark is not None else None,
            "win_rate_vs_benchmark": round(self.win_rate_vs_benchmark, 1),
            "max_drawdown_vs": round(self.max_drawdown_vs, 1),
            "verdict": self.verdict,
            "summary": self.summary,
        }


class SymbolComparisonEngine:
    """
    Compare a symbol against peers, sector, or index.

    Uses price return data to compute relative strength,
    momentum ranking, and risk-adjusted comparison.
    """

    def compare_vs_benchmark(
        self,
        ticker_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        ticker: str,
        benchmark: str,
        benchmark_type: str = "index",
    ) -> ComparisonResult:
        """
        Compare ticker returns against benchmark returns.

        Args:
            ticker_returns: array of daily returns (%) for the ticker
            benchmark_returns: array of daily returns (%) for the benchmark
            ticker: ticker symbol
            benchmark: benchmark symbol
            benchmark_type: "peer", "sector", or "index"
        """
        result = ComparisonResult(
            ticker=ticker, benchmark=benchmark, benchmark_type=benchmark_type
        )

        n = min(len(ticker_returns), len(benchmark_returns))
        if n < 5:
            result.summary = "Insufficient data for comparison"
            return result

        t = ticker_returns[-n:]
        b = benchmark_returns[-n:]

        # Relative strength over periods
        result.rs_1m = self._relative_strength(t, b, 21)
        result.rs_3m = self._relative_strength(t, b, 63)
        result.rs_6m = self._relative_strength(t, b, 126)
        result.rs_12m = self._relative_strength(t, b, min(252, n))

        # Weighted composite: 25% 1M, 35% 3M, 25% 6M, 15% 12M
        weights = [0.25, 0.35, 0.25, 0.15]
        rs_values = [result.rs_1m, result.rs_3m, result.rs_6m, result.rs_12m]
        available = min(len(rs_values), n // 21 + 1)
        if available > 0:
            result.rs_composite = sum(
                w * rs for w, rs in zip(weights[:available], rs_values[:available])
            ) / sum(weights[:available])

        # Beta
        result.beta = self._compute_beta(t, b)

        # Relative volatility
        t_vol = np.std(t) * np.sqrt(252) if len(t) > 1 else 0
        b_vol = np.std(b) * np.sqrt(252) if len(b) > 1 else 1
        result.relative_volatility = t_vol / b_vol if b_vol > 0 else 1.0

        # Win rate vs benchmark
        wins = sum(1 for ti, bi in zip(t, b) if ti > bi)
        result.win_rate_vs_benchmark = (wins / n) * 100

        # Max drawdown comparison
        t_dd = self._max_drawdown(t)
        b_dd = self._max_drawdown(b)
        result.max_drawdown_vs = t_dd - b_dd

        # Verdict
        result.verdict = self._classify_verdict(result.rs_composite, result.beta, result.win_rate_vs_benchmark)
        result.summary = self._build_summary(result)

        return result

    def compare_vs_peers(
        self,
        ticker_returns: np.ndarray,
        peer_returns: Dict[str, np.ndarray],
        ticker: str,
    ) -> ComparisonResult:
        """
        Compare ticker against its peer group.

        peer_returns: dict mapping peer_ticker → return array
        """
        # Compute peer average returns
        min_len = min(len(r) for r in peer_returns.values()) if peer_returns else 0
        if min_len < 5 or not peer_returns:
            return ComparisonResult(
                ticker=ticker, benchmark="PEERS", benchmark_type="peer",
                summary="No peer data available"
            )

        peer_avg = np.mean(
            [r[-min_len:] for r in peer_returns.values()], axis=0
        )

        result = self.compare_vs_benchmark(
            ticker_returns[-min_len:], peer_avg, ticker, "PEERS", "peer"
        )

        # Compute rank among peers
        all_rs = {}
        for peer_t, peer_r in peer_returns.items():
            if len(peer_r) >= min_len:
                rs = self._relative_strength(peer_r[-min_len:], peer_avg, min(63, min_len))
                all_rs[peer_t] = rs
        all_rs[ticker] = result.rs_composite

        sorted_peers = sorted(all_rs.items(), key=lambda x: x[1], reverse=True)
        rank = next(
            (i + 1 for i, (t, _) in enumerate(sorted_peers) if t == ticker), 0
        )
        result.momentum_rank = rank
        result.momentum_percentile = (
            (1 - rank / max(len(sorted_peers), 1)) * 100
        )

        return result

    @staticmethod
    def _relative_strength(
        ticker_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        lookback: int,
    ) -> float:
        """Compute Mansfield-style relative strength (100 = in-line)."""
        n = min(len(ticker_returns), len(benchmark_returns), lookback)
        if n < 5:
            return 100.0
        t_cum = np.prod(1 + ticker_returns[-n:] / 100) - 1
        b_cum = np.prod(1 + benchmark_returns[-n:] / 100) - 1
        if b_cum == 0:
            return 100.0 + t_cum * 100
        rs = (1 + t_cum) / (1 + b_cum) * 100
        return max(0, min(300, rs))

    @staticmethod
    def _compute_beta(
        ticker_returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> float:
        n = min(len(ticker_returns), len(benchmark_returns))
        if n < 10:
            return 1.0
        t = ticker_returns[-n:]
        b = benchmark_returns[-n:]
        cov = np.cov(t, b)
        if cov[1, 1] == 0:
            return 1.0
        return float(cov[0, 1] / cov[1, 1])

    @staticmethod
    def _max_drawdown(returns: np.ndarray) -> float:
        cumulative = np.cumprod(1 + returns / 100)
        peak = np.maximum.accumulate(cumulative)
        dd = (cumulative - peak) / peak * 100
        return float(np.min(dd))

    @staticmethod
    def _classify_verdict(
        rs_composite: float, beta: float, win_rate: float
    ) -> str:
        if rs_composite >= 115 and win_rate >= 55:
            return "LEADER"
        elif rs_composite >= 105 and win_rate >= 50:
            return "STRONG"
        elif rs_composite >= 95:
            return "NEUTRAL"
        elif rs_composite >= 85:
            return "WEAK"
        else:
            return "LAGGARD"

    @staticmethod
    def _build_summary(result: ComparisonResult) -> str:
        parts = []
        if result.verdict == "LEADER":
            parts.append(f"{result.ticker} is a clear leader vs {result.benchmark}")
        elif result.verdict == "STRONG":
            parts.append(f"{result.ticker} shows strength vs {result.benchmark}")
        elif result.verdict == "WEAK":
            parts.append(f"{result.ticker} is underperforming {result.benchmark}")
        elif result.verdict == "LAGGARD":
            parts.append(f"{result.ticker} is a laggard vs {result.benchmark}")
        else:
            parts.append(f"{result.ticker} is in-line with {result.benchmark}")

        if result.rs_composite > 100:
            parts.append(f"RS composite {result.rs_composite:.0f} (above benchmark)")
        else:
            parts.append(f"RS composite {result.rs_composite:.0f} (below benchmark)")

        if result.beta > 1.3:
            parts.append(f"High beta ({result.beta:.1f}) — amplified moves")
        elif result.beta < 0.7:
            parts.append(f"Low beta ({result.beta:.1f}) — defensive profile")

        return ". ".join(parts) + "."
