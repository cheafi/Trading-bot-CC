"""
Structure Detector — Chart Thinking Engine.

Detects price structure that indicators miss:
1. HH/HL vs LH/LL swing structure (trend quality)
2. Support / Resistance levels (from swing pivots)
3. Liquidity traps / stop hunts / fake breakouts
4. Volume exhaustion vs confirmation
5. Breakout quality assessment

This replaces indicator-only thinking with
price-action + structure-first analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────


class TrendStructure(str, Enum):
    STRONG_UPTREND = "strong_uptrend"  # HH + HL
    UPTREND = "uptrend"  # mostly HH/HL
    RANGE = "range"  # no clear direction
    DOWNTREND = "downtrend"  # mostly LH/LL
    STRONG_DOWNTREND = "strong_downtrend"  # LH + LL
    TRANSITION = "transition"  # mixed signals


class BreakoutQuality(str, Enum):
    GENUINE = "genuine"
    WEAK = "weak"
    FAKE = "fake"
    EXHAUSTION = "exhaustion"


# ── Data Classes ───────────────────────────────────────


@dataclass
class SwingPoint:
    """A detected swing high or swing low."""

    index: int
    price: float
    is_high: bool
    volume: float = 0.0
    strength: int = 1  # how many bars on each side


@dataclass
class SRLevel:
    """A support or resistance level."""

    price: float
    level_type: str  # "support" or "resistance"
    touches: int = 1  # how many times price touched
    strength: float = 0.0
    first_seen: int = 0  # bar index
    last_seen: int = 0


@dataclass
class StructureReport:
    """Full structure analysis output."""

    trend: TrendStructure = TrendStructure.RANGE
    trend_quality: float = 0.0  # 0-100
    swing_highs: List[SwingPoint] = field(
        default_factory=list,
    )
    swing_lows: List[SwingPoint] = field(
        default_factory=list,
    )
    support_levels: List[SRLevel] = field(
        default_factory=list,
    )
    resistance_levels: List[SRLevel] = field(
        default_factory=list,
    )
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    breakout_quality: Optional[BreakoutQuality] = None
    is_extended: bool = False
    extension_pct: float = 0.0
    is_at_resistance: bool = False
    is_near_support: bool = False
    volume_confirms: bool = False
    volume_exhaustion: bool = False
    liquidity_trap_risk: float = 0.0  # 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend": self.trend.value,
            "trend_quality": round(self.trend_quality, 1),
            "swing_highs": len(self.swing_highs),
            "swing_lows": len(self.swing_lows),
            "support_levels": [
                {
                    "price": round(s.price, 2),
                    "touches": s.touches,
                    "strength": round(s.strength, 1),
                }
                for s in self.support_levels[:5]
            ],
            "resistance_levels": [
                {
                    "price": round(r.price, 2),
                    "touches": r.touches,
                    "strength": round(r.strength, 1),
                }
                for r in self.resistance_levels[:5]
            ],
            "nearest_support": (
                round(self.nearest_support, 2) if self.nearest_support else None
            ),
            "nearest_resistance": (
                round(self.nearest_resistance, 2) if self.nearest_resistance else None
            ),
            "breakout_quality": (
                self.breakout_quality.value if self.breakout_quality else None
            ),
            "is_extended": bool(self.is_extended),
            "extension_pct": round(float(self.extension_pct), 2),
            "is_at_resistance": bool(self.is_at_resistance),
            "is_near_support": bool(self.is_near_support),
            "volume_confirms": bool(self.volume_confirms),
            "volume_exhaustion": bool(self.volume_exhaustion),
            "liquidity_trap_risk": round(float(self.liquidity_trap_risk), 2),
        }


# ── Structure Detector ────────────────────────────────


class StructureDetector:
    """
    Price structure analysis engine.

    Replaces indicator-only thinking with
    swing structure + S/R + volume context.
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        sr_tolerance_pct: float = 0.015,
        extension_threshold_pct: float = 5.0,
    ):
        self.swing_lookback = swing_lookback
        self.sr_tolerance = sr_tolerance_pct
        self.extension_threshold = extension_threshold_pct

    def analyze(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> StructureReport:
        """Full structure analysis."""
        report = StructureReport()

        if len(close) < 20:
            return report

        # 1. Detect swing points
        highs = self._find_swing_highs(high, volume)
        lows = self._find_swing_lows(low, volume)
        report.swing_highs = highs
        report.swing_lows = lows

        # 2. Classify trend from swings
        report.trend, report.trend_quality = self._classify_trend(highs, lows)

        # 3. Build S/R levels
        report.support_levels = self._build_sr(lows, close[-1], "support")
        report.resistance_levels = self._build_sr(highs, close[-1], "resistance")

        # 4. Nearest S/R
        price = close[-1]
        supports = [s.price for s in report.support_levels if s.price < price]
        resistances = [r.price for r in report.resistance_levels if r.price > price]
        if supports:
            report.nearest_support = max(supports)
            dist = (price - report.nearest_support) / price
            report.is_near_support = dist < 0.02
        if resistances:
            report.nearest_resistance = min(resistances)
            dist = (report.nearest_resistance - price) / price
            report.is_at_resistance = dist < 0.015

        # 5. Extension check
        if len(close) > 20:
            sma20 = np.mean(close[-20:])
            report.extension_pct = (price - sma20) / sma20 * 100
            report.is_extended = report.extension_pct > self.extension_threshold

        # 6. Volume analysis
        report.volume_confirms = self._check_volume_confirms(close, volume)
        report.volume_exhaustion = self._check_volume_exhaustion(close, volume)

        # 7. Breakout quality
        report.breakout_quality = self._assess_breakout_quality(
            close, high, volume, report
        )

        # 8. Liquidity trap risk
        report.liquidity_trap_risk = self._liquidity_trap_risk(close, high, low, volume)

        return report

    def _find_swing_highs(
        self,
        high: np.ndarray,
        volume: np.ndarray,
    ) -> List[SwingPoint]:
        """Detect swing highs."""
        n = self.swing_lookback
        swings = []
        for i in range(n, len(high) - n):
            if high[i] >= max(high[i - n : i + n + 1]) - 1e-6:
                swings.append(
                    SwingPoint(
                        index=i,
                        price=float(high[i]),
                        is_high=True,
                        volume=float(volume[i]),
                        strength=n,
                    )
                )
        return swings

    def _find_swing_lows(
        self,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> List[SwingPoint]:
        """Detect swing lows."""
        n = self.swing_lookback
        swings = []
        for i in range(n, len(low) - n):
            if low[i] <= min(low[i - n : i + n + 1]) + 1e-6:
                swings.append(
                    SwingPoint(
                        index=i,
                        price=float(low[i]),
                        is_high=False,
                        volume=float(volume[i]),
                        strength=n,
                    )
                )
        return swings

    def _classify_trend(
        self,
        highs: List[SwingPoint],
        lows: List[SwingPoint],
    ) -> Tuple[TrendStructure, float]:
        """
        Classify trend from swing sequence.

        HH + HL = uptrend
        LH + LL = downtrend
        Mixed = range / transition
        """
        if len(highs) < 2 or len(lows) < 2:
            return TrendStructure.RANGE, 0.0

        # Check recent swings (last 4-6)
        recent_h = highs[-4:] if len(highs) >= 4 else highs
        recent_l = lows[-4:] if len(lows) >= 4 else lows

        hh_count = 0
        lh_count = 0
        for i in range(1, len(recent_h)):
            if recent_h[i].price > recent_h[i - 1].price:
                hh_count += 1
            else:
                lh_count += 1

        hl_count = 0
        ll_count = 0
        for i in range(1, len(recent_l)):
            if recent_l[i].price > recent_l[i - 1].price:
                hl_count += 1
            else:
                ll_count += 1

        total = max(hh_count + lh_count + hl_count + ll_count, 1)
        bull_score = (hh_count + hl_count) / total
        bear_score = (lh_count + ll_count) / total

        if bull_score >= 0.8:
            return (
                TrendStructure.STRONG_UPTREND,
                bull_score * 100,
            )
        elif bull_score >= 0.6:
            return TrendStructure.UPTREND, bull_score * 100
        elif bear_score >= 0.8:
            return (
                TrendStructure.STRONG_DOWNTREND,
                bear_score * 100,
            )
        elif bear_score >= 0.6:
            return (
                TrendStructure.DOWNTREND,
                bear_score * 100,
            )
        elif abs(bull_score - bear_score) < 0.2:
            return TrendStructure.RANGE, 50.0
        else:
            return TrendStructure.TRANSITION, 50.0

    def _build_sr(
        self,
        swings: List[SwingPoint],
        current_price: float,
        level_type: str,
    ) -> List[SRLevel]:
        """
        Cluster swing points into S/R levels.

        Multiple touches at similar price = stronger level.
        """
        if not swings:
            return []

        tol = self.sr_tolerance
        levels: List[SRLevel] = []

        for sp in swings:
            merged = False
            for lv in levels:
                if abs(sp.price - lv.price) / lv.price < tol:
                    # Merge: update average price
                    lv.price = (lv.price * lv.touches + sp.price) / (lv.touches + 1)
                    lv.touches += 1
                    lv.last_seen = sp.index
                    lv.strength = lv.touches * 10 + sp.volume / 1e6
                    merged = True
                    break
            if not merged:
                levels.append(
                    SRLevel(
                        price=sp.price,
                        level_type=level_type,
                        touches=1,
                        strength=10.0 + sp.volume / 1e6,
                        first_seen=sp.index,
                        last_seen=sp.index,
                    )
                )

        # Sort by strength descending
        levels.sort(key=lambda x: x.strength, reverse=True)
        return levels[:10]

    def _check_volume_confirms(
        self,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> bool:
        """
        Volume confirmation: up day on above-avg volume.
        """
        if len(close) < 21:
            return False
        avg_vol = np.mean(volume[-20:])
        return bool(close[-1] > close[-2] and volume[-1] > avg_vol * 1.2)

    def _check_volume_exhaustion(
        self,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> bool:
        """
        Volume exhaustion: climax volume after extended move.

        High volume + extended price + near resistance
        = exhaustion, not confirmation.
        """
        if len(close) < 21:
            return False
        avg_vol = np.mean(volume[-20:])
        sma20 = np.mean(close[-20:])
        extended = (close[-1] - sma20) / sma20 > 0.05
        climax_vol = volume[-1] > avg_vol * 2.5
        return bool(extended and climax_vol)

    def _assess_breakout_quality(
        self,
        close: np.ndarray,
        high: np.ndarray,
        volume: np.ndarray,
        report: StructureReport,
    ) -> Optional[BreakoutQuality]:
        """
        Assess breakout quality if price is near
        recent highs.
        """
        if len(close) < 21:
            return None

        recent_high = float(np.max(high[-20:-1]))
        price = close[-1]

        # Not a breakout if not near highs
        if price < recent_high * 0.98:
            return None

        avg_vol = np.mean(volume[-20:])
        vol_ratio = volume[-1] / avg_vol if avg_vol > 0 else 1

        if report.volume_exhaustion:
            return BreakoutQuality.EXHAUSTION
        if vol_ratio < 1.0:
            return BreakoutQuality.WEAK
        if report.liquidity_trap_risk > 0.6 or vol_ratio < 0.8:
            return BreakoutQuality.FAKE
        if vol_ratio > 1.5:
            return BreakoutQuality.GENUINE
        return BreakoutQuality.WEAK

    def _liquidity_trap_risk(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> float:
        """
        Detect potential liquidity trap / stop hunt.

        Signs:
        - Spike above resistance then close back inside
        - Spike below support then close back above
        - High volume on reversal candle
        """
        if len(close) < 5:
            return 0.0

        risk = 0.0

        # Check last candle for rejection
        body = abs(close[-1] - close[-2])
        upper_wick = high[-1] - max(close[-1], close[-2])
        lower_wick = min(close[-1], close[-2]) - low[-1]
        candle_range = high[-1] - low[-1]

        if candle_range == 0:
            return 0.0

        # Large upper wick = potential bull trap
        if upper_wick > body * 2:
            risk += 0.3

        # Large lower wick = potential bear trap
        if lower_wick > body * 2:
            risk += 0.2

        # High volume on reversal
        if len(volume) >= 20:
            avg_vol = np.mean(volume[-20:])
            if volume[-1] > avg_vol * 2:
                if close[-1] < close[-2]:
                    risk += 0.3  # High vol down = distribution
                else:
                    risk -= 0.1  # High vol up = accumulation

        return max(0.0, min(1.0, risk))


def analyze_structure(
    close: list,
    high: list,
    low: list,
    volume: list,
) -> Dict[str, Any]:
    """Convenience function for quick analysis."""
    detector = StructureDetector()
    report = detector.analyze(
        np.array(close, dtype=float),
        np.array(high, dtype=float),
        np.array(low, dtype=float),
        np.array(volume, dtype=float),
    )
    return report.to_dict()
