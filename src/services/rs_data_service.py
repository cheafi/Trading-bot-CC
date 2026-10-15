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
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from src.services.market_data import extract_close_series

logger = logging.getLogger(__name__)

from src.core.state_paths import yfinance_cache_dir

_YF_CACHE = str(yfinance_cache_dir())


def _configure_yfinance_cache() -> None:
    try:
        os.makedirs(_YF_CACHE, exist_ok=True)
        import yfinance as yf

        yf.set_tz_cache_location(_YF_CACHE)
    except Exception as exc:
        logger.debug("[RSData] yfinance cache setup skipped: %s", exc)


_configure_yfinance_cache()

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
                batch_str,
                period=period,
                interval=interval,
                progress=False,
                group_by="ticker",
                threads=True,
            )

            if data is not None and len(data) > 0:
                for t in needed:
                    try:
                        # Flat columns identify only a single requested ticker.
                        if len(needed) > 1 and data.columns.nlevels == 1:
                            continue
                        series = extract_close_series(data, t)
                        if series is not None and (
                            len(needed) == 1 or len(series) >= 22
                        ):
                            _CLOSES_CACHE[t] = (now, series)
                            result[t] = series
                    except Exception as exc:
                        logger.debug("[RSData] skip %s from batch: %s", t, exc)

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
        axis=1,
        join="inner",
    ).dropna()

    if len(merged) < 22:
        return {
            "rs_composite": 100.0,
            "rs_1m": 100.0,
            "rs_3m": 100.0,
            "rs_6m": 100.0,
            "rs_slope": 0.0,
            "rs_status": "NEUTRAL",
        }

    return compute_rs_vs_benchmark(
        np.array(merged["ticker"].values, dtype=float),
        np.array(merged["bench"].values, dtype=float),
    )


def clear_cache() -> None:
    """Clear all cached data."""
    _CLOSES_CACHE.clear()
