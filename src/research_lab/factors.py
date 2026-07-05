"""Factor models — momentum, value, quality, volatility."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def momentum_score(returns: np.ndarray, lookback: int = 252) -> float:
    """12-month momentum factor score (skip last month)."""
    if len(returns) < lookback:
        return 0.0
    # 12-1 momentum: total return over 12m, skip last 1m
    r = returns[-lookback:-21] if len(returns) > lookback else returns[:-21]
    return float(np.prod(1 + r) - 1)


def mean_reversion_score(
    returns: np.ndarray, lookback: int = 20,
) -> float:
    """Short-term mean reversion z-score."""
    if len(returns) < lookback:
        return 0.0
    recent = returns[-lookback:]
    return float(
        -(np.sum(recent)) / (np.std(recent) * math.sqrt(lookback) + 1e-8)
    )


def quality_score(
    roe: float, debt_equity: float, margin: float,
) -> float:
    """Simple quality composite: high ROE, low D/E, high margin."""
    s = 0.0
    s += min(1.0, roe / 0.20) * 0.4        # 20% ROE = full score
    s += max(0, 1 - debt_equity / 2) * 0.3  # D/E < 2 = full score
    s += min(1.0, margin / 0.15) * 0.3      # 15% margin = full
    return round(s, 3)


def volatility_factor(
    returns: np.ndarray, window: int = 60,
) -> float:
    """Low-volatility factor — inverse realized vol."""
    if len(returns) < window:
        return 0.0
    vol = float(np.std(returns[-window:]) * math.sqrt(252))
    return round(1.0 / max(vol, 0.01), 3)
