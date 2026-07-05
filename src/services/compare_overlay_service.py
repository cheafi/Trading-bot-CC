"""
Compare Overlay Service
========================

Date-aligned comparison engine for the Compare Overlay surface.

Implements:
  - **Strict mode** — inner join (only dates where ALL tickers traded)
  - **Smooth mode** — outer join + forward-fill (mixed calendars)

Comparison modes:
  1. **Normalized return** — rebased to 100
  2. **Relative strength ratio** — ticker / benchmark
  3. **Rolling correlation** — pairwise rolling Pearson
  4. **Rolling beta** — rolling OLS beta to benchmark

All outputs carry alignment metadata so the UI never silently misaligns.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CompareOverlayResult:
    """Structured output from the compare engine."""

    tickers: List[str]
    dates: List[str]
    series: Dict[str, List[float]]      # ticker → values
    stats: Dict[str, Dict[str, float]]  # ticker → stat dict
    correlation_matrix: Dict[str, Dict[str, float]]
    alignment: Dict[str, Any]           # metadata about join strategy


class CompareOverlayService:
    """Date-aligned multi-instrument comparison engine."""

    def compare(
        self,
        history_map: Dict[str, Any],
        *,
        mode: str = "normalized",
        join: str = "strict",
        benchmark: str = "SPY",
        rolling_window: int = 60,
    ) -> CompareOverlayResult:
        """Run comparison across instruments.

        Parameters
        ----------
        history_map : dict
            ticker → pandas DataFrame with DatetimeIndex + "Close" column.
        mode : str
            "normalized" | "relative_strength" | "rolling_correlation" | "rolling_beta"
        join : str
            "strict" (inner join) | "smooth" (outer + ffill)
        benchmark : str
            Ticker to use as benchmark for relative strength / beta.
        rolling_window : int
            Window size for rolling calculations.

        Returns
        -------
        CompareOverlayResult
        """
        import pandas as pd

        tickers = list(history_map.keys())
        if len(tickers) < 1:
            raise ValueError("Need ≥ 1 ticker for comparison")

        # Build aligned DataFrame
        frames = {}
        for sym, df in history_map.items():
            if df is None or df.empty:
                continue
            col = "Close" if "Close" in df.columns else "close"
            if col not in df.columns:
                continue
            s = df[col].dropna()
            s.name = sym
            frames[sym] = s

        if not frames:
            raise ValueError("No valid price data for any ticker")

        combined = pd.DataFrame(frames)

        # Join strategy
        pre_align_shape = combined.shape
        if join == "strict":
            combined = combined.dropna()
        else:  # smooth
            combined = combined.ffill().dropna()

        post_align_shape = combined.shape
        if len(combined) < 5:
            raise ValueError(
                f"Insufficient aligned data: {post_align_shape[0]} rows "
                f"after {join} join (need ≥ 5)",
            )

        aligned_tickers = [t for t in tickers if t in combined.columns]
        dates = [d.strftime("%Y-%m-%d") for d in combined.index]

        # ── Mode dispatch ──
        if mode == "normalized":
            series, stats = self._normalized(combined, aligned_tickers)
        elif mode == "relative_strength":
            series, stats = self._relative_strength(
                combined, aligned_tickers, benchmark,
            )
        elif mode == "rolling_correlation":
            series, stats = self._rolling_corr(
                combined, aligned_tickers, rolling_window,
            )
        elif mode == "rolling_beta":
            series, stats = self._rolling_beta(
                combined, aligned_tickers, benchmark, rolling_window,
            )
        else:
            series, stats = self._normalized(combined, aligned_tickers)

        # Correlation matrix (on returns)
        rets = combined[aligned_tickers].pct_change().dropna()
        corr = rets.corr()
        corr_dict: Dict[str, Dict[str, float]] = {}
        for t1 in aligned_tickers:
            corr_dict[t1] = {}
            for t2 in aligned_tickers:
                corr_dict[t1][t2] = round(float(corr.loc[t1, t2]), 3)

        alignment = {
            "join_strategy": join,
            "mode": mode,
            "pre_align_rows": pre_align_shape[0],
            "post_align_rows": post_align_shape[0],
            "rows_dropped": (
                pre_align_shape[0] - post_align_shape[0]
            ),
            "tickers_with_data": len(aligned_tickers),
            "tickers_requested": len(tickers),
            "date_range": {
                "start": dates[0] if dates else None,
                "end": dates[-1] if dates else None,
            },
        }

        return CompareOverlayResult(
            tickers=aligned_tickers,
            dates=dates,
            series=series,
            stats=stats,
            correlation_matrix=corr_dict,
            alignment=alignment,
        )

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------

    @staticmethod
    def _normalized(
        df: Any, tickers: List[str],
    ) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
        """Rebased to 100 at first aligned date."""
        series: Dict[str, List[float]] = {}
        stats: Dict[str, Dict[str, float]] = {}

        for sym in tickers:
            prices = df[sym].values
            base = prices[0] if prices[0] != 0 else 1
            norm = (prices / base * 100).tolist()
            series[sym] = [round(v, 2) for v in norm]

            total_ret = (prices[-1] / base - 1) * 100
            rets = np.diff(prices) / prices[:-1]
            vol = float(np.std(rets) * math.sqrt(252)) * 100
            sharpe = (
                (float(np.mean(rets)) * 252 - 0.045)
                / (float(np.std(rets)) * math.sqrt(252))
                if np.std(rets) > 0 else 0
            )
            cum = np.cumprod(1 + rets)
            peak = np.maximum.accumulate(cum)
            max_dd = float(np.min((cum - peak) / peak)) * 100

            stats[sym] = {
                "total_return": round(total_ret, 2),
                "annualized_vol": round(vol, 2),
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
            }

        return series, stats

    @staticmethod
    def _relative_strength(
        df: Any,
        tickers: List[str],
        benchmark: str,
    ) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
        """Ratio of ticker / benchmark price (rebased)."""
        series: Dict[str, List[float]] = {}
        stats: Dict[str, Dict[str, float]] = {}

        bm_col = benchmark if benchmark in df.columns else tickers[0]
        bm = df[bm_col].values
        bm_base = bm[0] if bm[0] != 0 else 1

        for sym in tickers:
            prices = df[sym].values
            base = prices[0] if prices[0] != 0 else 1
            # Relative strength = (price/base) / (benchmark/bm_base)
            ratio = (prices / base) / (bm / bm_base)
            series[sym] = [round(float(v), 4) for v in ratio]

            # Stats
            current_rs = float(ratio[-1])
            rs_change = (current_rs / ratio[0] - 1) * 100
            stats[sym] = {
                "current_rs": round(current_rs, 4),
                "rs_change_pct": round(rs_change, 2),
                "outperforming": current_rs > 1.0,
            }

        return series, stats

    @staticmethod
    def _rolling_corr(
        df: Any,
        tickers: List[str],
        window: int,
    ) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
        """Pairwise rolling correlation (first ticker as base)."""
        rets = df[tickers].pct_change().dropna()
        base_ticker = tickers[0]
        series: Dict[str, List[float]] = {}
        stats: Dict[str, Dict[str, float]] = {}

        for sym in tickers[1:]:
            rc = rets[base_ticker].rolling(window).corr(rets[sym])
            vals = rc.dropna().tolist()
            series[f"{base_ticker}_vs_{sym}"] = [
                round(float(v), 3) for v in vals
            ]
            stats[f"{base_ticker}_vs_{sym}"] = {
                "current_corr": round(float(vals[-1]), 3) if vals else 0,
                "mean_corr": round(float(np.mean(vals)), 3) if vals else 0,
                "min_corr": round(float(np.min(vals)), 3) if vals else 0,
                "max_corr": round(float(np.max(vals)), 3) if vals else 0,
            }

        return series, stats

    @staticmethod
    def _rolling_beta(
        df: Any,
        tickers: List[str],
        benchmark: str,
        window: int,
    ) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
        """Rolling OLS beta to benchmark."""
        rets = df[tickers].pct_change().dropna()
        bm_col = benchmark if benchmark in rets.columns else tickers[0]
        series: Dict[str, List[float]] = {}
        stats: Dict[str, Dict[str, float]] = {}

        bm_rets = rets[bm_col].values

        for sym in tickers:
            if sym == bm_col:
                continue
            sym_rets = rets[sym].values
            betas: List[float] = []
            for i in range(window, len(sym_rets)):
                x = bm_rets[i - window:i]
                y = sym_rets[i - window:i]
                cov = np.cov(x, y)[0, 1]
                var = np.var(x)
                beta = cov / var if var > 0 else 1.0
                betas.append(round(float(beta), 3))

            series[f"{sym}_beta"] = betas
            stats[f"{sym}_beta"] = {
                "current_beta": betas[-1] if betas else 1.0,
                "mean_beta": (
                    round(float(np.mean(betas)), 3) if betas else 1.0
                ),
                "min_beta": (
                    round(float(np.min(betas)), 3) if betas else 1.0
                ),
                "max_beta": (
                    round(float(np.max(betas)), 3) if betas else 1.0
                ),
            }

        return series, stats
