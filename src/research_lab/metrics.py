"""Risk and return metrics — Sharpe, Sortino, drawdown analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class DrawdownPeriod:
    """A single drawdown episode."""
    start_idx: int
    trough_idx: int
    recovery_idx: Optional[int]
    depth_pct: float
    duration_days: int


def sharpe_ratio(
    returns: np.ndarray, rf: float = 0.045, ann: float = 252,
) -> float:
    """Annualized Sharpe ratio."""
    if len(returns) < 2 or np.std(returns) == 0:
        return 0.0
    excess = np.mean(returns) * ann - rf
    vol = np.std(returns) * math.sqrt(ann)
    return round(float(excess / vol), 3)


def sortino_ratio(
    returns: np.ndarray, rf: float = 0.045, ann: float = 252,
) -> float:
    """Annualized Sortino ratio."""
    if len(returns) < 2:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) == 0:
        return 10.0
    ds_vol = float(np.std(downside) * math.sqrt(ann))
    if ds_vol == 0:
        return 10.0
    excess = np.mean(returns) * ann - rf
    return round(float(excess / ds_vol), 3)


def calmar_ratio(
    returns: np.ndarray, ann: float = 252,
) -> float:
    """Calmar ratio = annualized return / max drawdown."""
    dd = max_drawdown(returns)
    if dd == 0:
        return 0.0
    ann_ret = float(np.mean(returns) * ann)
    return round(abs(ann_ret / dd), 3)


def max_drawdown(returns: np.ndarray) -> float:
    """Maximum drawdown as a negative fraction."""
    if len(returns) < 2:
        return 0.0
    cum = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    return round(float(np.min(dd)), 4)


def analyze_drawdowns(
    returns: np.ndarray, top_n: int = 5,
) -> List[DrawdownPeriod]:
    """Find the top-N deepest drawdown periods."""
    if len(returns) < 2:
        return []

    cum = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak

    periods: List[DrawdownPeriod] = []
    in_dd = False
    start = 0
    trough = 0
    depth = 0.0

    for i in range(len(dd)):
        if dd[i] < -0.01 and not in_dd:
            in_dd = True
            start = i
            depth = dd[i]
            trough = i
        elif in_dd and dd[i] < depth:
            depth = dd[i]
            trough = i
        elif in_dd and dd[i] >= -0.005:
            periods.append(DrawdownPeriod(
                start_idx=start,
                trough_idx=trough,
                recovery_idx=i,
                depth_pct=round(float(depth) * 100, 2),
                duration_days=i - start,
            ))
            in_dd = False

    if in_dd:
        periods.append(DrawdownPeriod(
            start_idx=start,
            trough_idx=trough,
            recovery_idx=None,
            depth_pct=round(float(depth) * 100, 2),
            duration_days=len(dd) - start,
        ))

    periods.sort(key=lambda p: p.depth_pct)
    return periods[:top_n]


def var_cvar(
    returns: np.ndarray, level: float = 0.05,
) -> tuple:
    """Value-at-Risk and Conditional VaR at given level."""
    if len(returns) < 10:
        return (0.0, 0.0)
    var = float(np.percentile(returns, level * 100))
    tail = returns[returns <= var]
    cvar = float(np.mean(tail)) if len(tail) > 0 else var
    return (round(var, 4), round(cvar, 4))
