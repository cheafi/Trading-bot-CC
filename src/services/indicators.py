"""
Technical Indicator Library — causal (right-aligned), no look-ahead bias.

Extracted from src/api/main.py. All functions operate on numpy arrays.
Every result[i] depends only on arr[0..i] — never on future bars.

Quant principle (Berlekamp): "We need a smaller edge on each trade."
These indicators give that edge only when used correctly:
  - Always right-aligned (causal)
  - ATR-normalised to make signals comparable across price levels
  - RS computed vs benchmark, not in isolation

Strategies inspired by je-suis-tm/quant-trading:
  - MACD: momentum convergence/divergence
  - Bollinger Bands: volatility contraction → expansion breakout
  - RSI: overbought/oversold + pattern recognition
  - Parabolic SAR: trend reversal identification
  - Dual Thrust: opening range breakout levels
  - Heikin-Ashi: noise-filtered momentum candles
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# CORE ROLLING PRIMITIVES
# ═══════════════════════════════════════════════════════════════════

def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """Causal (right-aligned) simple moving average.

    result[i] = mean(arr[i-window+1 .. i]).
    First (window-1) bars use expanding mean (partial window).
    No look-ahead bias — safe for backtesting.
    """
    n = len(arr)
    window = min(window, n)
    out = np.empty(n, dtype=float)
    cumsum = np.cumsum(arr)
    out[:window] = cumsum[:window] / np.arange(1, window + 1)
    if window < n:
        out[window:] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling standard deviation (population, ddof=0)."""
    n = len(arr)
    window = min(window, n)
    out = np.empty(n, dtype=float)
    for i in range(n):
        w = min(i + 1, window)
        out[i] = np.std(arr[max(0, i - w + 1): i + 1])
    return out


