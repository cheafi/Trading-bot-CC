"""Chart and candlestick pattern recognition."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def detect_patterns(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
) -> List[Dict[str, Any]]:
    """Detect common chart patterns in OHLCV data.

    Returns list of detected patterns with confidence scores.
    """
    patterns: List[Dict[str, Any]] = []
    n = len(close)
    if n < 20:
        return patterns

    # Double bottom
    if n >= 50:
        mid = n // 2
        left_min = np.min(low[:mid])
        right_min = np.min(low[mid:])
        if abs(left_min - right_min) / left_min < 0.03:
            neckline = np.max(high[mid - 10:mid + 10])
            if close[-1] > neckline:
                patterns.append({
                    "pattern": "double_bottom",
                    "confidence": 0.7,
                    "direction": "bullish",
                    "support": round(float(min(left_min, right_min)), 2),
                    "neckline": round(float(neckline), 2),
                })

    # Higher highs + higher lows (uptrend)
    if n >= 30:
        recent_highs = high[-20:]
        recent_lows = low[-20:]
        h1, h2 = np.max(recent_highs[:10]), np.max(recent_highs[10:])
        l1, l2 = np.min(recent_lows[:10]), np.min(recent_lows[10:])
        if h2 > h1 and l2 > l1:
            patterns.append({
                "pattern": "uptrend",
                "confidence": 0.65,
                "direction": "bullish",
                "higher_high": round(float(h2), 2),
                "higher_low": round(float(l2), 2),
            })
        elif h2 < h1 and l2 < l1:
            patterns.append({
                "pattern": "downtrend",
                "confidence": 0.65,
                "direction": "bearish",
                "lower_high": round(float(h2), 2),
                "lower_low": round(float(l2), 2),
            })

    # Volume climax
    avg_vol = np.mean(volume[-20:])
    if volume[-1] > avg_vol * 3:
        patterns.append({
            "pattern": "volume_climax",
            "confidence": 0.6,
            "direction": "neutral",
            "volume_ratio": round(float(volume[-1] / avg_vol), 1),
        })

    return patterns
