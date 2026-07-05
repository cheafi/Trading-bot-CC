"""Portfolio optimization utilities — extracted from strategy_portfolio_lab."""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np


def equal_weight(strategies: List[str]) -> Dict[str, float]:
    """1/N equal weight."""
    n = len(strategies)
    return {s: round(1.0 / n, 4) for s in strategies}


def inverse_vol_weight(
    returns_map: Dict[str, List[float]],
) -> Dict[str, float]:
    """Weight inversely proportional to realized volatility."""
    vols = {}
    for s, rets in returns_map.items():
        vols[s] = float(np.std(rets)) if len(rets) > 1 else 1.0

    inv = {s: 1.0 / max(v, 1e-8) for s, v in vols.items()}
    total = sum(inv.values())
    return {s: round(v / total, 4) for s, v in inv.items()}


def max_sharpe_weight(
    returns_map: Dict[str, List[float]],
    rf: float = 0.045,
    ann: float = 252,
) -> Dict[str, float]:
    """Analytical max-Sharpe weights via mean-variance."""
    strategies = list(returns_map.keys())
    n = len(strategies)
    min_len = min(len(v) for v in returns_map.values())

    R = np.array([
        returns_map[s][:min_len] for s in strategies
    ])

    means = R.mean(axis=1) * ann
    cov = np.cov(R) * ann

    try:
        excess = means - rf
        inv_cov = np.linalg.inv(cov)
        raw = inv_cov @ excess
        if raw.sum() <= 0:
            raw = np.ones(n)
        w = np.clip(raw / raw.sum(), 0, 1)
        w = w / w.sum()
    except np.linalg.LinAlgError:
        w = np.ones(n) / n

    return {s: round(float(w[i]), 4) for i, s in enumerate(strategies)}
