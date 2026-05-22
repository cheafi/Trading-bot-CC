"""
Shared liquidity-aware slippage estimator.

Lifted from ``src/backtest/enhanced_backtester.py`` so the live order
router and the backtester use identical math. This is the only way
paper-vs-live performance numbers are comparable; running different
slippage assumptions in research and production is the most common
source of "it worked in backtest" disappointment.

Formula
-------
    slippage_bps = base + k_vol * (1 / rel_vol) + k_spread * atr_pct
    if near_earnings: slippage_bps += earnings_gap_extra_bps
    slippage_bps = min(slippage_bps, cap_bps)

Usage
-----
Backtester: pass per-day OHLCV history slice.
Live router: pass a recent ~30 day window of daily bars + today's
realized volume snapshot. Returns bps (fraction = bps / 10_000).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class SlippageConfig:
    base_bps: float = 2.0
    k_volume: float = 5.0
    k_spread: float = 0.3
    cap_bps: float = 50.0
    earnings_gap_extra_bps: float = 30.0


def estimate_slippage_bps(
    price: float,
    bars: Optional[pd.DataFrame],
    near_earnings: bool = False,
    config: Optional[SlippageConfig] = None,
) -> float:
    """
    Estimate expected execution slippage in basis points.

    Parameters
    ----------
    price : float
        Reference price (last/mid). Used to convert ATR to ATR%.
    bars : pd.DataFrame or None
        Recent OHLCV bars with columns: high, low, close, volume.
        At least 21 rows are required to compute relative volume +
        ATR; if insufficient or None, falls back to base bps only.
    near_earnings : bool
        Whether the symbol has an earnings event within ~2 days.
    config : SlippageConfig
        Model coefficients. Defaults to the backtester-calibrated set.

    Returns
    -------
    float
        Slippage in basis points (e.g. 12.5 means 12.5 bps).
    """
    cfg = config or SlippageConfig()
    bps = cfg.base_bps

    if bars is not None and len(bars) >= 21 and price > 0:
        window = bars.tail(21)
        try:
            avg_vol = window["volume"].iloc[:-1].mean()
            today_vol = window["volume"].iloc[-1]
            rel_vol = today_vol / avg_vol if avg_vol > 0 else 1.0
            bps += cfg.k_volume * (1.0 / max(rel_vol, 0.1))

            highs = window["high"]
            lows = window["low"]
            closes = window["close"]
            tr = pd.concat(
                [
                    highs - lows,
                    (highs - closes.shift()).abs(),
                    (lows - closes.shift()).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr = tr.tail(14).mean()
            atr_pct = (atr / price) * 100 if price > 0 else 0.0
            bps += cfg.k_spread * float(atr_pct)
        except (KeyError, ValueError, TypeError):
            pass

    if near_earnings:
        bps += cfg.earnings_gap_extra_bps

    return float(min(bps, cfg.cap_bps))


def slippage_bps_to_fraction(bps: float) -> float:
    """Convert bps to a price-fraction (e.g. 10 bps -> 0.001)."""
    return float(bps) / 10_000.0