def ema(arr: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average with Wilder smoothing (alpha = 1/period).

    Used by RSI, ATR (Wilder), ADX.
    """
    alpha = 1.0 / period
    out = np.empty(len(arr), dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


# ═══════════════════════════════════════════════════════════════════
# STANDARD INDICATOR SUITE
# ═══════════════════════════════════════════════════════════════════

def compute_indicators(close: np.ndarray, volume: np.ndarray) -> Dict:
    """Compute standard indicator suite. All arrays length n, right-aligned.

    Returns: sma20, sma50, sma200, rsi14, vol_ratio, atr14, atr_pct,
             macd_line, macd_signal, macd_hist, bb_upper, bb_mid, bb_lower,
             bb_pct_b, bb_width, parabolic_sar (simplified), heikin_close.
    """
    n = len(close)
    sma20  = rolling_mean(close, 20)
    sma50  = rolling_mean(close, 50)
    sma200 = rolling_mean(close, min(200, n))

    # RSI-14 (Wilder smoothed)
    deltas   = np.diff(close, prepend=close[0])
    gains    = np.where(deltas > 0, deltas, 0.0)
    losses   = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = ema(gains, 14)
    avg_loss = ema(losses, 14)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
    rsi14 = 100.0 - (100.0 / (1.0 + rs))

    # Volume ratio
    vol_float = volume.astype(float)
    vol_ma    = rolling_mean(vol_float, 20)
    vol_ratio = np.where(vol_ma > 0, vol_float / vol_ma, 1.0)

    # ATR-14 (close-to-close proxy)
    true_range = np.abs(np.diff(close, prepend=close[0]))
    atr14      = rolling_mean(true_range, 14)
    atr_pct    = np.where(close > 0, atr14 / close, 0.02)

    # MACD (12, 26, 9) — je-suis-tm strategy #1
    # Short EMA minus Long EMA = momentum divergence
    ema12       = _ema_fast(close, 12)
    ema26       = _ema_fast(close, 26)
    macd_line   = ema12 - ema26
    macd_signal = _ema_fast(macd_line, 9)
    macd_hist   = macd_line - macd_signal

    # Bollinger Bands (20, 2σ) — je-suis-tm strategy #9
    bb_mid   = sma20
    bb_std   = rolling_std(close, 20)
    bb_upper = bb_mid + 2.0 * bb_std
    bb_lower = bb_mid - 2.0 * bb_std
    bb_range = bb_upper - bb_lower
    # %B: 0=at lower band, 0.5=mid, 1.0=at upper band
    bb_pct_b = np.where(bb_range > 0, (close - bb_lower) / bb_range, 0.5)
    # Band width normalised by mid: contraction signal
    bb_width = np.where(bb_mid > 0, bb_range / bb_mid, 0.0)

    # Heikin-Ashi close (smoothed candle noise filter) — je-suis-tm #3
    # HA_close = (O + H + L + C) / 4 — approximate with close only
    # Full HA needs OHLC; here we use (prev_close + close) / 2 as proxy
    ha_close = np.empty(n, dtype=float)
    ha_close[0] = close[0]
    for i in range(1, n):
        ha_close[i] = (close[i - 1] + close[i]) / 2.0

    return {
        "sma20":        sma20,
        "sma50":        sma50,
        "sma200":       sma200,
        "rsi14":        rsi14,
        "vol_ratio":    vol_ratio,
        "atr14":        atr14,
        "atr_pct":      atr_pct,
        "macd_line":    macd_line,
        "macd_signal":  macd_signal,
        "macd_hist":    macd_hist,
        "bb_upper":     bb_upper,
        "bb_mid":       bb_mid,
        "bb_lower":     bb_lower,
        "bb_pct_b":     bb_pct_b,
        "bb_width":     bb_width,
        "ha_close":     ha_close,
    }


def _ema_fast(arr: np.ndarray, period: int) -> np.ndarray:
    """Standard EMA (alpha = 2 / (period + 1)), causal."""
    alpha = 2.0 / (period + 1)
    out = np.empty(len(arr), dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


# ═══════════════════════════════════════════════════════════════════
# DUAL THRUST LEVELS (je-suis-tm strategy #7)
# ═══════════════════════════════════════════════════════════════════

def dual_thrust_levels(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
    k1: float = 0.5,
    k2: float = 0.5,
    lookback: int = 4,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute Dual Thrust upper/lower breakout levels.

    Upper = Open + k1 * Range
    Lower = Open - k2 * Range
    Range = max(HH-LC, HC-LL) over lookback days.

    Args:
        k1, k2: thrust multipliers (typically 0.5)
        lookback: days used to compute range (typically 4)

    Returns: (upper_levels, lower_levels) arrays of same length as input.
    """
    n = len(close)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    for i in range(lookback, n):
        hh = np.max(high[i - lookback: i])
        lc = np.min(close[i - lookback: i])
        hc = np.max(close[i - lookback: i])
        ll = np.min(low[i - lookback: i])
        rng = max(hh - lc, hc - ll)
        upper[i] = open_[i] + k1 * rng
        lower[i] = open_[i] - k2 * rng

    return upper, lower


# ═══════════════════════════════════════════════════════════════════
# RELATIVE STRENGTH vs BENCHMARK (Mansfield RS)
# ═══════════════════════════════════════════════════════════════════

def compute_rs_vs_benchmark(
    stock_close: np.ndarray,
    bench_close: np.ndarray,
) -> Dict:
    """Mansfield-style RS: stock return / benchmark return.

    RS = 100 means in-line with benchmark.
    RS > 120 = LEADER, RS < 80 = LAGGARD.

    Windows: 1M (21d), 3M (63d), 6M (126d).
    Composite: 0.25 * rs_1m + 0.40 * rs_3m + 0.35 * rs_6m
      (3M weighted highest — balances signal quality vs recency).

    RS slope: current rs_1m minus rs_1m from 21 days ago
      (positive slope = gaining vs SPY).
    """
    n = min(len(stock_close), len(bench_close))
    if n < 22:
        return {
            "rs_composite": 100.0,
            "rs_1m": 100.0,
            "rs_3m": 100.0,
            "rs_6m": 100.0,
            "rs_slope": 0.0,
            "rs_status": "NEUTRAL",
        }

    def _pct(arr, lb):
        if n < lb + 1:
            return 0.0
        return (arr[-1] / arr[-1 - lb] - 1.0) * 100.0

    def _rs(s_ret, b_ret):
        if b_ret == 0:
            return 100.0 + s_ret * 10.0
        return max(0.0, min(300.0, (1.0 + s_ret / 100.0) / (1.0 + b_ret / 100.0) * 100.0))

    s, b = stock_close[-n:], bench_close[-n:]
    rs_1m = _rs(_pct(s, 21), _pct(b, 21))
    rs_3m = _rs(_pct(s, 63), _pct(b, 63)) if n >= 64 else rs_1m
    rs_6m = _rs(_pct(s, 126), _pct(b, 126)) if n >= 127 else rs_3m

    composite = 0.25 * rs_1m + 0.40 * rs_3m + 0.35 * rs_6m

    rs_slope = 0.0
    if n >= 43:
        old_s = (s[-22] / s[-43] - 1.0) * 100.0 if n >= 43 else 0.0
        old_b = (b[-22] / b[-43] - 1.0) * 100.0 if n >= 43 else 0.0
        old_rs = _rs(old_s, old_b)
        rs_slope = round(rs_1m - old_rs, 1)

    if composite >= 120:
        status = "LEADER"
    elif composite >= 105:
        status = "STRONG"
    elif composite >= 95:
        status = "NEUTRAL"
    elif composite >= 80:
        status = "WEAK"
    else:
        status = "LAGGARD"

    return {
        "rs_composite": round(composite, 1),
        "rs_1m":        round(rs_1m, 1),
        "rs_3m":        round(rs_3m, 1),
        "rs_6m":        round(rs_6m, 1),
        "rs_slope":     rs_slope,
        "rs_status":    status,
    }


# ═══════════════════════════════════════════════════════════════════
# SIGNAL QUALITY FEATURES (scalar, from latest bar)
# ═══════════════════════════════════════════════════════════════════

def signal_quality_features(
    close: np.ndarray,
    volume: np.ndarray,
    indics: Optional[Dict] = None,
) -> Dict:
    """Extract scalar quality features from the latest bar.

    Used by OpportunityEnsembler to enrich scoring.
    If indics dict already computed, pass it in to avoid recompute.
    """
    if indics is None:
        indics = compute_indicators(close, volume)

    rsi = float(indics["rsi14"][-1])
    macd_hist = float(indics["macd_hist"][-1])
    bb_pct_b = float(indics["bb_pct_b"][-1])
    bb_width = float(indics["bb_width"][-1])
    vol_ratio = float(indics["vol_ratio"][-1])
    atr_pct = float(indics["atr_pct"][-1])

    # MACD momentum: True = bullish (hist > 0), False = bearish/flat
    macd_momentum: bool = macd_hist > 0

    # Bollinger Band position — je-suis-tm #9
    # 0-0.2: near lower band (potential mean-reversion buy)
    # 0.8-1.0: near upper band (momentum breakout or overbought)
    bb_signal = "LOWER_BAND" if bb_pct_b < 0.2 else "UPPER_BAND" if bb_pct_b > 0.8 else "MID_BAND"

    # BB contraction: low width = coiling energy → expect expansion
    # Threshold: width < 5% of price = tight coil
    bb_contracted = bb_width < 0.05

    # RSI regime (je-suis-tm #10)
    rsi_regime = (
        "OVERSOLD"   if rsi < 30 else
        "RECOVERING" if rsi < 45 else
        "NEUTRAL"    if rsi < 55 else
        "MOMENTUM"   if rsi < 70 else
        "OVERBOUGHT"
    )

    # Volume surge: >2x average = institutional interest
    vol_surge = vol_ratio >= 2.0

    return {
        "rsi":           round(rsi, 1),
        "rsi_regime":    rsi_regime,
        "macd_momentum": macd_momentum,
        "bb_pct_b":      round(bb_pct_b, 3),
        "bb_signal":     bb_signal,
        "bb_contracted": bb_contracted,
        "bb_width":      round(bb_width, 4),
        "vol_ratio":     round(vol_ratio, 2),
        "vol_surge":     vol_surge,
        "atr_pct":       round(atr_pct, 4),
    }
