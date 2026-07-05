"""
Expert Track-Record Tracker — Sprint 52
========================================
Tracks per-expert historical accuracy and adjusts vote weights
based on realized performance rather than equal weighting.

This addresses the P1 TODO in main.py: "Expert Track-Record Weighting"

How it works:
 1. After each trade outcome, record which experts were correct
 2. Compute rolling accuracy per expert per regime
 3. Weight future votes by track-record (Bayesian-inspired)
 4. Experts that are consistently wrong get down-weighted
 5. Experts that excel in certain regimes get regime-specific boosts

This is the "meritocracy of experts" — earn your weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpertRecord:
    """Track record for one expert."""

    role: str
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.5  # Prior: assume 50% until proven
    weight: float = 1.0  # Relative weight multiplier
    by_regime: dict = field(default_factory=dict)

    def update(self, was_correct: bool, regime: str = "ALL"):
        self.total_predictions += 1
        if was_correct:
            self.correct_predictions += 1

        # Bayesian-inspired: blend prior with observed
        # Prior: 50% accuracy, strength = 10 virtual samples
        prior_strength = 10
        self.accuracy = (self.correct_predictions + prior_strength * 0.5) / (
            self.total_predictions + prior_strength
        )

        # Weight: accuracy relative to baseline (0.5)
        # Expert at 70% accuracy → weight 1.4
        # Expert at 30% accuracy → weight 0.6
        self.weight = round(max(0.3, min(2.0, self.accuracy / 0.5)), 3)

        # Per-regime tracking
        if regime not in self.by_regime:
            self.by_regime[regime] = {
                "total": 0,
                "correct": 0,
                "accuracy": 0.5,
            }
        r = self.by_regime[regime]
        r["total"] += 1
        if was_correct:
            r["correct"] += 1
        r["accuracy"] = round((r["correct"] + 5 * 0.5) / (r["total"] + 5), 3)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy": round(self.accuracy, 3),
            "weight": self.weight,
            "by_regime": self.by_regime,
        }


class ExpertTracker:
    """
    Tracks expert performance and produces adjusted weights.

    The 7 CC experts:
     - trend_expert, mean_reversion_expert, macro_expert,
       volatility_expert, execution_expert, portfolio_expert,
       risk_expert
    """

    EXPERT_ROLES = [
        "trend_expert",
        "mean_reversion_expert",
        "macro_expert",
        "volatility_expert",
        "execution_expert",
        "portfolio_expert",
        "risk_expert",
    ]

    def __init__(self):
        self._records: dict[str, ExpertRecord] = {
            role: ExpertRecord(role=role) for role in self.EXPERT_ROLES
        }

    def record_outcome(
        self,
        expert_role: str,
        predicted_direction: str,
        actual_direction: str,
        regime: str = "ALL",
    ) -> Optional[ExpertRecord]:
        """Record whether an expert's prediction was correct."""
        if expert_role not in self._records:
            self._records[expert_role] = ExpertRecord(role=expert_role)

        was_correct = predicted_direction.upper() == actual_direction.upper()
        record = self._records[expert_role]
        record.update(was_correct, regime)
        return record

    def get_weights(
        self,
        regime: Optional[str] = None,
    ) -> dict[str, float]:
        """Get current expert weights, optionally regime-specific."""
        weights = {}
        for role, rec in self._records.items():
            if regime and regime in rec.by_regime:
                regime_data = rec.by_regime[regime]
                regime_acc = regime_data["accuracy"]
                weights[role] = round(max(0.3, min(2.0, regime_acc / 0.5)), 3)
            else:
                weights[role] = rec.weight
        return weights

    def weighted_vote(
        self,
        votes: dict[str, float],
        regime: Optional[str] = None,
    ) -> float:
        """
        Apply track-record weights to expert votes.

        votes: {expert_role: vote_value (-1 to +1)}
        Returns: weighted average vote
        """
        weights = self.get_weights(regime)
        total_weight = 0.0
        weighted_sum = 0.0

        for role, vote in votes.items():
            w = weights.get(role, 1.0)
            weighted_sum += vote * w
            total_weight += w

        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 4)

    def get_record(self, expert_role: str) -> Optional[dict]:
        rec = self._records.get(expert_role)
        return rec.to_dict() if rec else None

    @property
    def total_observations(self) -> int:
        return sum(r.total_predictions for r in self._records.values())

    def leaderboard(self) -> list[dict]:
        """Rank experts by accuracy."""
        ranked = sorted(
            self._records.values(),
            key=lambda r: r.accuracy,
            reverse=True,
        )
        return [r.to_dict() for r in ranked]

    def summary(self) -> dict:
        return {
            "total_observations": self.total_observations,
            "experts": len(self._records),
            "weights": self.get_weights(),
            "leaderboard": self.leaderboard(),
        }
