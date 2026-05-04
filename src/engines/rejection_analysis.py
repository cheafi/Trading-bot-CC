"""
Rejection Analysis Engine.

Analyzes rejected/avoided signals to find:
  1. Confidence disagreement patterns (when models disagree)
  2. Rejection reason clustering (what categories dominate)
  3. False-negative detection (signals that were rejected but would have won)
  4. Rule tuning recommendations based on rejection outcomes
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RejectionRecord:
    """A single rejected signal with context."""
    ticker: str
    strategy: str
    direction: str
    confidence: float
    rejection_reasons: List[str] = field(default_factory=list)
    rejection_category: str = "unknown"  # timing, liquidity, earnings, regime, conflict, data
    regime_at_rejection: str = ""
    timestamp: str = ""
    # Outcome tracking (filled later)
    actual_return_5d: Optional[float] = None
    actual_return_10d: Optional[float] = None
    actual_return_20d: Optional[float] = None
    was_false_negative: bool = False  # would have been a winner

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy": self.strategy,
            "direction": self.direction,
            "confidence": self.confidence,
            "rejection_reasons": self.rejection_reasons,
            "rejection_category": self.rejection_category,
            "regime_at_rejection": self.regime_at_rejection,
            "timestamp": self.timestamp,
            "actual_return_5d": self.actual_return_5d,
            "actual_return_10d": self.actual_return_10d,
            "actual_return_20d": self.actual_return_20d,
            "was_false_negative": self.was_false_negative,
        }


@dataclass
class ConfidenceDisagreement:
    """When two confidence sources disagree on a signal."""
    ticker: str
    strategy_confidence: float  # from signal engine
    ensemble_confidence: float  # from opportunity ensembler
    gpt_confidence: Optional[float] = None  # from GPT validator
    disagreement_magnitude: float = 0.0
    direction: str = ""  # "overconfident" or "underconfident"
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy_confidence": round(self.strategy_confidence, 2),
            "ensemble_confidence": round(self.ensemble_confidence, 2),
            "gpt_confidence": round(self.gpt_confidence, 2) if self.gpt_confidence is not None else None,
            "disagreement_magnitude": round(self.disagreement_magnitude, 2),
            "direction": self.direction,
            "explanation": self.explanation,
        }


@dataclass
class RejectionAnalysis:
    """Complete rejection analysis result."""
    total_rejections: int = 0
    rejection_categories: Dict[str, int] = field(default_factory=dict)
    false_negative_rate: float = 0.0  # % of rejections that would have won
    false_negative_cost: float = 0.0  # total missed return %
    top_rejection_reasons: List[Dict[str, Any]] = field(default_factory=list)
    confidence_disagreements: List[Dict[str, Any]] = field(default_factory=list)
    rule_recommendations: List[str] = field(default_factory=list)
    regime_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rejections": self.total_rejections,
            "rejection_categories": self.rejection_categories,
            "false_negative_rate": round(self.false_negative_rate, 1),
            "false_negative_cost": round(self.false_negative_cost, 2),
            "top_rejection_reasons": self.top_rejection_reasons,
            "confidence_disagreements": self.confidence_disagreements,
            "rule_recommendations": self.rule_recommendations,
            "regime_breakdown": self.regime_breakdown,
        }


class RejectionAnalysisEngine:
    """
    Analyzes rejected signals to improve the decision pipeline.

    Tracks rejections, checks outcomes, and recommends rule adjustments.
    """

    def __init__(self):
        self._rejections: List[RejectionRecord] = []
        self._disagreements: List[ConfidenceDisagreement] = []

    def record_rejection(self, record: RejectionRecord):
        """Record a rejected signal for analysis."""
        record.rejection_category = self._categorize(record.rejection_reasons)
        self._rejections.append(record)

    def record_disagreement(self, disagreement: ConfidenceDisagreement):
        """Record a confidence disagreement between sources."""
        self._disagreements.append(disagreement)

    def update_outcome(
        self,
        ticker: str,
        actual_return_5d: Optional[float] = None,
        actual_return_10d: Optional[float] = None,
        actual_return_20d: Optional[float] = None,
    ):
        """Update outcome for a previously rejected signal.

        Called after the fact (e.g., at EOD or next cycle) to fill in
        what actually happened to a rejected ticker.  Marks false
        negatives when the rejected signal would have been a winner.
        """
        for rec in self._rejections:
            if rec.ticker == ticker and rec.actual_return_5d is None:
                if actual_return_5d is not None:
                    rec.actual_return_5d = actual_return_5d
                if actual_return_10d is not None:
                    rec.actual_return_10d = actual_return_10d
                if actual_return_20d is not None:
                    rec.actual_return_20d = actual_return_20d
                # A rejected signal that would have returned >2% in 5d
                # is considered a false negative
                if rec.actual_return_5d is not None and rec.actual_return_5d > 2.0:
                    rec.was_false_negative = True

    def analyze(self) -> RejectionAnalysis:
        """Run full rejection analysis on accumulated data."""
        result = RejectionAnalysis()
        result.total_rejections = len(self._rejections)

        if not self._rejections:
            result.rule_recommendations = ["No rejections to analyze yet."]
            return result

        # Category breakdown
        categories: Dict[str, int] = defaultdict(int)
        for r in self._rejections:
            categories[r.rejection_category] += 1
        result.rejection_categories = dict(sorted(
            categories.items(), key=lambda x: x[1], reverse=True
        ))

        # Top rejection reasons
        reason_counts: Dict[str, int] = defaultdict(int)
        for r in self._rejections:
            for reason in r.rejection_reasons:
                reason_counts[reason] += 1
        result.top_rejection_reasons = [
            {"reason": k, "count": v, "pct": round(v / len(self._rejections) * 100, 1)}
            for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # False negative analysis
        fn_count = sum(1 for r in self._rejections if r.was_false_negative)
        result.false_negative_rate = (fn_count / len(self._rejections)) * 100

        # Missed return cost
        missed_returns = []
        for r in self._rejections:
            if r.was_false_negative and r.actual_return_5d is not None:
                missed_returns.append(r.actual_return_5d)
        result.false_negative_cost = sum(missed_returns)

        # Regime breakdown
        regime_cats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in self._rejections:
            regime = r.regime_at_rejection or "unknown"
            regime_cats[regime][r.rejection_category] += 1
        result.regime_breakdown = {
            k: dict(v) for k, v in regime_cats.items()
        }

        # Confidence disagreements
        result.confidence_disagreements = [
            d.to_dict() for d in self._disagreements[-20:]  # last 20
        ]

        # Rule recommendations
        result.rule_recommendations = self._generate_recommendations(
            result, categories, fn_count
        )

        return result

    def _categorize(self, reasons: List[str]) -> str:
        """Categorize rejection reasons into broad categories."""
        reason_text = " ".join(reasons).lower()
        if any(k in reason_text for k in ["timing", "extended", "overbought", "late"]):
            return "timing"
        if any(k in reason_text for k in ["liquidity", "volume", "thin", "spread"]):
            return "liquidity"
        if any(k in reason_text for k in ["earnings", "event", "binary", "fomc"]):
            return "earnings"
        if any(k in reason_text for k in ["regime", "risk_off", "no_trade", "vix"]):
            return "regime"
        if any(k in reason_text for k in ["conflict", "crowded", "consensus"]):
            return "conflict"
        if any(k in reason_text for k in ["data", "stale", "missing"]):
            return "data"
        if any(k in reason_text for k in ["score", "weak", "low"]):
            return "weak_setup"
        return "other"

    def _generate_recommendations(
        self,
        result: RejectionAnalysis,
        categories: Dict[str, int],
        fn_count: int,
    ) -> List[str]:
        """Generate actionable rule tuning recommendations."""
        recs = []
        total = result.total_rejections

        # High false negative rate
        if result.false_negative_rate > 20:
            recs.append(
                f"HIGH FALSE NEGATIVE RATE ({result.false_negative_rate:.0f}%): "
                f"Consider relaxing rejection rules — {fn_count} rejected signals "
                f"would have been winners. Missed return: {result.false_negative_cost:.1f}%"
            )

        # Timing rejections dominate
        timing_pct = categories.get("timing", 0) / max(total, 1) * 100
        if timing_pct > 30:
            recs.append(
                f"TIMING REJECTIONS DOMINATE ({timing_pct:.0f}%): "
                "Consider adding a 'late entry' mode that allows smaller positions "
                "on strong setups even when timing is suboptimal."
            )

        # Regime rejections in specific regimes
        for regime, cats in result.regime_breakdown.items():
            regime_total = sum(cats.values())
            if regime_total > 5 and cats.get("regime", 0) / regime_total > 0.5:
                recs.append(
                    f"REGIME '{regime}' blocks many signals: "
                    "Consider regime-conditional relaxation for A+ setups."
                )

        # Conflict rejections
        conflict_pct = categories.get("conflict", 0) / max(total, 1) * 100
        if conflict_pct > 15:
            recs.append(
                f"CONFLICT REJECTIONS HIGH ({conflict_pct:.0f}%): "
                "When bullish+bearish signals conflict, consider keeping the "
                "higher-confidence direction instead of rejecting both."
            )

        # Confidence disagreement pattern
        if len(self._disagreements) > 5:
            overconfident = sum(
                1 for d in self._disagreements if d.direction == "overconfident"
            )
            if overconfident > len(self._disagreements) * 0.6:
                recs.append(
                    "STRATEGY OVERCONFIDENCE PATTERN: Strategy confidence "
                    "consistently exceeds ensemble confidence. Consider "
                    "applying a confidence dampener to raw strategy scores."
                )

        if not recs:
            recs.append("Rejection patterns look healthy — no rule changes recommended.")

        return recs
