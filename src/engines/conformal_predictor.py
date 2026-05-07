"""Conformal prediction — uncertainty bands for every recommendation.

Implements split-conformal prediction intervals using historical residuals.
Each signal gets a prediction interval (lower, upper) at a chosen confidence
level (default 90 %).  This lets the UI show "price likely between $X and $Y"
instead of a single point target.

Reference: Vovk, Gammerman & Shafer — *Algorithmic Learning in a Random World*.
scikit-learn compatible; MAPIE-inspired but dependency-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

__all__ = ["ConformalPredictor", "PredictionInterval"]


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PredictionInterval:
    """A single prediction interval for a price target."""

    point: float  # point forecast (e.g. target price)
    lower: float  # lower bound
    upper: float  # upper bound
    confidence_level: float  # e.g. 0.90
    method: str = "split_conformal"
    sample_size: int = 0  # calibration set size
    coverage_note: str = ""  # human-readable reliability note

    def width(self) -> float:
        return self.upper - self.lower

    def width_pct(self) -> float:
        """Width as percentage of point forecast."""
        return (self.width() / self.point * 100) if self.point else 0.0

    def to_dict(self) -> dict:
        return {
            "point": round(self.point, 2),
            "lower": round(self.lower, 2),
            "upper": round(self.upper, 2),
            "confidence_level": self.confidence_level,
            "width_pct": round(self.width_pct(), 2),
            "method": self.method,
            "sample_size": self.sample_size,
            "coverage_note": self.coverage_note,
        }


# ═══════════════════════════════════════════════════════════════
# Reliability buckets
# ═══════════════════════════════════════════════════════════════


def reliability_bucket(sample_size: int) -> str:
    """Assign a human-readable reliability bucket based on sample size."""
    if sample_size >= 200:
        return "HIGH"
    if sample_size >= 50:
        return "MODERATE"
    if sample_size >= 20:
        return "LOW"
    return "EXPERIMENTAL"


def reliability_note(sample_size: int) -> str:
    """Human-readable note about reliability."""
    bucket = reliability_bucket(sample_size)
    return {
        "HIGH": f"Based on {sample_size} observations — statistically robust",
        "MODERATE": f"Based on {sample_size} observations — reasonable confidence",
        "LOW": f"Based on {sample_size} observations — treat with caution",
        "EXPERIMENTAL": f"Only {sample_size} observations — highly uncertain",
    }[bucket]


# ═══════════════════════════════════════════════════════════════
# Conformal predictor
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConformalPredictor:
    """Split-conformal predictor for price targets.

    Usage:
        cp = ConformalPredictor()
        cp.calibrate(historical_targets, historical_actuals)
        interval = cp.predict(target_price=150.0)
    """

    confidence_level: float = 0.90
    _residuals: np.ndarray = field(default_factory=lambda: np.array([]))
    _quantile: float = 0.0
    _calibrated: bool = False

    # ── Calibrate from historical residuals ──────────────────

    def calibrate(
        self,
        predicted: Sequence[float],
        actual: Sequence[float],
    ) -> None:
        """Calibrate using historical predicted vs actual values.

        Args:
            predicted: historical point forecasts (e.g. target prices)
            actual: corresponding realized prices
        """
        pred = np.asarray(predicted, dtype=float)
        act = np.asarray(actual, dtype=float)
        if len(pred) < 5:
            self._calibrated = False
            return

        # Absolute residuals (non-conformity scores)
        self._residuals = np.abs(act - pred)

        # Conformal quantile with finite-sample correction
        n = len(self._residuals)
        alpha = 1.0 - self.confidence_level
        q = min(math.ceil((n + 1) * (1 - alpha)) / n, 1.0)
        self._quantile = float(np.quantile(self._residuals, q))
        self._calibrated = True

    def calibrate_from_returns(
        self,
        close_prices: Sequence[float],
        horizon_days: int = 20,
    ) -> None:
        """Calibrate from a price series by computing forward returns.

        Uses the close series to build pseudo-predictions (close[i])
        vs pseudo-actuals (close[i + horizon]) and calibrates on residuals.
        """
        c = np.asarray(close_prices, dtype=float)
        if len(c) < horizon_days + 20:
            self._calibrated = False
            return

        # Pseudo-forecast: use SMA20 as naive predictor
        sma = np.convolve(c, np.ones(20) / 20, mode="valid")
        # Align: sma[i] predicts c[i + 19 + horizon_days]
        n_pairs = min(len(sma), len(c) - 19 - horizon_days)
        if n_pairs < 10:
            self._calibrated = False
            return

        predicted = sma[:n_pairs]
        actual = c[19 + horizon_days : 19 + horizon_days + n_pairs]
        self.calibrate(predicted, actual)

    # ── Predict ──────────────────────────────────────────────

    def predict(self, target_price: float) -> PredictionInterval:
        """Generate a prediction interval around a point forecast."""
        n = len(self._residuals)

        if not self._calibrated or n < 5:
            # Fallback: use ±5 % of target
            fallback_w = target_price * 0.05
            return PredictionInterval(
                point=target_price,
                lower=round(target_price - fallback_w, 2),
                upper=round(target_price + fallback_w, 2),
                confidence_level=self.confidence_level,
                method="fallback_5pct",
                sample_size=n,
                coverage_note=reliability_note(n),
            )

        return PredictionInterval(
            point=target_price,
            lower=round(target_price - self._quantile, 2),
            upper=round(target_price + self._quantile, 2),
            confidence_level=self.confidence_level,
            method="split_conformal",
            sample_size=n,
            coverage_note=reliability_note(n),
        )

    # ── Convenience ──────────────────────────────────────────

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    @property
    def sample_size(self) -> int:
        return len(self._residuals)

    def summary(self) -> dict:
        return {
            "calibrated": self._calibrated,
            "confidence_level": self.confidence_level,
            "sample_size": self.sample_size,
            "reliability": reliability_bucket(self.sample_size),
            "quantile_width": round(self._quantile, 4) if self._calibrated else None,
        }
