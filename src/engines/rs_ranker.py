"""
RS Ranker — Universe-Level Relative Strength Ranking.

Ranks all tickers in a universe by their price performance
vs SPY over multiple timeframes, returning a 0-100 percentile.

Usage:
    ranker = RSRanker()
    ranks = ranker.rank_universe(returns_dict)
    # ranks = {"NVDA": 95.2, "AAPL": 72.1, "XOM": 45.0, ...}
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class RSRanker:
    """Rank tickers by relative strength percentile."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ):
        # Multi-timeframe weights (63d=3mo, 126d=6mo, 21d=1mo)
        self.weights = weights or {
            "21d": 0.25,
            "63d": 0.50,
            "126d": 0.25,
        }

    def rank_universe(
        self,
        universe_returns: Dict[str, Dict[str, float]],
        spy_returns: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Rank all tickers by relative strength.

        Parameters
        ----------
        universe_returns : {ticker: {"21d": ret, "63d": ret, "126d": ret}}
        spy_returns : {"21d": ret, "63d": ret, "126d": ret} (optional)

        Returns
        -------
        {ticker: percentile_rank (0-100)}
        """
        if not universe_returns:
            return {}

        spy = spy_returns or {}

        # Compute composite RS score per ticker
        composite: Dict[str, float] = {}
        for ticker, rets in universe_returns.items():
            score = 0.0
            for period, weight in self.weights.items():
                stock_ret = rets.get(period, 0.0)
                spy_ret = spy.get(period, 0.0)
                excess = stock_ret - spy_ret
                score += excess * weight
            composite[ticker] = score

        # Convert to percentile ranks (0-100)
        if len(composite) <= 1:
            return {t: 50.0 for t in composite}

        scores = np.array(list(composite.values()))
        ranks: Dict[str, float] = {}
        for ticker, score in composite.items():
            # Percentile: what % of universe is this score above
            pct = float(np.sum(scores <= score) / len(scores) * 100)
            ranks[ticker] = round(pct, 1)

        return ranks

    def rank_from_closes(
        self,
        universe_closes: Dict[str, List[float]],
        spy_close: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """
        Convenience: rank from raw close price arrays.

        Parameters
        ----------
        universe_closes : {ticker: [close_0, close_1, ..., close_n]}
            Must be sorted chronologically (oldest first).
        spy_close : [close_0, ..., close_n] (optional)
        """
        universe_returns: Dict[str, Dict[str, float]] = {}

        for ticker, closes in universe_closes.items():
            if len(closes) < 22:
                continue
            arr = np.array(closes, dtype=float)
            rets: Dict[str, float] = {}
            for label, period in [("21d", 21), ("63d", 63), ("126d", 126)]:
                if len(arr) >= period + 1:
                    rets[label] = float((arr[-1] / arr[-period - 1] - 1) * 100)
                else:
                    rets[label] = float((arr[-1] / arr[0] - 1) * 100)
            universe_returns[ticker] = rets

        spy_rets: Optional[Dict[str, float]] = None
        if spy_close and len(spy_close) >= 22:
            spy_arr = np.array(spy_close, dtype=float)
            spy_rets = {}
            for label, period in [("21d", 21), ("63d", 63), ("126d", 126)]:
                if len(spy_arr) >= period + 1:
                    spy_rets[label] = float(
                        (spy_arr[-1] / spy_arr[-period - 1] - 1) * 100
                    )

        return self.rank_universe(universe_returns, spy_rets)
