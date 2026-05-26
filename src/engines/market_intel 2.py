"""
Market Intelligence Fusion Engine — Sprint 51
===============================================
Aggregates multi-dimensional market intelligence signals per ticker
into a unified intelligence score.

Signal dimensions (probabilistic evidence, not certainty):
 • Insider filings (SEC Form 4) — public buying/selling disclosures
 • Unusual volume — abnormal trading activity
 • Analyst consensus — revision direction and magnitude
 • Fund flows — ETF/institutional positioning shifts
 • Macro regime — central bank, yield curve, credit spreads
 • News sentiment — recent headline sentiment
 • Options activity — unusual call/put volume ratios

Each dimension produces a signal in [-1.0, +1.0] with a confidence
weight. The fusion score is a weighted average.

IMPORTANT: All data is from lawful, public, licensed sources.
Unusual activity is treated as probabilistic evidence, not certainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IntelSignal:
    """A single intelligence signal."""

    dimension: str  # e.g. "insider", "volume", "analyst"
    direction: float  # -1.0 (bearish) to +1.0 (bullish)
    confidence: float  # 0.0 to 1.0 (how much to trust)
    detail: str  # Human-readable explanation
    source: str  # "SEC_FORM4", "volume_scan", etc.
    is_leading: bool  # Leading vs lagging indicator
    best_for: str  # "short_term" / "swing" / "long_term"


@dataclass
class IntelReport:
    """Fused intelligence report for a ticker."""

    ticker: str
    fusion_score: float  # -1.0 to +1.0
    fusion_confidence: float  # 0.0 to 1.0
    bullish_signals: list[dict] = field(default_factory=list)
    bearish_signals: list[dict] = field(default_factory=list)
    neutral_signals: list[dict] = field(default_factory=list)
    signal_count: int = 0
    agreement_ratio: float = 0.0  # How aligned are signals
    dominant_theme: str = ""
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat() + "Z"


class MarketIntelEngine:
    """
    Fuses multiple intelligence dimensions into a unified view.

    Currently uses heuristic signals derived from price/volume data.
    Designed to be extended with real data feeds (EDGAR, news API,
    options flow API) as they become available.
    """

    # Dimension weights (higher = more influence)
    WEIGHTS = {
        "insider": 0.20,
        "volume": 0.15,
        "analyst": 0.15,
        "momentum": 0.15,
        "volatility": 0.10,
        "breadth": 0.10,
        "macro": 0.10,
        "sentiment": 0.05,
    }

    def analyse(
        self,
        ticker: str,
        price: float = 0.0,
        rsi: float = 50.0,
        volume_ratio: float = 1.0,
        atr_pct: float = 0.02,
        above_sma20: bool = False,
        above_sma50: bool = False,
        above_sma200: bool = False,
        regime: str = "UNKNOWN",
        vix: Optional[float] = None,
        change_pct: float = 0.0,
    ) -> IntelReport:
        """Generate intelligence report from available data."""
        signals: list[IntelSignal] = []

        # ── 1. Volume intelligence ──────────────────────────────────
        if volume_ratio > 2.0:
            signals.append(
                IntelSignal(
                    dimension="volume",
                    direction=0.5 if change_pct > 0 else -0.5,
                    confidence=min(0.8, volume_ratio / 5.0),
                    detail=(
                        f"Volume {volume_ratio:.1f}x average — "
                        f"unusual {'buying' if change_pct > 0 else 'selling'} "
                        f"pressure detected"
                    ),
                    source="volume_scan",
                    is_leading=True,
                    best_for="short_term",
                )
            )
        elif volume_ratio < 0.5:
            signals.append(
                IntelSignal(
                    dimension="volume",
                    direction=0.0,
                    confidence=0.3,
                    detail="Very low volume — thin liquidity, caution",
                    source="volume_scan",
                    is_leading=False,
                    best_for="short_term",
                )
            )

        # ── 2. Momentum / trend intelligence ────────────────────────
        trend_score = 0.0
        if above_sma20:
            trend_score += 0.25
        if above_sma50:
            trend_score += 0.25
        if above_sma200:
            trend_score += 0.25
        if 40 < rsi < 60:
            trend_score += 0.15
        elif rsi > 70:
            trend_score -= 0.3
        elif rsi < 30:
            trend_score += 0.2  # Oversold bounce potential

        signals.append(
            IntelSignal(
                dimension="momentum",
                direction=round(trend_score, 2),
                confidence=0.6,
                detail=self._momentum_detail(
                    rsi,
                    above_sma20,
                    above_sma50,
                    above_sma200,
                ),
                source="trend_analysis",
                is_leading=False,
                best_for="swing",
            )
        )

        # ── 3. Volatility intelligence ──────────────────────────────
        vol_signal = 0.0
        vol_detail = ""
        if atr_pct > 0.04:
            vol_signal = -0.3
            vol_detail = f"ATR {atr_pct:.1%} — high volatility, " f"wider stops needed"
        elif atr_pct < 0.01:
            vol_signal = 0.2
            vol_detail = (
                f"ATR {atr_pct:.1%} — low volatility, " f"possible breakout setup"
            )
        else:
            vol_signal = 0.0
            vol_detail = f"ATR {atr_pct:.1%} — normal volatility"

        signals.append(
            IntelSignal(
                dimension="volatility",
                direction=vol_signal,
                confidence=0.5,
                detail=vol_detail,
                source="volatility_analysis",
                is_leading=True,
                best_for="swing",
            )
        )

        # ── 4. Macro regime intelligence ────────────────────────────
        macro_signal = 0.0
        macro_detail = f"Regime: {regime}"
        if regime in ("RISK_ON", "UPTREND"):
            macro_signal = 0.4
            macro_detail += " — favorable for long positions"
        elif regime in ("RISK_OFF", "DOWNTREND"):
            macro_signal = -0.4
            macro_detail += " — defensive posture recommended"
        elif regime in ("CRISIS", "BEAR"):
            macro_signal = -0.7
            macro_detail += " — capital preservation priority"

        if vix is not None:
            if vix > 30:
                macro_signal -= 0.2
                macro_detail += f", VIX {vix:.0f} elevated"
            elif vix < 15:
                macro_signal += 0.1
                macro_detail += f", VIX {vix:.0f} low complacency risk"

        signals.append(
            IntelSignal(
                dimension="macro",
                direction=round(max(-1, min(1, macro_signal)), 2),
                confidence=0.7,
                detail=macro_detail,
                source="regime_analysis",
                is_leading=True,
                best_for="long_term",
            )
        )

        # ── 5. RSI-based mean-reversion signal ──────────────────────
        if rsi > 80:
            signals.append(
                IntelSignal(
                    dimension="analyst",
                    direction=-0.6,
                    confidence=0.7,
                    detail=(
                        f"RSI {rsi:.0f} — extremely overbought, "
                        f"mean-reversion risk high"
                    ),
                    source="rsi_extreme",
                    is_leading=True,
                    best_for="short_term",
                )
            )
        elif rsi < 25:
            signals.append(
                IntelSignal(
                    dimension="analyst",
                    direction=0.5,
                    confidence=0.6,
                    detail=(
                        f"RSI {rsi:.0f} — deeply oversold, "
                        f"bounce potential elevated"
                    ),
                    source="rsi_extreme",
                    is_leading=True,
                    best_for="short_term",
                )
            )

        # ── Fusion ──────────────────────────────────────────────────
        return self._fuse(ticker, signals)

    def _fuse(
        self,
        ticker: str,
        signals: list[IntelSignal],
    ) -> IntelReport:
        """Weighted fusion of all signals."""
        if not signals:
            return IntelReport(
                ticker=ticker,
                fusion_score=0.0,
                fusion_confidence=0.0,
                dominant_theme="No data",
            )

        weighted_sum = 0.0
        total_weight = 0.0
        bullish: list[dict] = []
        bearish: list[dict] = []
        neutral: list[dict] = []

        for s in signals:
            w = self.WEIGHTS.get(s.dimension, 0.05)
            weighted_sum += s.direction * s.confidence * w
            total_weight += w

            entry = {
                "dimension": s.dimension,
                "direction": s.direction,
                "confidence": s.confidence,
                "detail": s.detail,
                "source": s.source,
                "is_leading": s.is_leading,
                "best_for": s.best_for,
            }

            if s.direction > 0.1:
                bullish.append(entry)
            elif s.direction < -0.1:
                bearish.append(entry)
            else:
                neutral.append(entry)

        fusion = weighted_sum / total_weight if total_weight > 0 else 0.0
        fusion = max(-1.0, min(1.0, fusion))

        # Agreement: what % of signals agree with fusion direction
        if fusion >= 0:
            agree = sum(1 for s in signals if s.direction >= 0)
        else:
            agree = sum(1 for s in signals if s.direction < 0)
        agreement = agree / len(signals) if signals else 0

        # Confidence: average signal confidence × agreement
        avg_conf = sum(s.confidence for s in signals) / len(signals)
        fused_conf = round(avg_conf * agreement, 3)

        # Dominant theme
        if len(bullish) > len(bearish) + 1:
            theme = "Bullish convergence"
        elif len(bearish) > len(bullish) + 1:
            theme = "Bearish convergence"
        elif bullish and bearish:
            theme = "Mixed / conflicting signals"
        else:
            theme = "Neutral / insufficient data"

        return IntelReport(
            ticker=ticker,
            fusion_score=round(fusion, 3),
            fusion_confidence=fused_conf,
            bullish_signals=bullish,
            bearish_signals=bearish,
            neutral_signals=neutral,
            signal_count=len(signals),
            agreement_ratio=round(agreement, 3),
            dominant_theme=theme,
        )

    @staticmethod
    def _momentum_detail(
        rsi: float,
        above_sma20: bool,
        above_sma50: bool,
        above_sma200: bool,
    ) -> str:
        parts = []
        if above_sma200:
            parts.append("above 200-day SMA")
        if above_sma50:
            parts.append("above 50-day SMA")
        if above_sma20:
            parts.append("above 20-day SMA")
        parts.append(f"RSI {rsi:.0f}")
        return "Trend: " + ", ".join(parts)

    def summary(self) -> dict:
        return {
            "engine": "MarketIntelEngine",
            "dimensions": list(self.WEIGHTS.keys()),
            "weights": self.WEIGHTS,
            "note": (
                "Signals are probabilistic evidence, "
                "not certainty. Verify with multiple sources."
            ),
        }
