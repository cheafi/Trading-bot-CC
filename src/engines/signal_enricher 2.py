"""
Signal Enricher — The Missing Data Bridge.

Takes raw OHLCV from MarketDataIngestor and computes all derived
fields that the pipeline (FitScorer, SectorClassifier, ScannerMatrix)
expects but were never populated:

  RSI-14, ATR%, vol_ratio, distance_from_50ma_pct, bb_width,
  rs_rank (vs SPY), contraction_count (VCP), base_depth_pct,
  days_to_earnings (stub), plus full StructureDetector analysis.

Usage:
    enricher = SignalEnricher()
    enriched = enricher.enrich(ticker, ohlcv_df, spy_returns=spy_ret)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.engines.structure_detector import StructureDetector, StructureReport

logger = logging.getLogger(__name__)


class SignalEnricher:
    """Compute real technical fields from OHLCV data."""

    def __init__(self):
        self.detector = StructureDetector()

    def enrich(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        spy_returns: Optional[pd.Series] = None,
        existing_signal: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a signal dict with computed fields from real OHLCV.

        Parameters
        ----------
        ticker : str
        ohlcv : DataFrame with columns [open, high, low, close, volume]
        spy_returns : optional Series of SPY daily returns for RS calc
        existing_signal : optional pre-existing signal dict to merge into

        Returns
        -------
        Enriched signal dict with all computed fields.
        """
        sig: Dict[str, Any] = dict(existing_signal or {})
        sig["ticker"] = ticker

        if ohlcv is None or len(ohlcv) < 20:
            logger.warning(
                "Insufficient OHLCV data for %s (%d bars)",
                ticker,
                len(ohlcv) if ohlcv is not None else 0,
            )
            return sig

        # Normalize column names to lowercase
        ohlcv = ohlcv.copy()
        ohlcv.columns = [c.lower() for c in ohlcv.columns]

        close = ohlcv["close"].values.astype(float)
        high = ohlcv["high"].values.astype(float)
        low = ohlcv["low"].values.astype(float)
        volume = ohlcv["volume"].values.astype(float)

        # ── 1. RSI-14 ──
        sig["rsi"] = self._rsi(close, 14)

        # ── 2. ATR% (14-period ATR / close, as percentage) ──
        sig["atr_pct"] = self._atr_pct(close, high, low, 14)

        # ── 3. Volume ratio (today vs 20-day avg) ──
        sig["vol_ratio"] = self._vol_ratio(volume)

        # ── 4. Distance from 50-day MA (%) ──
        sig["distance_from_50ma_pct"] = self._distance_from_ma(close, 50)

        # ── 5. Bollinger Band width ──
        sig["bb_width"] = self._bb_width(close, 20)

        # ── 6. Relative strength rank vs SPY (0-100) ──
        sig["rs_rank"] = self._rs_rank(close, spy_returns)

        # ── 7. VCP contraction count ──
        sig["contraction_count"] = self._contraction_count(high, low)

        # ── 8. Base depth % (max drawdown from high in last 60 bars) ──
        sig["base_depth_pct"] = self._base_depth(close)

        # ── 9. Risk/reward if we have nearby S/R from structure ──
        # (computed after StructureDetector)

        # ── 10. StructureDetector full analysis ──
        try:
            structure: StructureReport = self.detector.analyze(close, high, low, volume)
            sig["_structure"] = structure
            sig["_structure_dict"] = structure.to_dict()

            # Merge key structure fields into signal for downstream
            sig["trend_structure"] = structure.trend.value
            sig["trend_quality"] = structure.trend_quality
            sig["breakout_quality"] = (
                structure.breakout_quality.value if structure.breakout_quality else None
            )
            sig["is_extended"] = structure.is_extended
            sig["extension_pct"] = structure.extension_pct
            sig["is_at_resistance"] = structure.is_at_resistance
            sig["is_near_support"] = structure.is_near_support
            sig["volume_confirms"] = structure.volume_confirms
            sig["volume_exhaustion"] = structure.volume_exhaustion
            sig["liquidity_trap_risk"] = structure.liquidity_trap_risk
            sig["nearest_support"] = structure.nearest_support
            sig["nearest_resistance"] = structure.nearest_resistance

            # Compute R:R from structure S/R levels
            price = float(close[-1])
            if structure.nearest_support and structure.nearest_resistance:
                risk = price - structure.nearest_support
                reward = structure.nearest_resistance - price
                if risk > 0:
                    sig["risk_reward"] = round(reward / risk, 2)

        except Exception as e:
            logger.warning("StructureDetector failed for %s: %s", ticker, e)
            sig["_structure"] = None
            sig["_structure_dict"] = {}

        return sig

    # ── Technical Indicators ─────────────────────────────────────

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> float:
        """Wilder's RSI."""
        if len(close) < period + 1:
            return 50.0
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - 100.0 / (1.0 + rs), 1)

    @staticmethod
    def _atr_pct(
        close: np.ndarray, high: np.ndarray, low: np.ndarray, period: int = 14
    ) -> float:
        """ATR as percentage of current price."""
        if len(close) < period + 1:
            return 2.0
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        atr = np.mean(tr[-period:])
        return round(atr / close[-1] * 100, 2) if close[-1] > 0 else 2.0

    @staticmethod
    def _vol_ratio(volume: np.ndarray, period: int = 20) -> float:
        """Latest volume / 20-day average volume."""
        if len(volume) < period:
            return 1.0
        avg = np.mean(volume[-period:])
        if avg == 0:
            return 1.0
        return round(float(volume[-1] / avg), 2)

    @staticmethod
    def _distance_from_ma(close: np.ndarray, period: int = 50) -> float:
        """Distance from N-period MA as percentage."""
        if len(close) < period:
            return 0.0
        ma = np.mean(close[-period:])
        if ma == 0:
            return 0.0
        return round((close[-1] - ma) / ma * 100, 2)

    @staticmethod
    def _bb_width(close: np.ndarray, period: int = 20) -> float:
        """Bollinger Band width: (upper - lower) / middle."""
        if len(close) < period:
            return 0.0
        ma = np.mean(close[-period:])
        std = np.std(close[-period:])
        if ma == 0:
            return 0.0
        upper = ma + 2 * std
        lower = ma - 2 * std
        return round((upper - lower) / ma * 100, 2)

    @staticmethod
    def _rs_rank(
        close: np.ndarray,
        spy_returns: Optional[pd.Series] = None,
        lookback: int = 63,
    ) -> float:
        """
        Relative strength vs SPY over ~3 months.

        Returns 0-100 percentile. Without SPY data, uses absolute
        momentum as a proxy.
        """
        if len(close) < lookback:
            return 50.0

        stock_ret = (close[-1] / close[-lookback] - 1) * 100

        if spy_returns is not None and len(spy_returns) >= lookback:
            spy_cum = float((1 + spy_returns.iloc[-lookback:]).prod() - 1) * 100
            excess = stock_ret - spy_cum
            # Map excess return to 0-100 scale
            # +20% excess → 95, 0% → 50, -20% → 5
            return round(max(0, min(100, 50 + excess * 2.25)), 1)

        # Fallback: absolute momentum → rough percentile
        return round(max(0, min(100, 50 + stock_ret * 1.5)), 1)

    @staticmethod
    def _contraction_count(high: np.ndarray, low: np.ndarray) -> int:
        """
        Count VCP-like contractions in the last 60 bars.

        A contraction = range shrinks by >30% from prior range.
        """
        if len(high) < 20:
            return 0

        lookback = min(60, len(high))
        window = 10
        contractions = 0
        prev_range = 0.0

        for i in range(0, lookback - window, window):
            start = len(high) - lookback + i
            end = start + window
            h = float(np.max(high[start:end]))
            l = float(np.min(low[start:end]))
            curr_range = h - l

            if prev_range > 0 and curr_range < prev_range * 0.7:
                contractions += 1
            prev_range = curr_range

        return contractions

    @staticmethod
    def _base_depth(close: np.ndarray, lookback: int = 60) -> float:
        """Max drawdown from peak in last N bars (as %)."""
        if len(close) < lookback:
            lookback = len(close)
        window = close[-lookback:]
        peak = np.max(window)
        if peak == 0:
            return 0.0
        trough = np.min(window)
        return round((peak - trough) / peak * 100, 1)
