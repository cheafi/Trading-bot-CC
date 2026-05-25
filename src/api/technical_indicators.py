"""Causal technical indicators shared by API routes."""

from __future__ import annotations

import numpy as np


def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """Right-aligned simple moving average (no look-ahead)."""
    n = len(arr)
    window = min(window, n)
    out = np.empty(n, dtype=float)
    cumsum = np.cumsum(arr)
    out[:window] = cumsum[:window] / np.arange(1, window + 1)
    if window < n:
        out[window:] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def compute_indicators(close: np.ndarray, volume: np.ndarray) -> dict:
    """Standard indicator suite: SMA, RSI, volume ratio, ATR."""
    n = len(close)
    sma20 = rolling_mean(close, 20)
    sma50 = rolling_mean(close, 50)
    sma200 = rolling_mean(close, min(200, n))

    deltas = np.diff(close, prepend=close[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = rolling_mean(gains, 14)
    avg_loss = rolling_mean(losses, 14)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    vol_float = volume.astype(float)
    vol_ma = rolling_mean(vol_float, 20)
    vol_ratio = np.where(vol_ma > 0, vol_float / vol_ma, 1.0)

    true_range = np.abs(np.diff(close, prepend=close[0]))
    atr = rolling_mean(true_range, 14)
    atr_pct = np.where(close > 0, atr / close, 0.02)

    return {
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "rsi": rsi,
        "vol_ratio": vol_ratio,
        "atr": atr,
        "atr_pct": atr_pct,
    }
