"""
Rejection Tracker — Rejected ideas & why-not-stronger surface (Sprint 71)
=========================================================================

Tracks every stock the system evaluated but chose NOT to recommend,
with explicit reasoning and counterfactuals. This is an active
intelligence surface, not a graveyard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RejectionRecord:
    """A single rejected idea with full reasoning."""
    ticker: str
    rejected_at: str = ""
    strategy: str = ""
    direction: str = ""  # "LONG" or "SHORT"

    # Why rejected
    rejection_reasons: List[str] = field(default_factory=list)
    failed_criteria: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    # What was close
    near_miss_score: float = 0.0  # 0–100, how close to passing
    passing_criteria: List[str] = field(default_factory=list)

    # Counterfactual — what would need to change
    counterfactuals: List[str] = field(default_factory=list)

    # Market context at rejection
    regime: str = ""
    sector_context: str = ""

    # Peer comparison weakness
    peer_weaknesses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "rejected_at": self.rejected_at,
            "strategy": self.strategy,
            "direction": self.direction,
            "rejection_reasons": self.rejection_reasons,
            "failed_criteria": self.failed_criteria,
            "risk_factors": self.risk_factors,
            "near_miss_score": round(self.near_miss_score, 1),
            "passing_criteria": self.passing_criteria,
            "counterfactuals": self.counterfactuals,
            "regime": self.regime,
            "sector_context": self.sector_context,
            "peer_weaknesses": self.peer_weaknesses,
        }


@dataclass
class RejectionSummary:
    """Aggregate rejection intelligence."""
    total_evaluated: int = 0
    total_rejected: int = 0
    total_actionable: int = 0
    rejection_rate: float = 0.0

    # Common rejection patterns
    top_rejection_reasons: List[Dict[str, Any]] = field(default_factory=list)

    # Near-misses that could become actionable
    near_misses: List[RejectionRecord] = field(default_factory=list)

    # All rejections
    rejections: List[RejectionRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "total_rejected": self.total_rejected,
            "total_actionable": self.total_actionable,
            "rejection_rate": round(self.rejection_rate, 3),
            "top_rejection_reasons": self.top_rejection_reasons,
            "near_misses": [r.to_dict() for r in self.near_misses],
            "rejections": [r.to_dict() for r in self.rejections],
        }


class RejectionTracker:
    """Track and analyze rejected ideas.

    Usage::

        tracker = RejectionTracker()
        tracker.record_rejection(
            ticker="XYZ",
            reasons=["RS rank below threshold", "No catalyst within 30d"],
            failed_criteria=["momentum_score >= 0.6"],
            counterfactuals=["Would become actionable if RS rank improves to top 20%"],
        )
        summary = tracker.get_summary()
    """

    def __init__(self):
        self._rejections: List[RejectionRecord] = []
        self._reason_counts: Dict[str, int] = {}

    def record_rejection(
        self,
        ticker: str,
        *,
        reasons: Optional[List[str]] = None,
        failed_criteria: Optional[List[str]] = None,
        risk_factors: Optional[List[str]] = None,
        passing_criteria: Optional[List[str]] = None,
        counterfactuals: Optional[List[str]] = None,
        strategy: str = "",
        direction: str = "",
        regime: str = "",
        sector_context: str = "",
        peer_weaknesses: Optional[List[str]] = None,
        near_miss_score: float = 0.0,
    ) -> RejectionRecord:
        """Record a rejected idea."""
        now = datetime.now(timezone.utc).isoformat()
        record = RejectionRecord(
            ticker=ticker,
            rejected_at=now,
            strategy=strategy,
            direction=direction,
            rejection_reasons=reasons or [],
            failed_criteria=failed_criteria or [],
            risk_factors=risk_factors or [],
            near_miss_score=near_miss_score,
            passing_criteria=passing_criteria or [],
            counterfactuals=counterfactuals or [],
            regime=regime,
            sector_context=sector_context,
            peer_weaknesses=peer_weaknesses or [],
        )
        self._rejections.append(record)

        # Track reason frequency
        for r in record.rejection_reasons:
            self._reason_counts[r] = self._reason_counts.get(r, 0) + 1

        return record

    def record_from_signal_eval(
        self,
        ticker: str,
        signal: Dict[str, Any],
        decision: Dict[str, Any],
        explanation: Optional[Dict[str, Any]] = None,
    ) -> RejectionRecord:
        """Record rejection from a signal evaluation that was rejected."""
        explanation = explanation or {}
        return self.record_rejection(
            ticker=ticker,
            reasons=explanation.get("key_contradiction", []),
            failed_criteria=self._extract_failed_criteria(decision),
            risk_factors=explanation.get("invalidation", "").split(". ")
            if explanation.get("invalidation") else [],
            passing_criteria=explanation.get("key_evidence", []),
            counterfactuals=self._build_counterfactuals(explanation, decision),
            strategy=signal.get("strategy", ""),
            direction=signal.get("direction", ""),
            regime=signal.get("regime", ""),
            sector_context=signal.get("sector", ""),
            near_miss_score=decision.get("confidence", 0) * 100,
        )

    def get_summary(
        self, total_evaluated: Optional[int] = None
    ) -> RejectionSummary:
        """Get aggregate rejection intelligence."""
        summary = RejectionSummary()
        summary.rejections = list(self._rejections)
        summary.total_rejected = len(self._rejections)
        summary.total_evaluated = total_evaluated or len(self._rejections)

        if summary.total_evaluated > 0:
            summary.rejection_rate = (
                summary.total_rejected / summary.total_evaluated
            )
        summary.total_actionable = (
            summary.total_evaluated - summary.total_rejected
        )

        # Top rejection reasons
        sorted_reasons = sorted(
            self._reason_counts.items(), key=lambda x: x[1], reverse=True
        )
        summary.top_rejection_reasons = [
            {"reason": r, "count": c} for r, c in sorted_reasons[:10]
        ]

        # Near-misses (score >= 50)
        summary.near_misses = [
            r for r in self._rejections if r.near_miss_score >= 50
        ]
        summary.near_misses.sort(
            key=lambda r: r.near_miss_score, reverse=True
        )

        return summary

    def get_rejections_for_ticker(self, ticker: str) -> List[RejectionRecord]:
        """Get all rejections for a specific ticker."""
        return [r for r in self._rejections if r.ticker == ticker]

    def _extract_failed_criteria(self, decision: Dict) -> List[str]:
        """Extract failed criteria from decision data."""
        failed = []
        gates = decision.get("gates", {})
        for gate_name, gate_val in gates.items():
            if isinstance(gate_val, dict) and not gate_val.get("passed", True):
                failed.append(
                    f"{gate_name}: {gate_val.get('reason', 'failed')}"
                )
            elif isinstance(gate_val, bool) and not gate_val:
                failed.append(f"{gate_name}: gate failed")
        return failed

    def _build_counterfactuals(
        self, explanation: Dict, decision: Dict
    ) -> List[str]:
        """Build counterfactual statements — what would need to change."""
        counterfactuals = []

        # From why_not_stronger
        why_not = explanation.get("why_not_stronger", "")
        if why_not:
            counterfactuals.append(
                f"Would be stronger if: {why_not}"
            )

        # From failed criteria
        gates = decision.get("gates", {})
        for gate_name, gate_val in gates.items():
            if isinstance(gate_val, dict) and not gate_val.get("passed", True):
                threshold = gate_val.get("threshold", "")
                current = gate_val.get("current", "")
                if threshold and current:
                    counterfactuals.append(
                        f"{gate_name} would need to reach {threshold} "
                        f"(currently {current})"
                    )

        # From better_alternative
        alt = explanation.get("better_alternative", "")
        if alt:
            counterfactuals.append(f"Consider instead: {alt}")

        return counterfactuals
