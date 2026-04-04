"""
Strategy Portfolio Lab
=======================

Multi-strategy sleeve optimizer that answers:
"How to mix strategy sleeves optimally?"

Given a set of strategy return streams, computes:
  - Max Sharpe weights
  - Min drawdown weights
  - Risk parity weights
  - Correlation matrix
  - Combined equity curve + attribution
  - Regime-conditioned weight profile (if regime data available)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SleeveResult:
    """Result for one optimization objective."""

    objective: str                      # max_sharpe | min_drawdown | risk_parity
    weights: Dict[str, float]           # strategy → weight
    expected_return: float              # annualized
    expected_vol: float                 # annualized
    sharpe: float
    max_drawdown: float
    equity_curve: List[float]


@dataclass
class StrategyPortfolioResult:
    """Full portfolio lab output."""

    strategies: List[str]
    correlation_matrix: Dict[str, Dict[str, float]]
    optimizations: List[SleeveResult]
    combined_equity: List[float]
    combined_dates: List[str]
    attribution: Dict[str, float]       # strategy → contribution %
    regime_weights: Optional[Dict[str, Dict[str, float]]] = None


class StrategyPortfolioLab:
    """Multi-strategy sleeve optimizer."""

    def __init__(self, risk_free_rate: float = 0.045):
        self.rf = risk_free_rate

    def optimize(
        self,
        return_streams: Dict[str, List[float]],
        dates: Optional[List[str]] = None,
        regime: Optional[str] = None,
    ) -> StrategyPortfolioResult:
        """Run full optimization suite.

        Parameters
        ----------
        return_streams : dict
            strategy_name → list of periodic returns (e.g. daily or monthly).
            All lists must be same length.
        dates : list[str], optional
            Date labels aligned with return arrays.
        regime : str, optional
            Current regime for conditioned weights.

        Returns
        -------
        StrategyPortfolioResult
        """
        strategies = list(return_streams.keys())
        n = len(strategies)
        if n < 2:
            raise ValueError("Need ≥ 2 strategies for optimization")

        # Align lengths
        min_len = min(len(v) for v in return_streams.values())
        if min_len < 10:
            raise ValueError(
                f"Need ≥ 10 return observations, got {min_len}",
            )

        R = np.array([
            return_streams[s][:min_len] for s in strategies
        ], dtype=float)  # shape: (n_strategies, T)

        # Correlation + covariance
        corr = np.corrcoef(R)
        cov = np.cov(R)

        # Annualization factor (assume monthly if < 60 obs, else daily)
        ann = 12.0 if min_len < 60 else 252.0

        means = R.mean(axis=1) * ann
        vols = R.std(axis=1) * math.sqrt(ann)

        # Build correlation dict
        corr_dict: Dict[str, Dict[str, float]] = {}
        for i, si in enumerate(strategies):
            corr_dict[si] = {}
            for j, sj in enumerate(strategies):
                corr_dict[si][sj] = round(float(corr[i, j]), 3)

        # ── Optimization: Max Sharpe ──
        max_sharpe = self._max_sharpe_weights(
            means, cov, ann, R, strategies,
        )

        # ── Optimization: Min Drawdown ──
        min_dd = self._min_drawdown_weights(R, ann, strategies)

        # ── Optimization: Risk Parity ──
        risk_par = self._risk_parity_weights(
            cov, ann, R, strategies,
        )

        optimizations = [max_sharpe, min_dd, risk_par]

        # Combined equity using max-Sharpe weights
        best_w = np.array([
            max_sharpe.weights[s] for s in strategies
        ])
        combined_rets = R.T @ best_w  # (T,)
        combined_eq = [100.0]
        for r in combined_rets:
            combined_eq.append(
                round(combined_eq[-1] * (1 + r), 2),
            )

        # Attribution — contribution of each sleeve
        total_ret = combined_eq[-1] / combined_eq[0] - 1
        attribution: Dict[str, float] = {}
        for i, s in enumerate(strategies):
            sleeve_ret = float(np.sum(R[i]) * best_w[i])
            pct = (sleeve_ret / total_ret * 100) if total_ret != 0 else 0
            attribution[s] = round(pct, 1)

        # Regime-conditioned weights
        regime_weights = None
        if regime:
            regime_weights = self._regime_conditioned(
                regime, means, vols, corr, strategies,
            )

        combined_dates = dates[:min_len + 1] if dates else [
            f"T{i}" for i in range(min_len + 1)
        ]

        return StrategyPortfolioResult(
            strategies=strategies,
            correlation_matrix=corr_dict,
            optimizations=optimizations,
            combined_equity=combined_eq,
            combined_dates=combined_dates,
            attribution=attribution,
            regime_weights=regime_weights,
        )

    # ------------------------------------------------------------------
    # Optimizers (analytical, no scipy dependency)
    # ------------------------------------------------------------------

    def _max_sharpe_weights(
        self,
        means: np.ndarray,
        cov: np.ndarray,
        ann: float,
        R: np.ndarray,
        strategies: List[str],
    ) -> SleeveResult:
        """Analytical max-Sharpe via inverse-variance shortcut."""
        n = len(strategies)
        try:
            excess = means - self.rf
            inv_cov = np.linalg.inv(cov * ann)
            raw = inv_cov @ excess
            if raw.sum() <= 0:
                raw = np.ones(n)
            w = np.clip(raw / raw.sum(), 0, 1)
            w = w / w.sum()
        except np.linalg.LinAlgError:
            w = np.ones(n) / n

        return self._build_result("max_sharpe", w, R, ann, strategies)

    def _min_drawdown_weights(
        self,
        R: np.ndarray,
        ann: float,
        strategies: List[str],
    ) -> SleeveResult:
        """Grid search for minimum max-drawdown portfolio."""
        n = len(strategies)
        if n == 2:
            best_w, best_dd = None, 999
            for a in np.linspace(0, 1, 21):
                w = np.array([a, 1 - a])
                dd = self._max_dd(R.T @ w)
                if dd < best_dd:
                    best_dd = dd
                    best_w = w
            return self._build_result(
                "min_drawdown", best_w, R, ann, strategies,  # type: ignore[arg-type]
            )

        # For >2 strategies, use inverse-vol heuristic
        vols = R.std(axis=1)
        inv_vol = 1.0 / np.maximum(vols, 1e-8)
        w = inv_vol / inv_vol.sum()
        return self._build_result("min_drawdown", w, R, ann, strategies)

    def _risk_parity_weights(
        self,
        cov: np.ndarray,
        ann: float,
        R: np.ndarray,
        strategies: List[str],
    ) -> SleeveResult:
        """Risk parity — equal risk contribution."""
        vols = np.sqrt(np.diag(cov))
        inv_vol = 1.0 / np.maximum(vols, 1e-8)
        w = inv_vol / inv_vol.sum()
        return self._build_result("risk_parity", w, R, ann, strategies)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_result(
        self,
        objective: str,
        w: np.ndarray,
        R: np.ndarray,
        ann: float,
        strategies: List[str],
    ) -> SleeveResult:
        port_rets = R.T @ w
        eq = [100.0]
        for r in port_rets:
            eq.append(round(eq[-1] * (1 + r), 2))

        ann_ret = float(np.mean(port_rets) * ann) * 100
        ann_vol = float(np.std(port_rets) * math.sqrt(ann)) * 100
        sharpe = (
            (ann_ret / 100 - self.rf) / (ann_vol / 100)
            if ann_vol > 0 else 0
        )
        dd = self._max_dd(port_rets)

        weights = {
            s: round(float(w[i]), 4) for i, s in enumerate(strategies)
        }

        return SleeveResult(
            objective=objective,
            weights=weights,
            expected_return=round(ann_ret, 2),
            expected_vol=round(ann_vol, 2),
            sharpe=round(sharpe, 2),
            max_drawdown=round(dd, 2),
            equity_curve=eq,
        )

    @staticmethod
    def _max_dd(returns: np.ndarray) -> float:
        """Max drawdown from return series."""
        cum = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cum)
        dd = (cum - peak) / peak
        return float(np.min(dd)) * 100  # as negative %

    @staticmethod
    def _regime_conditioned(
        regime: str,
        means: np.ndarray,
        vols: np.ndarray,
        corr: np.ndarray,
        strategies: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Suggest weight tilts by regime."""
        n = len(strategies)
        base = np.ones(n) / n

        # Regime modifiers
        regime_upper = regime.upper()
        if "BULL" in regime_upper or "RISK_ON" in regime_upper:
            # Tilt toward higher-return sleeves
            tilt = means / np.maximum(means.sum(), 1e-8)
            w = 0.5 * base + 0.5 * tilt
        elif "BEAR" in regime_upper or "RISK_OFF" in regime_upper:
            # Tilt toward lower-vol sleeves
            inv_vol = 1.0 / np.maximum(vols, 1e-8)
            tilt = inv_vol / inv_vol.sum()
            w = 0.3 * base + 0.7 * tilt
        elif "CRISIS" in regime_upper:
            # Heavy defensive
            inv_vol = 1.0 / np.maximum(vols, 1e-8)
            w = 0.1 * base + 0.9 * (inv_vol / inv_vol.sum())
        else:
            w = base

        w = np.clip(w, 0, 1)
        w = w / w.sum()

        return {
            regime: {
                s: round(float(w[i]), 4)
                for i, s in enumerate(strategies)
            },
        }
