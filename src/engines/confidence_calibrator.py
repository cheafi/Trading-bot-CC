"""
Confidence Calibrator — Sprint 52
===================================
Maps raw model scores to historically-honest probability estimates.

Problem: A "75% confidence" from a model rarely means the signal
is correct 75% of the time. Most systems have uncalibrated confidence.

Solution: Track predicted confidence vs actual outcomes, then build
a calibration curve that maps raw scores to empirical probabilities.

This prevents fake precision and builds genuine trust.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CalibrationBin:
    """One bin in the calibration curve."""

    bin_lower: float
    bin_upper: float
    predicted_avg: float
    actual_rate: float
    count: int
    calibration_error: float  # |predicted - actual|


@dataclass
class CalibrationReport:
    """Output of calibration analysis."""

    is_calibrated: bool
    total_observations: int
    expected_calibration_error: float  # ECE
    bins: list[dict] = field(default_factory=list)
    adjustment_map: dict = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "is_calibrated": self.is_calibrated,
            "total_observations": self.total_observations,
            "expected_calibration_error": (self.expected_calibration_error),
            "bins": self.bins,
            "adjustment_map": self.adjustment_map,
            "recommendation": self.recommendation,
        }


class ConfidenceCalibrator:
    """
    Tracks confidence vs outcomes and produces calibrated estimates.

    Usage:
        cal = ConfidenceCalibrator()
        # Record historical predictions
        cal.record(predicted=0.80, was_correct=True)
        cal.record(predicted=0.80, was_correct=False)
        # Get calibrated confidence
        calibrated = cal.calibrate(raw_confidence=0.80)
    """

    N_BINS = 10
    MIN_OBSERVATIONS = 20  # Need this many before calibrating

    def __init__(self):
        self._predictions: list[tuple[float, bool]] = []

    def record(
        self,
        predicted: float,
        was_correct: bool,
    ) -> None:
        """Record a prediction and its outcome."""
        self._predictions.append((max(0.0, min(1.0, predicted)), was_correct))

    def calibrate(self, raw_confidence: float) -> float:
        """
        Map a raw confidence to a calibrated probability.

        If not enough data, returns the raw confidence with
        a conservative discount.
        """
        if len(self._predictions) < self.MIN_OBSERVATIONS:
            # Conservative: pull toward 50% (shrinkage)
            return round(0.5 + (raw_confidence - 0.5) * 0.6, 3)

        # Find the bin for this raw confidence
        report = self.analyse()
        adj = report.adjustment_map

        # Find nearest bin
        raw = max(0.0, min(1.0, raw_confidence))
        bin_key = f"{int(raw * self.N_BINS) / self.N_BINS:.1f}"

        if bin_key in adj:
            return adj[bin_key]

        # Fallback: conservative shrinkage
        return round(0.5 + (raw - 0.5) * 0.7, 3)

    def analyse(self) -> CalibrationReport:
        """Produce full calibration analysis."""
        n = len(self._predictions)
        if n < self.MIN_OBSERVATIONS:
            return CalibrationReport(
                is_calibrated=False,
                total_observations=n,
                expected_calibration_error=0.0,
                recommendation=(
                    f"Need {self.MIN_OBSERVATIONS - n} more "
                    f"observations to calibrate"
                ),
            )

        # Bin predictions
        bins_data: dict[int, list[tuple[float, bool]]] = defaultdict(list)
        for pred, correct in self._predictions:
            b = min(
                self.N_BINS - 1,
                int(pred * self.N_BINS),
            )
            bins_data[b].append((pred, correct))

        bins: list[CalibrationBin] = []
        adjustment_map: dict[str, float] = {}
        ece = 0.0

        for b in range(self.N_BINS):
            lower = b / self.N_BINS
            upper = (b + 1) / self.N_BINS
            items = bins_data.get(b, [])

            if not items:
                bins.append(
                    CalibrationBin(
                        bin_lower=lower,
                        bin_upper=upper,
                        predicted_avg=lower + 0.05,
                        actual_rate=0.5,
                        count=0,
                        calibration_error=0.0,
                    )
                )
                adjustment_map[f"{lower:.1f}"] = round(lower + 0.05, 3)
                continue

            pred_avg = sum(p for p, _ in items) / len(items)
            actual_rate = sum(1 for _, c in items if c) / len(items)
            error = abs(pred_avg - actual_rate)
            ece += error * len(items) / n

            bins.append(
                CalibrationBin(
                    bin_lower=lower,
                    bin_upper=upper,
                    predicted_avg=round(pred_avg, 3),
                    actual_rate=round(actual_rate, 3),
                    count=len(items),
                    calibration_error=round(error, 3),
                )
            )
            # Map raw → calibrated
            adjustment_map[f"{lower:.1f}"] = round(actual_rate, 3)

        return CalibrationReport(
            is_calibrated=True,
            total_observations=n,
            expected_calibration_error=round(ece, 4),
            bins=[
                {
                    "range": f"{b.bin_lower:.1f}-{b.bin_upper:.1f}",
                    "predicted_avg": b.predicted_avg,
                    "actual_rate": b.actual_rate,
                    "count": b.count,
                    "calibration_error": b.calibration_error,
                }
                for b in bins
            ],
            adjustment_map=adjustment_map,
            recommendation=(
                "Well calibrated"
                if ece < 0.05
                else (
                    "Moderately calibrated"
                    if ece < 0.10
                    else "Poorly calibrated — confidence values unreliable"
                )
            ),
        )

    @property
    def observation_count(self) -> int:
        return len(self._predictions)

    def summary(self) -> dict:
        report = self.analyse()
        return {
            "observations": self.observation_count,
            "is_calibrated": report.is_calibrated,
            "ece": report.expected_calibration_error,
            "recommendation": report.recommendation,
        }
