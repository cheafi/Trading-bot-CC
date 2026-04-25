"""
CC — Explanation Engine
========================
Generates deterministic explanations for every signal decision.

Output fields:
  why_now, why_not_stronger, invalidation,
  key_evidence, key_contradiction, better_alternative
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.confidence_engine import ConfidenceBreakdown
from src.engines.decision_mapper import Action, Decision
from src.engines.fit_scorer import FitScores
from src.engines.sector_classifier import (
    LeaderStatus,
    SectorBucket,
    SectorContext,
)

logger = logging.getLogger(__name__)


@dataclass
class Explanation:
    """Structured explanation for a signal decision."""

    why_now: str = ""
    why_not_stronger: str = ""
    invalidation: str = ""
    key_evidence: List[str] = field(default_factory=list)
    key_contradiction: List[str] = field(default_factory=list)
    better_alternative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "why_now": self.why_now,
            "why_not_stronger": self.why_not_stronger,
            "invalidation": self.invalidation,
            "key_evidence": self.key_evidence,
            "key_contradiction": self.key_contradiction,
            "better_alternative": self.better_alternative,
        }


class ExplanationEngine:
    """Build deterministic explanations from signal + pipeline data."""

    def explain(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        fit: FitScores,
        confidence: ConfidenceBreakdown,
        decision: Decision,
    ) -> Explanation:
        ex = Explanation()
        ex.why_now = self._build_why_now(signal, sector, fit, decision)
        ex.why_not_stronger = self._build_why_not(signal, sector, fit, confidence)
        ex.invalidation = self._build_invalidation(signal, sector)
        ex.key_evidence = self._build_evidence(signal, sector, fit)
        ex.key_contradiction = self._build_contradictions(
            signal, sector, fit, confidence
        )
        ex.better_alternative = self._suggest_alternative(signal, sector, decision)
        return ex

    def _build_why_now(
        self,
        sig: Dict,
        sector: SectorContext,
        fit: FitScores,
        decision: Decision,
    ) -> str:
        """Why is this actionable now?"""
        ticker = sig.get("ticker", "?")
        strategy = sig.get("strategy", "setup")
        parts = []

        if decision.action == Action.TRADE:
            parts.append(
                f"{ticker} {strategy} scores {fit.final_score:.1f} "
                f"({fit.grade}) with {decision.confidence_label} confidence"
            )
        elif decision.action == Action.WATCH:
            parts.append(
                f"{ticker} showing potential {strategy} — " f"needs confirmation"
            )
        else:
            parts.append(f"{ticker} not actionable now — {decision.rationale}")

        # Sector context
        if sector.sector_bucket != SectorBucket.UNKNOWN:
            parts.append(
                f"Sector: {sector.theme or sector.sector_bucket.value} "
                f"({sector.sector_stage.value})"
            )

        # Leader status
        if sector.leader_status == LeaderStatus.LEADER:
            parts.append("This is a sector leader")
        elif sector.leader_status == LeaderStatus.LAGGARD:
            parts.append("Caution: laggard, not leader")

        return ". ".join(parts)

    def _build_why_not(
        self,
        sig: Dict,
        sector: SectorContext,
        fit: FitScores,
        conf: ConfidenceBreakdown,
    ) -> str:
        """What prevents higher conviction?"""
        reasons = []

        if fit.regime_fit < 5:
            reasons.append("regime not fully supportive")
        if fit.timing_fit < 5:
            reasons.append("timing not ideal — extended or late")
        if sector.crowding_risk > 0.5:
            reasons.append("elevated crowding risk")
        if conf.data < 0.5:
            reasons.append("data quality concerns")
        if sector.leader_status == LeaderStatus.LAGGARD:
            reasons.append("laggard position in sector")
        if fit.evidence_conflicts:
            reasons.append(f"evidence conflict: {fit.evidence_conflicts[0]}")

        if not reasons:
            return "No major detractors — strong conviction"
        return "Conviction limited by: " + "; ".join(reasons[:3])

    def _build_invalidation(
        self,
        sig: Dict,
        sector: SectorContext,
    ) -> str:
        """What would invalidate this trade?"""
        stop = sig.get("stop_price", 0)
        entry = sig.get("entry_price", 0)
        ticker = sig.get("ticker", "?")

        parts = []
        if stop > 0:
            parts.append(f"Break below ${stop:.2f}")
        if entry > 0 and stop > 0:
            risk_pct = abs(entry - stop) / entry * 100
            parts.append(f"({risk_pct:.1f}% risk from entry)")

        # Sector-specific invalidation
        if sector.sector_bucket == SectorBucket.CYCLICAL:
            parts.append("Watch commodity/futures divergence")
        elif sector.sector_bucket == SectorBucket.THEME_HYPE:
            parts.append("Stage shift to distribution kills thesis")
        elif sector.sector_bucket == SectorBucket.HIGH_GROWTH:
            parts.append("Sector rotation out of growth")

        return ". ".join(parts) if parts else "See stop level"

    def _build_evidence(
        self,
        sig: Dict,
        sector: SectorContext,
        fit: FitScores,
    ) -> List[str]:
        """Key supporting evidence."""
        evidence = []

        score = sig.get("score", 0)
        rr = sig.get("risk_reward", 0)
        vol = sig.get("vol_ratio", 1.0)

        if score >= 7:
            evidence.append(f"Technical score {score:.1f}/10")
        if rr >= 2.5:
            evidence.append(f"R:R {rr:.1f} — favorable risk/reward")
        if vol >= 1.5:
            evidence.append(f"Volume {vol:.1f}x avg — confirms interest")
        if sector.leader_status == LeaderStatus.LEADER:
            evidence.append("Sector leader — RS rank top 15%")
        if sector.relative_strength > 0.3:
            evidence.append("Strong relative strength vs benchmark")
        if fit.setup_quality >= 7:
            evidence.append("High-quality setup pattern")

        return evidence[:5]

    def _build_contradictions(
        self,
        sig: Dict,
        sector: SectorContext,
        fit: FitScores,
        conf: ConfidenceBreakdown,
    ) -> List[str]:
        """Key contradicting evidence."""
        contras = list(fit.evidence_conflicts)

        if conf.timing < 0.4:
            contras.append("Timing dimension weak")
        if conf.execution < 0.4:
            contras.append("Execution risk elevated")
        if sector.crowding_risk > 0.6:
            contras.append(f"Crowding risk {sector.crowding_risk:.0%}")

        rsi = sig.get("rsi", 50)
        if rsi > 75:
            contras.append(f"RSI {rsi:.0f} — overbought")

        return contras[:4]

    def _suggest_alternative(
        self,
        sig: Dict,
        sector: SectorContext,
        decision: Decision,
    ) -> str:
        """Suggest a better alternative if available."""
        if decision.action in (Action.TRADE,):
            return ""

        if sector.leader_status == LeaderStatus.LAGGARD:
            return (
                f"Consider the sector leader instead of this "
                f"laggard — check {sector.benchmark_etf} "
                f"constituents"
            )

        if decision.action == Action.WAIT:
            return "Wait for pullback to support or pivot confirmation"

        return ""
