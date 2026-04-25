"""
CC — Decision Mapper
======================
Maps fit score + confidence → one of 7 canonical actions:
  TRADE / WATCH / WAIT / HOLD / REDUCE / EXIT / NO_TRADE

Also produces a one-line rationale for each decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from src.engines.confidence_engine import ConfidenceBreakdown
from src.engines.fit_scorer import FitScores
from src.engines.sector_classifier import SectorBucket, SectorContext

logger = logging.getLogger(__name__)


class Action:
    TRADE = "TRADE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    NO_TRADE = "NO_TRADE"

    ALL = (TRADE, WATCH, WAIT, HOLD, REDUCE, EXIT, NO_TRADE)


@dataclass
class Decision:
    """Final decision output."""

    action: str = Action.NO_TRADE
    rationale: str = ""
    score: float = 0.0
    grade: str = "F"
    confidence: float = 0.0
    confidence_label: str = "LOW"
    risk_level: str = "HIGH"  # LOW / MEDIUM / HIGH / EXTREME

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "rationale": self.rationale,
            "score": round(self.score, 1),
            "grade": self.grade,
            "confidence": round(self.confidence, 2),
            "confidence_label": self.confidence_label,
            "risk_level": self.risk_level,
        }


class DecisionMapper:
    """Map fit + confidence → action."""

    def decide(
        self,
        fit: FitScores,
        confidence: ConfidenceBreakdown,
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> Decision:
        d = Decision(
            score=fit.final_score,
            grade=fit.grade,
            confidence=confidence.final,
            confidence_label=confidence.label,
        )

        should_trade = regime.get("should_trade", True)
        score = fit.final_score
        conf = confidence.final

        # Hard blocks
        if not should_trade:
            d.action = Action.NO_TRADE
            d.rationale = "Market regime blocks new entries"
            d.risk_level = "EXTREME"
            return d

        if fit.evidence_conflicts and len(fit.evidence_conflicts) >= 3:
            d.action = Action.NO_TRADE
            d.rationale = f"Too many conflicts: {', '.join(fit.evidence_conflicts[:2])}"
            d.risk_level = "HIGH"
            return d

        # Theme/hype in distribution
        from src.engines.sector_classifier import SectorStage

        if (
            sector.sector_bucket == SectorBucket.THEME_HYPE
            and sector.sector_stage == SectorStage.DISTRIBUTION
        ):
            d.action = Action.NO_TRADE
            d.rationale = "Theme in distribution stage — avoid"
            d.risk_level = "EXTREME"
            return d

        # Score+confidence matrix
        if score >= 8.0 and conf >= 0.65:
            d.action = Action.TRADE
            d.rationale = "High-conviction setup — actionable"
            d.risk_level = "LOW"
        elif score >= 7.0 and conf >= 0.55:
            d.action = Action.TRADE
            d.rationale = "Good setup with decent confidence"
            d.risk_level = "MEDIUM"
        elif score >= 6.5 and conf >= 0.5:
            d.action = Action.WATCH
            d.rationale = "Promising but needs confirmation"
            d.risk_level = "MEDIUM"
        elif score >= 5.5 and conf >= 0.4:
            d.action = Action.WAIT
            d.rationale = "Setup forming — wait for better entry"
            d.risk_level = "MEDIUM"
        elif score >= 4.0:
            d.action = Action.WATCH
            d.rationale = "Weak setup — monitor only"
            d.risk_level = "HIGH"
        else:
            d.action = Action.NO_TRADE
            d.rationale = "Insufficient quality"
            d.risk_level = "HIGH"

        # Override for laggards
        from src.engines.sector_classifier import LeaderStatus

        if sector.leader_status == LeaderStatus.LAGGARD and d.action == Action.TRADE:
            d.action = Action.WATCH
            d.rationale += " (downgraded: laggard, not leader)"
            d.risk_level = "MEDIUM"

        return d
