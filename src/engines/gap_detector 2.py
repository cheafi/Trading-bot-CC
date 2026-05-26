"""
Gap Detection Engine — Sprint 66
===================================
Detects and classifies price gaps from OHLCV data.

Gap types:
  - GAP_UP / GAP_DOWN: open vs previous close
  - BREAKAWAY: gaps through resistance/support on volume
  - EXHAUSTION: gaps in extended trend with fading volume
  - COMMON: small gap in range-bound action

Usage:
    detector = GapDetector()
    gaps = detector.detect(ohlcv)
    # ohlcv = [{"open":..., "high":..., "low":..., "close":..., "volume":...}, ...]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Gap:
    """A single detected gap."""

    bar_index: int = 0
    direction: str = ""  # "UP" / "DOWN"
    gap_pct: float = 0.0  # Size as % of prev close
    gap_type: str = "COMMON"  # BREAKAWAY / EXHAUSTION / COMMON
    filled: bool = False  # Has the gap been filled?
    fill_bars: int = 0  # Bars to fill (0 = unfilled)
    open_price: float = 0.0
    prev_close: float = 0.0
    volume_ratio: float = 1.0  # Volume vs 20-bar avg

    def to_dict(self) -> dict:
        return {
            "bar_index": self.bar_index,
            "direction": self.direction,
            "gap_pct": round(self.gap_pct, 2),
            "gap_type": self.gap_type,
            "filled": self.filled,
            "fill_bars": self.fill_bars,
            "volume_ratio": round(self.volume_ratio, 2),
        }


@dataclass
class GapReport:
    """Summary of gap analysis for a ticker."""

    ticker: str = ""
    gaps: List[Gap] = field(default_factory=list)
    unfilled_gaps: int = 0
    recent_gap: Optional[Gap] = None
    gap_tendency: str = "neutral"  # "fills_fast" / "runs" / "neutral"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "total_gaps": len(self.gaps),
            "unfilled_gaps": self.unfilled_gaps,
            "recent_gap": self.recent_gap.to_dict() if self.recent_gap else None,
            "gap_tendency": self.gap_tendency,
            "gaps": [g.to_dict() for g in self.gaps[-5:]],
        }


class GapDetector:
    """
    Detect and classify price gaps from OHLCV bars.
    """

    MIN_GAP_PCT = 0.5  # Minimum 0.5% to count as gap
    BREAKAWAY_VOL_RATIO = 1.5  # Volume 1.5x avg for breakaway
    LOOKBACK_AVG_VOL = 20  # Bars for avg volume

    def detect(
        self,
        bars: List[Dict[str, Any]],
        ticker: str = "",
    ) -> GapReport:
        """
        Detect gaps in OHLCV data.

        Args:
            bars: List of dicts with open/high/low/close/volume keys.
                  Ordered oldest → newest.
            ticker: Optional ticker symbol.
        """
        if len(bars) < 2:
            return GapReport(ticker=ticker)

        gaps: List[Gap] = []

        for i in range(1, len(bars)):
            prev = bars[i - 1]
            curr = bars[i]

            prev_close = prev.get("close", 0)
            curr_open = curr.get("open", 0)

            if prev_close <= 0:
                continue

            gap_pct = (curr_open - prev_close) / prev_close * 100

            if abs(gap_pct) < self.MIN_GAP_PCT:
                continue

            # Volume ratio
            vol_window = bars[max(0, i - self.LOOKBACK_AVG_VOL) : i]
            avg_vol = sum(b.get("volume", 0) for b in vol_window) / max(
                1, len(vol_window)
            )
            curr_vol = curr.get("volume", 0)
            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

            direction = "UP" if gap_pct > 0 else "DOWN"

            # Classify gap type
            gap_type = self._classify(gap_pct, vol_ratio, bars, i, direction)

            gap = Gap(
                bar_index=i,
                direction=direction,
                gap_pct=gap_pct,
                gap_type=gap_type,
                open_price=curr_open,
                prev_close=prev_close,
                volume_ratio=vol_ratio,
            )
            gaps.append(gap)

        # Check gap fills
        self._check_fills(gaps, bars)

        # Build report
        unfilled = sum(1 for g in gaps if not g.filled)
        recent = gaps[-1] if gaps else None

        # Gap tendency
        tendency = "neutral"
        if len(gaps) >= 3:
            filled_gaps = [g for g in gaps if g.filled]
            if filled_gaps:
                avg_fill = sum(g.fill_bars for g in filled_gaps) / len(filled_gaps)
                if avg_fill <= 3:
                    tendency = "fills_fast"
                elif avg_fill > 10:
                    tendency = "runs"

        return GapReport(
            ticker=ticker,
            gaps=gaps,
            unfilled_gaps=unfilled,
            recent_gap=recent,
            gap_tendency=tendency,
        )

    def _classify(
        self,
        gap_pct: float,
        vol_ratio: float,
        bars: List[Dict[str, Any]],
        idx: int,
        direction: str,
    ) -> str:
        """Classify a gap as BREAKAWAY, EXHAUSTION, or COMMON."""

        # Breakaway: large gap + high volume
        if abs(gap_pct) >= 2.0 and vol_ratio >= self.BREAKAWAY_VOL_RATIO:
            return "BREAKAWAY"

        # Exhaustion: gap after extended trend with lower volume
        if idx >= 10:
            # Check if price has been trending in the gap direction
            lookback = bars[idx - 10 : idx]
            closes = [b.get("close", 0) for b in lookback]
            if len(closes) >= 2 and closes[-1] > 0 and closes[0] > 0:
                trend_pct = (closes[-1] - closes[0]) / closes[0] * 100
                # Same direction trend + fading volume
                if direction == "UP" and trend_pct > 10 and vol_ratio < 1.0:
                    return "EXHAUSTION"
                if direction == "DOWN" and trend_pct < -10 and vol_ratio < 1.0:
                    return "EXHAUSTION"

        return "COMMON"

    def _check_fills(self, gaps: List[Gap], bars: List[Dict[str, Any]]) -> None:
        """Check if each gap has been filled by subsequent price action."""
        for gap in gaps:
            fill_level = gap.prev_close
            start = gap.bar_index + 1

            for j in range(start, len(bars)):
                bar = bars[j]
                low = bar.get("low", 0)
                high = bar.get("high", 0)

                if gap.direction == "UP" and low <= fill_level:
                    gap.filled = True
                    gap.fill_bars = j - gap.bar_index
                    break
                elif gap.direction == "DOWN" and high >= fill_level:
                    gap.filled = True
                    gap.fill_bars = j - gap.bar_index
                    break
