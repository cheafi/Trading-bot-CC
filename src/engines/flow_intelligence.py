"""
CC — Flow Intelligence Engine
================================
Detects smart money / institutional flow signals from
price-volume data (no paid data feeds required).

Layers:
  1. Abnormal Volume — volume spike detection
  2. Large Trade Proxy — price impact estimation
  3. Options Activity Proxy — implied from vol patterns
  4. Accumulation/Distribution — OBV + money flow
  5. Insider Proxy — unusual pre-event patterns

All signals are heuristic-based using free data (yfinance).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class FlowType(str, Enum):
    VOLUME_SPIKE = "VOLUME_SPIKE"
    LARGE_TRADE = "LARGE_TRADE"
    OPTIONS_PROXY = "OPTIONS_PROXY"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    INSIDER_PROXY = "INSIDER_PROXY"
    DARK_POOL_PROXY = "DARK_POOL_PROXY"


class FlowDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class FlowStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


@dataclass
class FlowSignal:
    """A single flow intelligence signal."""

    ticker: str
    flow_type: FlowType
    direction: FlowDirection
    strength: FlowStrength
    score: float = 0.0  # 0-100
    description: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "flow_type": self.flow_type.value,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "score": round(self.score, 1),
            "description": self.description,
            "detail": self.detail,
        }


@dataclass
class FlowProfile:
    """Complete flow intelligence profile for a ticker."""

    ticker: str
    signals: List[FlowSignal] = field(default_factory=list)
    composite_score: float = 0.0  # -100 to +100
    direction: FlowDirection = FlowDirection.NEUTRAL
    summary: str = ""

    # Individual layer scores
    volume_score: float = 0.0
    accumulation_score: float = 0.0
    large_trade_score: float = 0.0
    options_proxy_score: float = 0.0
    insider_proxy_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "composite_score": round(self.composite_score, 1),
            "direction": self.direction.value,
            "summary": self.summary,
            "volume_score": round(self.volume_score, 1),
            "accumulation_score": round(self.accumulation_score, 1),
            "large_trade_score": round(self.large_trade_score, 1),
            "options_proxy_score": round(self.options_proxy_score, 1),
            "insider_proxy_score": round(self.insider_proxy_score, 1),
            "signals": [s.to_dict() for s in self.signals],
            "signal_count": len(self.signals),
        }


class FlowIntelligenceEngine:
    """
    Detects institutional/smart-money flow patterns.

    All heuristic-based using OHLCV data only.

    Usage:
        engine = FlowIntelligenceEngine()
        profile = engine.analyze(price_data)
    """

    def analyze(self, data: Dict[str, Any]) -> FlowProfile:
        """
        Analyze a single ticker's flow.

        data should contain:
          ticker, volume, avg_volume_20, avg_volume_50,
          close, open, high, low, prev_close,
          change_pct, atr, rsi,
          volume_5d (list), close_5d (list),
          obv_slope (float, optional)
        """
        ticker = data.get("ticker", "")
        profile = FlowProfile(ticker=ticker)
        signals: List[FlowSignal] = []

        # Layer 1: Volume Spike
        vol = data.get("volume", 0)
        avg_vol = data.get("avg_volume_20", 1)
        vol_ratio = vol / max(avg_vol, 1)

        if vol_ratio >= 3.0:
            strength = FlowStrength.STRONG
            score = min(100, vol_ratio * 20)
        elif vol_ratio >= 2.0:
            strength = FlowStrength.MODERATE
            score = vol_ratio * 15
        elif vol_ratio >= 1.5:
            strength = FlowStrength.WEAK
            score = vol_ratio * 10
        else:
            strength = None
            score = 0

        if strength:
            chg = data.get("change_pct", 0)
            direction = (
                FlowDirection.BULLISH
                if chg > 0.5
                else FlowDirection.BEARISH if chg < -0.5 else FlowDirection.NEUTRAL
            )
            signals.append(
                FlowSignal(
                    ticker=ticker,
                    flow_type=FlowType.VOLUME_SPIKE,
                    direction=direction,
                    strength=strength,
                    score=score,
                    description=f"Volume {vol_ratio:.1f}x avg",
                    detail=f"Vol {vol:,.0f} vs avg {avg_vol:,.0f}",
                )
            )
            profile.volume_score = score * (
                1 if direction == FlowDirection.BULLISH else -1
            )

        # Layer 2: Large Trade Proxy
        # High price impact with high volume = institutional
        high = data.get("high", 0)
        low = data.get("low", 0)
        close = data.get("close", 0)
        atr = data.get("atr", 1)
        if close > 0 and atr > 0:
            range_pct = (high - low) / close * 100
            range_vs_atr = (high - low) / atr if atr > 0 else 1

            # Narrow range + high volume = dark pool / block trade
            if vol_ratio >= 1.5 and range_vs_atr < 0.8:
                lt_score = min(80, vol_ratio * 15)
                signals.append(
                    FlowSignal(
                        ticker=ticker,
                        flow_type=FlowType.DARK_POOL_PROXY,
                        direction=FlowDirection.NEUTRAL,
                        strength=FlowStrength.MODERATE,
                        score=lt_score,
                        description="Narrow range + high volume",
                        detail=f"Range {range_pct:.1f}% vs "
                        f"ATR {range_vs_atr:.1f}x, vol {vol_ratio:.1f}x",
                    )
                )
                profile.large_trade_score = lt_score

            # Wide range + high volume = aggressive buying/selling
            elif vol_ratio >= 1.5 and range_vs_atr > 1.5:
                chg = data.get("change_pct", 0)
                direction = FlowDirection.BULLISH if chg > 0 else FlowDirection.BEARISH
                lt_score = min(90, vol_ratio * 18)
                signals.append(
                    FlowSignal(
                        ticker=ticker,
                        flow_type=FlowType.LARGE_TRADE,
                        direction=direction,
                        strength=FlowStrength.STRONG,
                        score=lt_score,
                        description="Wide range breakout + volume",
                        detail=f"Range {range_pct:.1f}%, " f"vol {vol_ratio:.1f}x",
                    )
                )
                profile.large_trade_score = lt_score * (
                    1 if direction == FlowDirection.BULLISH else -1
                )

        # Layer 3: Accumulation / Distribution
        close_5d = data.get("close_5d", [])
        volume_5d = data.get("volume_5d", [])
        if len(close_5d) >= 5 and len(volume_5d) >= 5:
            # Simple money flow: up days on high volume = accumulation
            up_vol = sum(
                v
                for i, (c, v) in enumerate(zip(close_5d[1:], volume_5d[1:]))
                if c > close_5d[i]
            )
            down_vol = sum(
                v
                for i, (c, v) in enumerate(zip(close_5d[1:], volume_5d[1:]))
                if c <= close_5d[i]
            )
            total_vol = up_vol + down_vol
            if total_vol > 0:
                mf_ratio = up_vol / total_vol
                if mf_ratio > 0.65:
                    acc_score = min(80, mf_ratio * 100)
                    signals.append(
                        FlowSignal(
                            ticker=ticker,
                            flow_type=FlowType.ACCUMULATION,
                            direction=FlowDirection.BULLISH,
                            strength=(
                                FlowStrength.STRONG
                                if mf_ratio > 0.8
                                else FlowStrength.MODERATE
                            ),
                            score=acc_score,
                            description="5-day accumulation pattern",
                            detail=f"Up-vol ratio {mf_ratio:.0%}",
                        )
                    )
                    profile.accumulation_score = acc_score
                elif mf_ratio < 0.35:
                    dist_score = min(80, (1 - mf_ratio) * 100)
                    signals.append(
                        FlowSignal(
                            ticker=ticker,
                            flow_type=FlowType.DISTRIBUTION,
                            direction=FlowDirection.BEARISH,
                            strength=(
                                FlowStrength.STRONG
                                if mf_ratio < 0.2
                                else FlowStrength.MODERATE
                            ),
                            score=dist_score,
                            description="5-day distribution pattern",
                            detail=f"Up-vol ratio {mf_ratio:.0%}",
                        )
                    )
                    profile.accumulation_score = -dist_score

        # Layer 4: Options Activity Proxy
        # High IV + high volume + narrow price = options hedging
        if vol_ratio >= 2.0 and abs(data.get("change_pct", 0)) < 1.0:
            opt_score = min(70, vol_ratio * 12)
            signals.append(
                FlowSignal(
                    ticker=ticker,
                    flow_type=FlowType.OPTIONS_PROXY,
                    direction=FlowDirection.NEUTRAL,
                    strength=FlowStrength.MODERATE,
                    score=opt_score,
                    description="High volume, flat price — options hedging?",
                    detail=f"Vol {vol_ratio:.1f}x, chg "
                    f"{data.get('change_pct', 0):.1f}%",
                )
            )
            profile.options_proxy_score = opt_score

        # Layer 5: Insider Proxy
        # Unusual pre-event pattern: steady accumulation
        if (
            profile.accumulation_score > 50
            and vol_ratio >= 1.3
            and abs(data.get("change_pct", 0)) < 2.0
        ):
            ins_score = min(60, profile.accumulation_score * 0.7)
            signals.append(
                FlowSignal(
                    ticker=ticker,
                    flow_type=FlowType.INSIDER_PROXY,
                    direction=FlowDirection.BULLISH,
                    strength=FlowStrength.WEAK,
                    score=ins_score,
                    description="Quiet accumulation pattern",
                    detail="Accumulation + moderate volume + " "small price change",
                )
            )
            profile.insider_proxy_score = ins_score

        # Composite
        profile.signals = signals
        if signals:
            bull = sum(s.score for s in signals if s.direction == FlowDirection.BULLISH)
            bear = sum(s.score for s in signals if s.direction == FlowDirection.BEARISH)
            profile.composite_score = max(-100, min(100, bull - bear))
            if bull > bear * 1.5:
                profile.direction = FlowDirection.BULLISH
            elif bear > bull * 1.5:
                profile.direction = FlowDirection.BEARISH
            else:
                profile.direction = FlowDirection.NEUTRAL

            parts = [s.description for s in signals[:3]]
            profile.summary = " | ".join(parts)
        else:
            profile.summary = "No significant flow detected"

        return profile

    def analyze_batch(self, universe: List[Dict[str, Any]]) -> List[FlowProfile]:
        """Analyze flow for multiple tickers."""
        profiles = [self.analyze(d) for d in universe]
        # Sort by absolute composite score
        profiles.sort(key=lambda p: abs(p.composite_score), reverse=True)
        return profiles

    def get_unusual_activity(
        self, profiles: List[FlowProfile], min_score: float = 30
    ) -> List[FlowProfile]:
        """Filter to profiles with significant flow signals."""
        return [p for p in profiles if abs(p.composite_score) >= min_score]
