"""
CC — VCP Intelligence System
==============================
4-layer VCP analysis: Detection → Quality → Context → Action.

Not just a label — a full VCP brain that grades setups,
knows sector context, and provides actionable guidance.

VCP Grades:
  A+/A  — clean contraction, dry volume, leader, stage-fit
  B+/B  — decent contraction but some weakness
  C     — loose base, laggard, or late-stage
  D/F   — not a real VCP or too risky
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.sector_classifier import (
    LeaderStatus,
    SectorBucket,
    SectorContext,
    SectorStage,
)

try:
    import numpy as np

    from src.engines.structure_detector import StructureDetector
    _HAS_STRUCTURE = True
except ImportError:
    _HAS_STRUCTURE = False

try:
    from src.engines.historical_analog import find_similar_cases, analog_summary
    _HAS_ANALOG = True
except ImportError:
    _HAS_ANALOG = False

logger = logging.getLogger(__name__)


# ── VCP Detection ────────────────────────────────────────────────────


@dataclass
class VCPDetection:
    """Layer 1 — raw detection metrics."""

    is_vcp: bool = False
    contraction_count: int = 0  # T1→T2→T3 etc.
    contractions: List[float] = field(default_factory=list)  # each range %
    base_depth_pct: float = 0.0  # total base depth
    distance_from_highs_pct: float = 0.0
    days_in_base: int = 0
    ma_alignment: str = "MIXED"  # STRONG / WEAK / MIXED
    price_above_50ma: bool = False
    price_above_200ma: bool = False


@dataclass
class VCPQuality:
    """Layer 2 — quality scoring (0-10 each)."""

    contraction_tightness: float = 5.0  # Are contractions getting tighter?
    volume_dry_up: float = 5.0  # Is volume drying up at pivot?
    pivot_clarity: float = 5.0  # Is there a clear pivot level?
    base_structure: float = 5.0  # Clean base vs choppy mess
    support_quality: float = 5.0  # Key support levels holding?
    trend_alignment: float = 5.0  # Aligned with 50/150/200 MA?
    overall: float = 5.0  # Weighted composite


@dataclass
class VCPContextScore:
    """Layer 3 — context scoring (0-10 each)."""

    sector_fit: float = 5.0  # Does this sector favor VCP?
    regime_fit: float = 5.0  # Is market regime supportive?
    stage_fit: float = 5.0  # Sector stage supports breakout?
    leader_quality: float = 5.0  # Leader vs laggard
    group_strength: float = 5.0  # Sector group momentum
    crowding_risk: float = 5.0  # Is this crowded?
    extension_risk: float = 5.0  # Already extended?
    event_proximity: float = 5.0  # Earnings/catalyst nearby?
    overall: float = 5.0


@dataclass
class VCPAction:
    """Layer 4 — final VCP output."""

    grade: str = "C"  # A+ / A / B+ / B / C / D / F
    quality_score: float = 5.0  # 0-10
    context_score: float = 5.0  # 0-10
    combined_score: float = 5.0  # 0-10

    phase: str = "FORMING"  # FORMING / NEAR_PIVOT / AT_PIVOT / EXTENDED
    action: str = "WATCH"  # TRADE / WATCH / WAIT / NO_TRADE
    size_guidance: str = "NORMAL"  # FULL / NORMAL / PILOT / AVOID
    entry_zone: str = ""  # e.g. "Near $145 pivot"
    invalidation: str = ""  # e.g. "Close below T3 low at $138"
    why_now: str = ""
    why_not: str = ""
    better_alternative: str = ""

    similar_cases: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VCPResult:
    """Complete VCP analysis result."""

    ticker: str = ""
    detection: VCPDetection = field(default_factory=VCPDetection)
    quality: VCPQuality = field(default_factory=VCPQuality)
    context: VCPContextScore = field(default_factory=VCPContextScore)
    action: VCPAction = field(default_factory=VCPAction)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "is_vcp": self.detection.is_vcp,
            "grade": self.action.grade,
            "quality_score": round(self.action.quality_score, 1),
            "context_score": round(self.action.context_score, 1),
            "combined_score": round(self.action.combined_score, 1),
            "phase": self.action.phase,
            "action": self.action.action,
            "size_guidance": self.action.size_guidance,
            "entry_zone": self.action.entry_zone,
            "invalidation": self.action.invalidation,
            "why_now": self.action.why_now,
            "why_not": self.action.why_not,
            "better_alternative": self.action.better_alternative,
            "detection": {
                "contraction_count": self.detection.contraction_count,
                "contractions": self.detection.contractions,
                "base_depth_pct": round(self.detection.base_depth_pct, 2),
                "days_in_base": self.detection.days_in_base,
                "ma_alignment": self.detection.ma_alignment,
            },
            "quality": {
                "contraction_tightness": round(
                    self.quality.contraction_tightness,
                    1,
                ),
                "volume_dry_up": round(self.quality.volume_dry_up, 1),
                "pivot_clarity": round(self.quality.pivot_clarity, 1),
                "base_structure": round(self.quality.base_structure, 1),
                "support_quality": round(self.quality.support_quality, 1),
                "trend_alignment": round(self.quality.trend_alignment, 1),
                "overall": round(self.quality.overall, 1),
            },
            "context": {
                "sector_fit": round(self.context.sector_fit, 1),
                "regime_fit": round(self.context.regime_fit, 1),
                "stage_fit": round(self.context.stage_fit, 1),
                "leader_quality": round(self.context.leader_quality, 1),
                "extension_risk": round(self.context.extension_risk, 1),
                "event_proximity": round(self.context.event_proximity, 1),
                "overall": round(self.context.overall, 1),
            },
        }


# ── VCP Intelligence Engine ─────────────────────────────────────────


class VCPIntelligence:
    """
    Full VCP analysis system.

    Usage:
        vcp = VCPIntelligence()
        result = vcp.analyze(signal, sector_ctx, regime)
    """

    def analyze(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> VCPResult:
        """Run full 4-layer VCP analysis."""
        result = VCPResult(ticker=signal.get("ticker", ""))

        # Layer 1: Detection
        result.detection = self._detect(signal)
        if not result.detection.is_vcp:
            result.action.action = "NO_TRADE"
            result.action.grade = "F"
            result.action.why_not = "Not a valid VCP pattern"
            return result

        # Layer 2: Quality
        result.quality = self._score_quality(signal, result.detection)

        # Layer 3: Context
        result.context = self._score_context(
            signal,
            sector,
            regime,
            result.detection,
        )

        # Layer 4: Action
        result.action = self._determine_action(
            signal, sector, result.detection, result.quality, result.context,
            regime=regime,
        )

        return result

    # ── Layer 1: Detection ───────────────────────────────────────

    def _detect(self, sig: Dict[str, Any]) -> VCPDetection:
        """Detect VCP pattern from signal data or raw OHLCV."""
        d = VCPDetection()

        # ── Try OHLCV-based detection via StructureDetector ──
        if _HAS_STRUCTURE and "closes" in sig:
            return self._detect_from_ohlcv(sig, d)

        # ── Fallback: pre-computed signal fields ──
        strategy = sig.get("strategy", "").lower()
        pattern = sig.get("pattern", "").lower()

        # Direct VCP label
        if "vcp" in strategy or "vcp" in pattern:
            d.is_vcp = True
        # Detect VCP-like characteristics from data
        elif sig.get("contraction_count", 0) >= 2:
            d.is_vcp = True

        if not d.is_vcp:
            return d

        # Extract VCP metrics from signal
        d.contraction_count = sig.get("contraction_count", 2)
        d.contractions = sig.get("contractions", [])
        d.base_depth_pct = sig.get("base_depth_pct", sig.get("drawdown", 15.0))
        d.distance_from_highs_pct = sig.get("distance_from_highs", 5.0)
        d.days_in_base = sig.get("days_in_base", 30)

        # Moving average alignment
        price = sig.get("price", sig.get("close", 0))
        ma50 = sig.get("ma50", sig.get("sma50", 0))
        ma200 = sig.get("ma200", sig.get("sma200", 0))
        d.price_above_50ma = price > ma50 > 0
        d.price_above_200ma = price > ma200 > 0

        if d.price_above_50ma and d.price_above_200ma and ma50 > ma200:
            d.ma_alignment = "STRONG"
        elif d.price_above_50ma:
            d.ma_alignment = "WEAK"
        else:
            d.ma_alignment = "MIXED"

        return d

    def _detect_from_ohlcv(
        self, sig: Dict[str, Any], d: VCPDetection
    ) -> VCPDetection:
        """
        Algorithmic VCP detection from raw OHLCV data.
        Uses StructureDetector to find swing points and measure
        contraction sequences — NOT label-dependent.
        """
        closes = np.array(sig["closes"], dtype=float)
        highs = np.array(sig.get("highs", sig["closes"]), dtype=float)
        lows = np.array(sig.get("lows", sig["closes"]), dtype=float)
        volumes = np.array(sig.get("volumes", [1e6] * len(closes)),
                           dtype=float)

        if len(closes) < 30:
            return d

        detector = StructureDetector(swing_lookback=3)
        report = detector.analyze(closes, highs, lows, volumes)

        # Find contraction sequence from swing highs
        swing_highs = [s.price for s in report.swing_highs[-6:]]
        swing_lows = [s.price for s in report.swing_lows[-6:]]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return d

        # Measure contraction ranges (high-low pairs)
        n = min(len(swing_highs), len(swing_lows))
        ranges = []
        for i in range(n):
            r = swing_highs[i] - swing_lows[i]
            if r > 0:
                ranges.append(r)

        if len(ranges) < 2:
            return d

        # VCP = contracting ranges (each smaller than previous)
        contracting = 0
        for i in range(1, len(ranges)):
            if ranges[i] < ranges[i - 1] * 1.05:  # 5% tolerance
                contracting += 1

        # Need at least 2 contractions for VCP
        if contracting >= 1:
            d.is_vcp = True
            d.contraction_count = contracting + 1
            d.contractions = [round(r, 2) for r in ranges]

            # Base depth: max range / price
            price = closes[-1]
            d.base_depth_pct = max(ranges) / price * 100 if price > 0 else 0

            # Distance from highs
            high_52 = max(highs[-min(252, len(highs)):])
            d.distance_from_highs_pct = (
                (high_52 - price) / high_52 * 100 if high_52 > 0 else 0
            )

            # Days in base (from first swing high to now)
            if report.swing_highs:
                first_idx = report.swing_highs[0].index
                d.days_in_base = len(closes) - first_idx

            # MA alignment
            if len(closes) >= 50:
                ma50 = np.mean(closes[-50:])
                ma200 = np.mean(closes[-200:]) if len(closes) >= 200 else 0
                d.price_above_50ma = price > ma50
                d.price_above_200ma = price > ma200 > 0
                if d.price_above_50ma and d.price_above_200ma and ma50 > ma200:
                    d.ma_alignment = "STRONG"
                elif d.price_above_50ma:
                    d.ma_alignment = "WEAK"
                else:
                    d.ma_alignment = "MIXED"

            # Inject structure data back into signal for downstream
            sig["trend_structure"] = report.trend
            sig["trend_quality"] = report.trend_quality
            sig["breakout_quality"] = report.breakout_quality
            sig["volume_confirms"] = report.volume_confirms
            sig["volume_exhaustion"] = report.volume_exhaustion
            if report.nearest_support:
                sig["nearest_support"] = report.nearest_support
            if report.nearest_resistance:
                sig["nearest_resistance"] = report.nearest_resistance

        return d

    # ── Layer 2: Quality ─────────────────────────────────────────

    def _score_quality(
        self, sig: Dict[str, Any], detection: VCPDetection
    ) -> VCPQuality:
        """Score VCP quality components."""
        q = VCPQuality()

        # Contraction tightness — are they getting tighter?
        contractions = detection.contractions
        if len(contractions) >= 2:
            # Each subsequent contraction should be smaller
            tightening = all(
                contractions[i] <= contractions[i - 1] * 1.1
                for i in range(1, len(contractions))
            )
            c0 = contractions[0]
            ratio = contractions[-1] / c0 if c0 > 0 else 1.0
            if tightening and ratio < 0.5:
                q.contraction_tightness = 9.0
            elif tightening:
                q.contraction_tightness = 7.5
            elif ratio < 0.7:
                q.contraction_tightness = 6.0
            else:
                q.contraction_tightness = 4.0
        else:
            # Use base depth as proxy
            depth = detection.base_depth_pct
            if depth < 15:
                q.contraction_tightness = 8.0
            elif depth < 25:
                q.contraction_tightness = 6.0
            elif depth < 35:
                q.contraction_tightness = 4.0
            else:
                q.contraction_tightness = 2.5

        # Volume dry-up at pivot
        vol_ratio = sig.get("vol_ratio", 1.0)
        vol_dry = sig.get("volume_dry_up")
        if vol_dry is not None:
            q.volume_dry_up = min(10, vol_dry)
        elif vol_ratio < 0.5:
            q.volume_dry_up = 8.5  # Very dry — good
        elif vol_ratio < 0.8:
            q.volume_dry_up = 7.0
        elif vol_ratio < 1.2:
            q.volume_dry_up = 5.5
        else:
            q.volume_dry_up = 4.0  # High volume in base — less ideal

        # Pivot clarity
        pivot = sig.get("pivot_price", sig.get("resistance", 0))
        if pivot > 0:
            q.pivot_clarity = 8.0
        else:
            q.pivot_clarity = 4.0
        # Bonus for tight pivot zone
        if sig.get("pivot_range_pct", 5.0) < 2.0:
            q.pivot_clarity = min(10, q.pivot_clarity + 1.5)

        # Base structure
        if detection.contraction_count >= 3 and detection.base_depth_pct < 30:
            q.base_structure = 8.5
        elif detection.contraction_count >= 2:
            q.base_structure = 7.0
        elif detection.base_depth_pct < 20:
            q.base_structure = 6.0
        else:
            q.base_structure = 4.5

        # Support quality
        support_tests = sig.get("support_tests", 0)
        if support_tests >= 3:
            q.support_quality = 8.5
        elif support_tests >= 2:
            q.support_quality = 7.0
        else:
            q.support_quality = 5.0

        # Trend alignment
        if detection.ma_alignment == "STRONG":
            q.trend_alignment = 9.0
        elif detection.ma_alignment == "WEAK":
            q.trend_alignment = 5.5
        else:
            q.trend_alignment = 3.0

        # Weighted overall
        q.overall = (
            0.25 * q.contraction_tightness
            + 0.20 * q.volume_dry_up
            + 0.15 * q.pivot_clarity
            + 0.15 * q.base_structure
            + 0.10 * q.support_quality
            + 0.15 * q.trend_alignment
        )

        return q

    # ── Layer 3: Context ─────────────────────────────────────────

    def _score_context(
        self,
        sig: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
        detection: VCPDetection,
    ) -> VCPContextScore:
        """Score VCP in its market/sector context."""
        c = VCPContextScore()

        # Sector fit — VCP works best in growth/tech
        _SECTOR_VCP_FIT = {
            SectorBucket.HIGH_GROWTH: 8.5,
            SectorBucket.CYCLICAL: 6.0,
            SectorBucket.DEFENSIVE: 5.0,
            SectorBucket.THEME_HYPE: 6.5,
            SectorBucket.UNKNOWN: 5.0,
        }
        c.sector_fit = _SECTOR_VCP_FIT.get(sector.sector_bucket, 5.0)

        # Regime fit
        should_trade = regime.get("should_trade", True)
        trend = regime.get("trend", "").upper()
        if not should_trade:
            c.regime_fit = 2.0
        elif trend in ("BULLISH", "RISK_ON", "UPTREND"):
            c.regime_fit = 8.5
        elif trend in ("NEUTRAL",):
            c.regime_fit = 6.0
        else:
            c.regime_fit = 3.0

        # Stage fit
        _STAGE_FIT = {
            SectorStage.LAUNCH: 7.0,
            SectorStage.ACCELERATION: 9.0,
            SectorStage.CLIMAX: 4.0,
            SectorStage.DISTRIBUTION: 2.0,
            SectorStage.UNKNOWN: 5.0,
        }
        c.stage_fit = _STAGE_FIT.get(sector.sector_stage, 5.0)

        # Leader quality
        _LEADER_FIT = {
            LeaderStatus.LEADER: 9.5,
            LeaderStatus.EARLY_FOLLOWER: 7.0,
            LeaderStatus.LAGGARD: 3.0,
            LeaderStatus.UNKNOWN: 5.0,
        }
        c.leader_quality = _LEADER_FIT.get(sector.leader_status, 5.0)

        # Group strength
        rs = sector.relative_strength
        c.group_strength = min(10, max(0, 5.0 + rs * 5.0))

        # Crowding risk (inverted — high crowding = bad)
        c.crowding_risk = max(0, 10 - sector.crowding_risk * 10)

        # Extension risk
        dist = detection.distance_from_highs_pct
        if dist < 3:
            c.extension_risk = 4.0  # Near highs — breakout territory but risky
        elif dist < 8:
            c.extension_risk = 8.0  # Sweet spot
        elif dist < 15:
            c.extension_risk = 7.0
        else:
            c.extension_risk = 5.0  # Deep base

        # Event proximity
        days_to_earnings = sig.get("days_to_earnings", 30)
        if days_to_earnings < 5:
            c.event_proximity = 3.0  # Too close
        elif days_to_earnings < 14:
            c.event_proximity = 5.5
        else:
            c.event_proximity = 8.0  # Clear runway

        # Weighted overall
        c.overall = (
            0.15 * c.sector_fit
            + 0.20 * c.regime_fit
            + 0.15 * c.stage_fit
            + 0.15 * c.leader_quality
            + 0.10 * c.group_strength
            + 0.05 * c.crowding_risk
            + 0.10 * c.extension_risk
            + 0.10 * c.event_proximity
        )

        return c

    # ── Layer 4: Action ──────────────────────────────────────────

    def _determine_action(
        self,
        sig: Dict[str, Any],
        sector: SectorContext,
        detection: VCPDetection,
        quality: VCPQuality,
        context: VCPContextScore,
        regime: Dict[str, Any] | None = None,
    ) -> VCPAction:
        """Final VCP decision."""
        a = VCPAction()
        a.quality_score = quality.overall
        a.context_score = context.overall
        a.combined_score = 0.55 * quality.overall + 0.45 * context.overall

        # Grade
        cs = a.combined_score
        if cs >= 8.5:
            a.grade = "A+"
        elif cs >= 7.5:
            a.grade = "A"
        elif cs >= 6.5:
            a.grade = "B+"
        elif cs >= 5.5:
            a.grade = "B"
        elif cs >= 4.5:
            a.grade = "C"
        elif cs >= 3.0:
            a.grade = "D"
        else:
            a.grade = "F"

        # Phase
        dist = detection.distance_from_highs_pct
        if dist > 15:
            a.phase = "FORMING"
        elif dist > 5:
            a.phase = "NEAR_PIVOT"
        elif dist > 1:
            a.phase = "AT_PIVOT"
        else:
            a.phase = "EXTENDED"

        # Action decision
        if a.grade in ("A+", "A") and a.phase in ("AT_PIVOT", "NEAR_PIVOT"):
            a.action = "TRADE"
            a.size_guidance = "FULL"
        elif a.grade in ("A+", "A", "B+") and a.phase == "NEAR_PIVOT":
            a.action = "TRADE"
            a.size_guidance = "NORMAL"
        elif a.grade in ("B+", "B") and a.phase in ("AT_PIVOT", "NEAR_PIVOT"):
            a.action = "WATCH"
            a.size_guidance = "PILOT"
        elif a.grade in ("A+", "A") and a.phase == "FORMING":
            a.action = "WATCH"
            a.size_guidance = "NORMAL"
        elif a.grade in ("D", "F"):
            a.action = "NO_TRADE"
            a.size_guidance = "AVOID"
        else:
            a.action = "WAIT"
            a.size_guidance = "PILOT"

        # Regime override — adverse macro caps action at WATCH
        regime_trend = regime.get("trend", "") if isinstance(regime, dict) else ""
        if regime_trend in ("RISK_OFF", "DOWNTREND", "CRISIS") and a.action == "TRADE":
            a.action = "WATCH"
            a.size_guidance = "PILOT"
            a.why_not = f"Regime {regime_trend} — wait for improved conditions"

        # Numeric regime_fit cap: weak regime fit also caps at WATCH
        if context.regime_fit < 4 and a.action == "TRADE":
            a.action = "WATCH"
            a.size_guidance = "PILOT"
            if not a.why_not or a.why_not == "Clean setup":
                a.why_not = f"Regime fit too low ({context.regime_fit:.1f}/10) — wait for better conditions"

        # Laggard override
        lag = sector.leader_status == LeaderStatus.LAGGARD
        if lag and a.action == "TRADE":
            a.action = "WATCH"
            a.size_guidance = "PILOT"

        # Build explanations
        ticker = sig.get("ticker", "?")
        pivot = sig.get("pivot_price", sig.get("resistance", 0))

        if pivot > 0:
            a.entry_zone = f"Near ${pivot:.2f} pivot"
        else:
            a.entry_zone = "At pivot breakout"

        # Why now
        parts = [
            f"{ticker} VCP Grade {a.grade} ({a.phase})",
            f"Quality {quality.overall:.1f}/10",
            f"Context {context.overall:.1f}/10",
        ]
        if sector.leader_status == LeaderStatus.LEADER:
            parts.append("sector leader")
        if sector.sector_stage == SectorStage.ACCELERATION:
            parts.append("sector accelerating")
        a.why_now = " — ".join(parts)

        # Why not
        why_not_parts = []
        if quality.contraction_tightness < 6:
            why_not_parts.append("contractions not tight enough")
        if quality.volume_dry_up < 6:
            why_not_parts.append("volume not dried up at pivot")
        if context.regime_fit < 5:
            why_not_parts.append("regime not supportive")
        if context.stage_fit < 5:
            why_not_parts.append("sector stage unfavorable")
        if sector.leader_status == LeaderStatus.LAGGARD:
            why_not_parts.append("laggard — not leading the move")
        if context.event_proximity < 5:
            why_not_parts.append("earnings too close")
        if why_not_parts:
            a.why_not = "; ".join(why_not_parts)
        else:
            a.why_not = "Clean setup"

        # Invalidation
        stop = sig.get("stop_price", 0)
        if stop > 0:
            a.invalidation = f"Close below ${stop:.2f}"
        elif detection.contractions:
            a.invalidation = "Break below last contraction low"
        else:
            a.invalidation = "Break below base support"

        # Historical analogs
        if _HAS_ANALOG:
            try:
                strategy = sig.get("strategy", "vcp")
                regime_trend = regime.get("trend", "") if isinstance(regime, dict) else ""
                cases = find_similar_cases(
                    strategy=strategy,
                    regime=regime_trend,
                    grade=a.grade,
                    direction=sig.get("direction", "LONG"),
                )
                a.similar_cases = cases
            except Exception as e:
                logger.debug("Analog lookup failed: %s", e)

        return a
