"""
CC — Calibration Engine

Converts raw confidence scores into calibrated probabilities with
reliability buckets, sample-size tracking, and conformal uncertainty bands.

This replaces "confidence presentation" with "statistically grounded forecast."

Reference: scikit-learn calibration curves (reliability diagrams) + MAPIE
conformal prediction concepts.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════
# ACTION STATES — first-class decision outputs
# ═══════════════════════════════════════════════════════════════════


class ActionState:
    """Canonical action ladder — every recommendation resolves to one."""

    STRONG_BUY = "STRONG_BUY"
    BUY_SMALL = "BUY_SMALL"
    WATCH = "WATCH"
    NO_TRADE = "NO_TRADE"
    REDUCE = "REDUCE"
    HEDGE = "HEDGE"
    CLOSE = "CLOSE"

    ALL = (STRONG_BUY, BUY_SMALL, WATCH, NO_TRADE, REDUCE, HEDGE, CLOSE)

    @staticmethod
    def rank(state: str) -> int:
        """Aggressiveness rank (higher = more aggressive)."""
        _RANK = {
            "CLOSE": 0,
            "HEDGE": 1,
            "REDUCE": 2,
            "NO_TRADE": 3,
            "WATCH": 4,
            "BUY_SMALL": 5,
            "STRONG_BUY": 6,
        }
        return _RANK.get(state, 3)


# ═══════════════════════════════════════════════════════════════════
# CONFIDENCE LAYERS — the 6-layer confidence object
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ConfidenceLayers:
    """
    Six visible layers of confidence (Section 10 of review):
    1. forecast_probability  — P(target beats stop over horizon)
    2. reliability_bucket    — realized hit rate of comparable setups
    3. uncertainty_band      — interval [low, high]
    4. data_confidence       — freshness, completeness, mode
    5. execution_confidence  — liquidity, spread, session, event proximity
    6. portfolio_fit         — diversifies or concentrates the book
    """

    forecast_probability: float = 0.5
    reliability_bucket: str = "uncalibrated"
    reliability_hit_rate: float = 0.0
    reliability_sample_size: int = 0
    uncertainty_low: float = 0.3
    uncertainty_high: float = 0.7
    data_confidence: str = "unknown"  # fresh / delayed / stale / synthetic
    data_freshness_seconds: float = 0.0
    execution_confidence: str = "unknown"  # good / fair / poor
    execution_spread_bps: float = 0.0
    portfolio_fit: str = "unknown"  # diversifying / neutral / concentrating

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_probability": round(self.forecast_probability, 4),
            "reliability": {
                "bucket": self.reliability_bucket,
                "hit_rate": round(self.reliability_hit_rate, 3),
                "sample_size": self.reliability_sample_size,
            },
            "uncertainty_band": {
                "low": round(self.uncertainty_low, 3),
                "high": round(self.uncertainty_high, 3),
                "width": round(self.uncertainty_high - self.uncertainty_low, 3),
            },
            "data_confidence": self.data_confidence,
            "execution_confidence": self.execution_confidence,
            "portfolio_fit": self.portfolio_fit,
        }


# ═══════════════════════════════════════════════════════════════════
# ENHANCED SIGNAL CARD — the explanation panel
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SignalExplanation:
    """
    Full explanation panel for every signal (Section 10 of review).
    Always shows both sides of the argument.
    """

    bull_case: str = ""
    bear_case: str = ""
    biggest_risks: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)
    why_now: str = ""
    why_wait: str = ""
    what_improves_confidence: List[str] = field(default_factory=list)
    what_reduces_confidence: List[str] = field(default_factory=list)
    action_state: str = ActionState.WATCH
    pre_mortem: str = ""  # "most likely failure mode"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "biggest_risks": self.biggest_risks,
            "invalidation_conditions": self.invalidation_conditions,
            "why_now": self.why_now,
            "why_wait": self.why_wait,
            "what_improves_confidence": self.what_improves_confidence,
            "what_reduces_confidence": self.what_reduces_confidence,
            "action_state": self.action_state,
            "pre_mortem": self.pre_mortem,
        }


# ═══════════════════════════════════════════════════════════════════
# CALIBRATION ENGINE
# ═══════════════════════════════════════════════════════════════════

# Reliability bucket definitions
_BUCKETS = [
    (0.0, 0.2, "very_low"),
    (0.2, 0.4, "low"),
    (0.4, 0.6, "moderate"),
    (0.6, 0.8, "high"),
    (0.8, 1.01, "very_high"),
]

# Minimum samples before we trust a bucket's hit rate
MIN_CALIBRATION_SAMPLES = 30


@dataclass
class BucketStats:
    """Realized outcome stats for one reliability bucket."""

    total: int = 0
    wins: int = 0
    losses: int = 0
    sum_forecast: float = 0.0  # sum of forecasted probabilities
    sum_realized: float = 0.0  # sum of 1 (win) or 0 (loss)

    @property
    def hit_rate(self) -> float:
        return self.wins / self.total if self.total > 0 else 0.0

    @property
    def avg_forecast(self) -> float:
        return self.sum_forecast / self.total if self.total > 0 else 0.5

    @property
    def calibration_error(self) -> float:
        """Absolute gap between avg forecast and realized hit rate."""
        return abs(self.avg_forecast - self.hit_rate)

    @property
    def is_calibrated(self) -> bool:
        return self.total >= MIN_CALIBRATION_SAMPLES


class CalibrationEngine:
    """
    Tracks forecast-vs-outcome by bucket × regime × strategy.

    Usage:
        engine = CalibrationEngine()
        # After trade closes:
        engine.record_outcome(forecast_p=0.72, won=True, regime="bull_trending", strategy="momentum")
        # Before next trade:
        layers = engine.build_confidence(raw_score=72, regime="bull_trending", strategy="momentum", ...)
    """

    def __init__(self) -> None:
        # Nested: _stats[regime][strategy][bucket_name] = BucketStats
        self._stats: Dict[str, Dict[str, Dict[str, BucketStats]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(BucketStats))
        )
        # Global stats (all regimes/strategies)
        self._global_stats: Dict[str, BucketStats] = defaultdict(BucketStats)
        self._total_outcomes: int = 0

    # ── Outcome recording ─────────────────────────────────────

    def record_outcome(
        self,
        forecast_p: float,
        won: bool,
        regime: str = "unknown",
        strategy: str = "unknown",
    ) -> None:
        """Record a realized trade outcome for calibration tracking."""
        bucket_name = self._bucket_name(forecast_p)
        realized = 1.0 if won else 0.0

        for stats in (
            self._stats[regime][strategy][bucket_name],
            self._global_stats[bucket_name],
        ):
            stats.total += 1
            stats.wins += int(won)
            stats.losses += int(not won)
            stats.sum_forecast += forecast_p
            stats.sum_realized += realized

        self._total_outcomes += 1

    # ── Confidence builder ────────────────────────────────────

    def build_confidence(
        self,
        raw_score: float,
        regime: str = "unknown",
        strategy: str = "unknown",
        data_freshness_seconds: float = 0.0,
        data_mode: str = "live",
        spread_bps: float = 0.0,
        session_quality: str = "normal",
        event_proximity_hours: float = 999.0,
        portfolio_correlation: float = 0.0,
        portfolio_sector_count: int = 0,
    ) -> ConfidenceLayers:
        """
        Build the full 6-layer confidence object from a raw score.
        """
        forecast_p = raw_score / 100.0 if raw_score > 1.0 else raw_score
        forecast_p = max(0.01, min(0.99, forecast_p))

        bucket_name = self._bucket_name(forecast_p)

        # Layer 1: Calibrated forecast
        calibrated_p = self._calibrated_probability(
            forecast_p, bucket_name, regime, strategy
        )

        # Layer 2: Reliability bucket
        stats = self._best_stats(bucket_name, regime, strategy)
        reliability_bucket = bucket_name
        if not stats.is_calibrated:
            reliability_bucket = f"{bucket_name} (uncalibrated, n={stats.total})"

        # Layer 3: Uncertainty band (conformal-inspired)
        width = self._uncertainty_width(stats, forecast_p)
        uncertainty_low = max(0.0, calibrated_p - width / 2)
        uncertainty_high = min(1.0, calibrated_p + width / 2)

        # Layer 4: Data confidence
        data_confidence = self._assess_data_confidence(
            data_freshness_seconds, data_mode
        )

        # Layer 5: Execution confidence
        execution_confidence = self._assess_execution_confidence(
            spread_bps, session_quality, event_proximity_hours
        )

        # Layer 6: Portfolio fit
        portfolio_fit = self._assess_portfolio_fit(
            portfolio_correlation, portfolio_sector_count
        )

        return ConfidenceLayers(
            forecast_probability=calibrated_p,
            reliability_bucket=reliability_bucket,
            reliability_hit_rate=stats.hit_rate,
            reliability_sample_size=stats.total,
            uncertainty_low=uncertainty_low,
            uncertainty_high=uncertainty_high,
            data_confidence=data_confidence,
            data_freshness_seconds=data_freshness_seconds,
            execution_confidence=execution_confidence,
            execution_spread_bps=spread_bps,
            portfolio_fit=portfolio_fit,
        )

    # ── Action state resolver ─────────────────────────────────

    def resolve_action_state(
        self,
        confidence: ConfidenceLayers,
        regime_fit: float = 0.5,
        composite_score: float = 0.0,
        is_existing_position: bool = False,
        drawdown_pct: float = 0.0,
    ) -> str:
        """
        Resolve the canonical ActionState for a recommendation.
        Promotes WAIT/NO_TRADE/REDUCE/HEDGE to first-class outputs.
        """
        p = confidence.forecast_probability
        width = confidence.uncertainty_high - confidence.uncertainty_low

        # Hard vetoes → NO_TRADE
        if confidence.data_confidence == "stale":
            return ActionState.NO_TRADE
        if confidence.execution_confidence == "poor":
            return ActionState.NO_TRADE
        if confidence.reliability_sample_size < 10 and p < 0.6:
            return ActionState.WATCH

        # Existing position management
        if is_existing_position:
            if drawdown_pct > 0.10:
                return ActionState.REDUCE
            if confidence.data_confidence == "delayed" and p < 0.5:
                return ActionState.HEDGE
            return ActionState.WATCH

        # New entry decisions
        if p >= 0.70 and width < 0.25 and regime_fit >= 0.6:
            return ActionState.STRONG_BUY
        if p >= 0.55 and width < 0.35:
            return ActionState.BUY_SMALL
        if p >= 0.45:
            return ActionState.WATCH
        return ActionState.NO_TRADE

    # ── Calibration diagnostics ───────────────────────────────

    def calibration_report(self) -> Dict[str, Any]:
        """Return calibration diagnostics for dashboard display."""
        report = {
            "total_outcomes": self._total_outcomes,
            "buckets": {},
        }
        for bname in ("very_low", "low", "moderate", "high", "very_high"):
            stats = self._global_stats[bname]
            report["buckets"][bname] = {
                "sample_size": stats.total,
                "avg_forecast": round(stats.avg_forecast, 3),
                "realized_hit_rate": round(stats.hit_rate, 3),
                "calibration_error": round(stats.calibration_error, 3),
                "is_calibrated": stats.is_calibrated,
            }
        return report

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _bucket_name(p: float) -> str:
        for lo, hi, name in _BUCKETS:
            if lo <= p < hi:
                return name
        return "very_high"

    def _best_stats(self, bucket: str, regime: str, strategy: str) -> BucketStats:
        """Prefer regime+strategy stats if calibrated, else fall back to global."""
        specific = self._stats[regime][strategy][bucket]
        if specific.is_calibrated:
            return specific
        return self._global_stats[bucket]

    def _calibrated_probability(
        self, raw_p: float, bucket: str, regime: str, strategy: str
    ) -> float:
        """Adjust raw forecast toward realized hit rate when calibrated."""
        stats = self._best_stats(bucket, regime, strategy)
        if not stats.is_calibrated:
            # Not enough data — shrink toward 0.5 (conservative)
            shrinkage = min(1.0, stats.total / MIN_CALIBRATION_SAMPLES)
            return raw_p * shrinkage + 0.5 * (1 - shrinkage)
        # Calibrated: blend raw with realized
        return 0.6 * stats.hit_rate + 0.4 * raw_p

    def _uncertainty_width(self, stats: BucketStats, raw_p: float) -> float:
        """
        Conformal-inspired uncertainty width.
        Wider when: fewer samples, mid-range probability, uncalibrated.
        """
        # Base width from sample size (Wilson interval approximation)
        n = max(1, stats.total)
        base_width = 1.96 * math.sqrt(raw_p * (1 - raw_p) / n)

        # Floor: never narrower than this (honesty)
        min_width = 0.15 if stats.is_calibrated else 0.30
        return max(min_width, min(0.80, base_width))

    @staticmethod
    def _assess_data_confidence(freshness_seconds: float, mode: str) -> str:
        if mode == "synthetic":
            return "synthetic"
        if freshness_seconds > 900:  # 15 min
            return "stale"
        if freshness_seconds > 300:  # 5 min
            return "delayed"
        return "fresh"

    @staticmethod
    def _assess_execution_confidence(
        spread_bps: float,
        session_quality: str,
        event_proximity_hours: float,
    ) -> str:
        if spread_bps > 50 or event_proximity_hours < 2:
            return "poor"
        if spread_bps > 20 or session_quality == "pre_market":
            return "fair"
        return "good"

    @staticmethod
    def _assess_portfolio_fit(
        correlation: float,
        sector_count: int,
    ) -> str:
        if correlation > 0.7 or sector_count > 3:
            return "concentrating"
        if correlation < 0.3:
            return "diversifying"
        return "neutral"


# ── Module-level singleton ────────────────────────────────────
_calibration_engine: Optional[CalibrationEngine] = None


def get_calibration_engine() -> CalibrationEngine:
    """Get or create the singleton CalibrationEngine."""
    global _calibration_engine
    if _calibration_engine is None:
        _calibration_engine = CalibrationEngine()
    return _calibration_engine
