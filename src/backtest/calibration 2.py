"""
Confidence Calibration Checker (Phase E)

Answers: "When the system says 70% confidence, does it win ~70% of the time?"

Buckets trades by confidence decile, computes actual win rate per bucket,
and reports calibration error (Brier score, reliability diagram data).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBucket:
    """One bucket in the calibration curve."""

    confidence_lo: float
    confidence_hi: float
    predicted_prob: float  # mean confidence in bucket
    actual_win_rate: float  # actual fraction of winners
    count: int
    avg_pnl_pct: float
    calibration_error: float  # |predicted - actual|


@dataclass
class CalibrationReport:
    """Full calibration report."""

    buckets: List[CalibrationBucket]
    brier_score: float  # lower = better calibrated
    ece: float  # expected calibration error
    mce: float  # max calibration error
    overconfident: bool  # predicted > actual overall?
    total_trades: int
    recommendation: str

    def summary(self) -> str:
        lines = [
            "Confidence Calibration Report",
            "=" * 40,
            f"Total trades: {self.total_trades}",
            f"Brier score: {self.brier_score:.4f} (lower=better, perfect=0)",
            f"ECE: {self.ece:.4f}",
            f"MCE: {self.mce:.4f}",
            f"Tendency: {'OVERCONFIDENT' if self.overconfident else 'UNDERCONFIDENT'}",
            "",
            f"{'Conf Range':>12} {'Predicted':>10} {'Actual':>10} {'Count':>6} {'Error':>8}",
            "-" * 50,
        ]
        for b in self.buckets:
            lines.append(
                f"{b.confidence_lo:.0%}-{b.confidence_hi:.0%}"
                f"  {b.predicted_prob:>8.1%}"
                f"  {b.actual_win_rate:>8.1%}"
                f"  {b.count:>6}"
                f"  {b.calibration_error:>8.4f}"
            )
        lines.append("")
        lines.append(f"Recommendation: {self.recommendation}")
        return "\n".join(lines)


class ConfidenceCalibrator:
    """
    Checks whether confidence scores are well-calibrated.

    Usage:
        calibrator = ConfidenceCalibrator()
        report = calibrator.calibrate(trades_with_confidence)
        print(report.summary())
    """

    def __init__(self, n_buckets: int = 5):
        self.n_buckets = n_buckets

    def calibrate(
        self,
        trades: List[Dict[str, Any]],
        confidence_key: str = "confidence",
        outcome_key: str = "pnl_pct",
    ) -> CalibrationReport:
        """
        Calibrate confidence scores against actual outcomes.

        Args:
            trades: List of dicts with at least confidence and pnl fields.
                    Each dict needs: {confidence: float, pnl_pct: float}
            confidence_key: Key for confidence value (0-1)
            outcome_key: Key for P&L percentage

        Returns:
            CalibrationReport with buckets, Brier score, ECE, MCE
        """
        if not trades:
            return CalibrationReport(
                buckets=[],
                brier_score=1.0,
                ece=1.0,
                mce=1.0,
                overconfident=True,
                total_trades=0,
                recommendation="No trades to calibrate",
            )

        confidences = np.array([t[confidence_key] for t in trades])
        outcomes = np.array([1.0 if t[outcome_key] > 0 else 0.0 for t in trades])
        pnls = np.array([t[outcome_key] for t in trades])

        # Brier score = mean((confidence - outcome)^2)
        brier = float(np.mean((confidences - outcomes) ** 2))

        # Build calibration buckets
        edges = np.linspace(0, 1, self.n_buckets + 1)
        buckets = []
        weighted_errors = []

        for i in range(self.n_buckets):
            lo, hi = edges[i], edges[i + 1]
            mask = (confidences >= lo) & (
                confidences < hi if i < self.n_buckets - 1 else confidences <= hi
            )
            count = int(mask.sum())

            if count == 0:
                buckets.append(
                    CalibrationBucket(
                        confidence_lo=lo,
                        confidence_hi=hi,
                        predicted_prob=(lo + hi) / 2,
                        actual_win_rate=0,
                        count=0,
                        avg_pnl_pct=0,
                        calibration_error=0,
                    )
                )
                continue

            pred = float(confidences[mask].mean())
            actual = float(outcomes[mask].mean())
            avg_pnl = float(pnls[mask].mean())
            error = abs(pred - actual)

            buckets.append(
                CalibrationBucket(
                    confidence_lo=lo,
                    confidence_hi=hi,
                    predicted_prob=pred,
                    actual_win_rate=actual,
                    count=count,
                    avg_pnl_pct=avg_pnl,
                    calibration_error=error,
                )
            )
            weighted_errors.append((count, error))

        # ECE = weighted average of |predicted - actual|
        total = sum(c for c, _ in weighted_errors) if weighted_errors else 1
        ece = sum(c * e for c, e in weighted_errors) / total if weighted_errors else 0
        mce = max((e for _, e in weighted_errors), default=0)

        # Overall tendency
        overconfident = float(confidences.mean()) > float(outcomes.mean())

        # Recommendation
        if brier < 0.15:
            rec = "GOOD: Confidence scores are well-calibrated."
        elif brier < 0.25:
            if overconfident:
                rec = "MODERATE: System is overconfident. Consider scaling confidence down by 10-20%."
            else:
                rec = "MODERATE: System is underconfident. Confidence scores could be raised."
        else:
            rec = "POOR: Confidence scores are unreliable. Retrain or recalibrate the scoring model."

        return CalibrationReport(
            buckets=buckets,
            brier_score=brier,
            ece=ece,
            mce=mce,
            overconfident=overconfident,
            total_trades=len(trades),
            recommendation=rec,
        )

    def recalibrate(
        self,
        trades: List[Dict[str, Any]],
        confidence_key: str = "confidence",
        outcome_key: str = "pnl_pct",
    ) -> Dict[str, float]:
        """
        Build a simple recalibration map: for each confidence decile,
        return what the adjusted confidence should be (= actual win rate).

        Returns:
            Dict mapping "0.6-0.8" → 0.55 (meaning 60-80% confidence
            should be adjusted to 55%)
        """
        report = self.calibrate(trades, confidence_key, outcome_key)
        mapping = {}
        for b in report.buckets:
            if b.count > 0:
                key = f"{b.confidence_lo:.1f}-{b.confidence_hi:.1f}"
                mapping[key] = b.actual_win_rate
        return mapping
