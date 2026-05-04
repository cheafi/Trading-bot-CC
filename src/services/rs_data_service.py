"""
RSDataService — Sprint 73 (debt reduction)
============================================
Wraps yfinance with:
  - Batch download (single call for multiple tickers)
  - Date-aligned merging (merge on date index, not array position)
  - In-process cache with TTL
  - Proper error handling

Routers MUST use this service instead of calling yfinance directly.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_CLOSES_CACHE: Dict[str, tuple[float, Any]] = {}  # ticker → (ts, DataFrame)
_CACHE_TTL = 300  # 5 min


def fetch_closes_batch(
    tickers: List[str],
    period: str = "6mo",
    interval: str = "1d",
) -> Dict[str, Any]:
    """
    Fetch close prices for multiple tickers in a single yfinance call.
    Returns {ticker: pd.Series} with date-indexed close prices.
    Cached per-ticker for 5 minutes.
    """
    now = time.time()

    # Split into cached vs needed
    result: Dict[str, Any] = {}
    needed: List[str] = []

    for t in tickers:
        cached = _CLOSES_CACHE.get(t)
        if cached and (now - cached[0]) < _CACHE_TTL:
            result[t] = cached[1]
        else:
            needed.append(t)

    if needed:
        try:
            import yfinance as yf
            # Batch download — single HTTP call for all tickers
            batch_str = " ".join(needed)
            data = yf.download(
                batch_str, period=period, interval=interval,
                progress=False, group_by="ticker", threads=True,
            )

            if data is not None and len(data) > 0:
                if len(needed) == 1:
                    # Single ticker: yf.download returns flat columns
                    t = needed[0]
                    col = "Close" if "Close" in data.columns else "close"
                    if col in data.columns:
                        series = data[col].dropna()
                        _CLOSES_CACHE[t] = (now, series)
                        result[t] = series
                else:
                    # Multiple tickers: grouped by ticker
                    for t in needed:
                        try:
                            if t in data.columns.get_level_values(0):
                                sub = data[t]
                                col = "Close" if "Close" in sub.columns else "close"
                                if col in sub.columns:
                                    series = sub[col].dropna()
                                    if len(series) >= 22:
                                        _CLOSES_CACHE[t] = (now, series)
                                        result[t] = series
                        except Exception:
                            logger.debug("[RSData] skip %s from batch", t)

        except Exception as e:
            logger.warning("[RSData] batch download failed: %s", e)

    return result


def fetch_single(ticker: str, period: str = "6mo") -> Optional[Any]:
    """Fetch closes for a single ticker. Returns pd.Series or None."""
    res = fetch_closes_batch([ticker], period=period)
    return res.get(ticker)


def compute_rs_date_aligned(
    ticker_closes: Any,
    benchmark_closes: Any,
) -> Dict[str, float]:
    """
    Compute RS vs benchmark with proper date alignment.
    Both inputs must be pd.Series with DatetimeIndex.
    Merges on date, not array position — handles IPOs, missing days, etc.
    """
    import pandas as pd
    from src.services.indicators import compute_rs_vs_benchmark

    # Align on date index — inner join keeps only common dates
    merged = pd.concat(
        [ticker_closes.rename("ticker"), benchmark_closes.rename("bench")],
        axis=1, join="inner",
    ).dropna()

    if len(merged) < 22:
        return {
            "rs_composite": 100.0, "rs_1m": 100.0, "rs_3m": 100.0,
            "rs_6m": 100.0, "rs_slope": 0.0, "rs_status": "NEUTRAL",
        }

    return compute_rs_vs_benchmark(
        np.array(merged["ticker"].values, dtype=float),
        np.array(merged["bench"].values, dtype=float),
    )


def clear_cache() -> None:
    """Clear all cached data."""
    _CLOSES_CACHE.clear()
