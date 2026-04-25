"""
CC — Sector-Adaptive Decision Pipeline
========================================
Orchestrates: Classify → Fit → Confidence → Decide → Explain

Usage:
    from src.engines.sector_pipeline import SectorPipeline
    pipeline = SectorPipeline()
    result = pipeline.process(signal, regime)
    enriched_signals = pipeline.process_batch(signals, regime)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.engines.confidence_engine import ConfidenceBreakdown, ConfidenceEngine
from src.engines.decision_mapper import Decision, DecisionMapper
from src.engines.evidence_conflict import (
    BetterAlternativeEngine,
    ConflictReport,
    EvidenceConflictEngine,
)
from src.engines.explainer import Explanation, ExplanationEngine
from src.engines.fit_scorer import FitScorer, FitScores
from src.engines.multi_ranker import MultiLayerRanker, MultiRank
from src.engines.scanner_matrix import ScannerMatrix
from src.engines.sector_classifier import SectorClassifier, SectorContext
from src.engines.sector_logic_packs import SectorAdjustment, get_sector_adjustment

logger = logging.getLogger(__name__)


class PipelineResult:
    """Full pipeline output for a single signal."""

    __slots__ = (
        "signal",
        "sector",
        "fit",
        "confidence",
        "decision",
        "explanation",
        "conflict",
        "sector_adjustment",
        "ranking",
    )

    def __init__(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        fit: FitScores,
        confidence: ConfidenceBreakdown,
        decision: Decision,
        explanation: Explanation,
        conflict: ConflictReport | None = None,
        sector_adjustment: SectorAdjustment | None = None,
        ranking: MultiRank | None = None,
    ):
        self.signal = signal
        self.sector = sector
        self.fit = fit
        self.confidence = confidence
        self.decision = decision
        self.explanation = explanation
        self.conflict = conflict
        self.sector_adjustment = sector_adjustment
        self.ranking = ranking

    def to_dict(self) -> Dict[str, Any]:
        """Full enriched signal dict for API response."""
        base = dict(self.signal)
        base["sector_context"] = self.sector.to_dict()
        base["fit_scores"] = self.fit.to_dict()
        base["confidence_breakdown"] = self.confidence.to_dict()
        base["decision"] = self.decision.to_dict()
        base["explanation"] = self.explanation.to_dict()
        if self.conflict:
            base["conflict"] = self.conflict.to_dict()
        if self.sector_adjustment:
            base["sector_adjustment"] = self.sector_adjustment.to_dict()
        if self.ranking:
            base["ranking"] = self.ranking.to_dict()
        # Promote key fields to top level for backward compat
        base["final_score"] = self.fit.final_score
        base["grade"] = self.fit.grade
        base["action"] = self.decision.action
        base["final_confidence"] = self.confidence.final
        base["confidence_label"] = self.confidence.label
        base["risk_level"] = self.decision.risk_level
        return base


class SectorPipeline:
    """Full sector-adaptive decision pipeline."""

    def __init__(self):
        self.classifier = SectorClassifier()
        self.scorer = FitScorer()
        self.confidence = ConfidenceEngine()
        self.mapper = DecisionMapper()
        self.explainer = ExplanationEngine()
        self.conflict_engine = EvidenceConflictEngine()
        self.alt_engine = BetterAlternativeEngine()
        self.ranker = MultiLayerRanker()
        self.scanner = ScannerMatrix()

    def process(
        self,
        signal: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> PipelineResult:
        """Run full pipeline on a single signal."""
        ticker = signal.get("ticker", "")

        # 1. Classify
        sector = self.classifier.classify(ticker, signal)

        # 2. Sector-specific adjustments
        adjustment = get_sector_adjustment(signal, sector, regime)

        # 3. Fit score
        fit = self.scorer.score(signal, sector, regime)
        # Apply sector adjustment
        fit.final_score = max(
            0,
            min(10, fit.final_score + adjustment.score_modifier),
        )
        fit.grade = self.scorer._to_grade(fit.final_score)

        # 4. Evidence conflict analysis
        conflict = self.conflict_engine.analyze(signal, sector, regime)
        fit.penalties += conflict.penalty
        fit.evidence_conflicts.extend(
            [f"conflict: {conflict.summary}"]
            if conflict.conflict_level in ("HIGH", "EXTREME")
            else []
        )

        # 5. Confidence
        conf = self.confidence.compute(signal, sector, fit, regime)
        conf.final = max(
            0,
            min(1.0, conf.final + adjustment.confidence_modifier),
        )

        # 6. Decision
        decision = self.mapper.decide(fit, conf, sector, regime)

        # 7. Explain
        explanation = self.explainer.explain(
            signal, sector, fit, conf, decision
        )

        return PipelineResult(
            signal=signal,
            sector=sector,
            fit=fit,
            confidence=conf,
            decision=decision,
            explanation=explanation,
            conflict=conflict,
            sector_adjustment=adjustment,
        )

    def process_batch(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[PipelineResult]:
        """Process all signals through the pipeline."""
        results = []
        for sig in signals:
            try:
                result = self.process(sig, regime)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "Pipeline error for %s: %s",
                    sig.get("ticker", "?"), e,
                )

        # Sort by final score descending
        results.sort(key=lambda r: r.fit.final_score, reverse=True)

        # Better alternatives (needs full batch)
        for result in results:
            alt = self.alt_engine.suggest(result.signal, result.sector, results)
            if alt:
                result.explanation.better_alternative = alt

        # Multi-layer ranking
        ranks = self.ranker.rank_batch(results)
        for result in results:
            ticker = result.signal.get("ticker", "")
            if ticker in ranks:
                result.ranking = ranks[ticker]

        return results

    def get_sector_summary(
        self,
        results: List[PipelineResult],
    ) -> Dict[str, Any]:
        """Sector bucket leaderboard for dashboard."""
        contexts = {r.signal.get("ticker", ""): r.sector for r in results}
        return self.classifier.get_sector_summary(contexts)

    def get_action_summary(
        self,
        results: List[PipelineResult],
    ) -> Dict[str, int]:
        """Count of signals per action."""
        counts: Dict[str, int] = {}
        for r in results:
            a = r.decision.action
            counts[a] = counts.get(a, 0) + 1
        return counts
