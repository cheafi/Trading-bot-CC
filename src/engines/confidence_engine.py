"""
CC — 4D Confidence Engine
==========================
Decomposes confidence into 4 dimensions:
  1. Thesis     (35%) — Is the fundamental/technical case sound?
  2. Timing     (30%) — Is the timing right for entry?
  3. Execution  (20%) — Can this trade be executed cleanly?
  4. Data       (15%) — How reliable is the underlying data?

final_confidence =
  0.35 * thesis + 0.30 * timing + 0.20 * execution + 0.15 * data
  - confidence_penalties
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.fit_scorer import FitScores
from src.engines.sector_classifier import SectorBucket, SectorContext, SectorStage

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBreakdown:
    """4-dimensional confidence output."""

    thesis: float = 0.5  # 0-1
    timing: float = 0.5
    execution: float = 0.5
    data: float = 0.5
    penalties: float = 0.0
    penalty_reasons: List[str] = field(default_factory=list)
    final: float = 0.5
    label: str = "MODERATE"  # LOW / MODERATE / HIGH / VERY_HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis": round(self.thesis, 2),
            "timing": round(self.timing, 2),
            "execution": round(self.execution, 2),
            "data": round(self.data, 2),
            "penalties": round(self.penalties, 2),
            "penalty_reasons": self.penalty_reasons,
            "final": round(self.final, 2),
            "label": self.label,
        }


class ConfidenceEngine:
    """Compute 4D confidence from fit scores + sector context."""

    def compute(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        fit: FitScores,
        regime: Dict[str, Any],
    ) -> ConfidenceBreakdown:
        cb = ConfidenceBreakdown()

        cb.thesis = self._thesis_confidence(signal, sector, fit)
        cb.timing = self._timing_confidence(signal, sector, fit)
        cb.execution = self._execution_confidence(signal, fit)
        cb.data = self._data_confidence(signal)

        # Penalties
        cb.penalties, cb.penalty_reasons = self._penalties(signal, sector, fit, regime)

        # Weighted final
        raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution + 0.15 * cb.data
        cb.final = max(0, min(1.0, raw - cb.penalties))
        cb.label = self._label(cb.final)
        return cb

    def _thesis_confidence(
        self, sig: Dict, sector: SectorContext, fit: FitScores
    ) -> float:
        """Is the underlying thesis (setup + sector + leader) sound?"""
        # Combine setup quality, sector fit, leader fit
        raw = (
            fit.setup_quality * 0.4 + fit.sector_fit * 0.3 + fit.leader_fit * 0.3
        ) / 10
        # Boost for leaders in acceleration
        if (
            sector.leader_status.value == "LEADER"
            and sector.sector_stage == SectorStage.ACCELERATION
        ):
            raw = min(1.0, raw + 0.1)
        return max(0, min(1.0, raw))

    def _timing_confidence(
        self, sig: Dict, sector: SectorContext, fit: FitScores
    ) -> float:
        """Is the timing right for entry now?"""
        raw = (fit.timing_fit * 0.5 + fit.stage_fit * 0.3 + fit.regime_fit * 0.2) / 10
        # Climax → timing confidence drops
        if sector.sector_stage == SectorStage.CLIMAX:
            raw *= 0.7
        return max(0, min(1.0, raw))

    def _execution_confidence(self, sig: Dict, fit: FitScores) -> float:
        """Can the trade be executed cleanly at planned levels?"""
        raw = (fit.execution_fit * 0.5 + fit.risk_fit * 0.5) / 10
        # Wide stops → lower execution confidence
        atr_pct = sig.get("atr_pct", 2.0)
        if atr_pct > 4.0:
            raw *= 0.8
        return max(0, min(1.0, raw))

    def _data_confidence(self, sig: Dict) -> float:
        """How reliable is the data behind this signal?"""
        freshness = sig.get("data_freshness", "")
        vol_ratio = sig.get("vol_ratio", 1.0)

        # Missing freshness → penalize (was defaulting to "live")
        if not freshness:
            base = 0.4
        elif freshness == "live":
            base = 0.9
        elif freshness == "delayed":
            base = 0.6
        elif freshness in ("stale", "synthetic"):
            base = 0.3
        else:
            base = 0.5

        # Volume confirms data quality
        if vol_ratio > 1.0:
            base = min(1.0, base + 0.1)
        elif vol_ratio < 0.3:
            base -= 0.15

        return max(0, min(1.0, base))

    def _penalties(
        self, sig: Dict, sector: SectorContext, fit: FitScores, regime: Dict
    ) -> tuple[float, list]:
        penalties = 0.0
        reasons: list[str] = []

        # Evidence conflicts from fit scoring
        if fit.evidence_conflicts:
            penalties += len(fit.evidence_conflicts) * 0.05
            reasons.extend(fit.evidence_conflicts)

        # High score but bad regime
        if fit.final_score > 7 and fit.regime_fit < 4:
            penalties += 0.1
            reasons.append("High score but poor regime — confidence capped")

        # Theme in late stage
        if sector.sector_bucket == SectorBucket.THEME_HYPE and sector.sector_stage in (
            SectorStage.CLIMAX,
            SectorStage.DISTRIBUTION,
        ):
            penalties += 0.15
            reasons.append("Theme late-stage — reduce confidence")

        return penalties, reasons

    @staticmethod
    def _label(conf: float) -> str:
        if conf >= 0.8:
            return "VERY_HIGH"
        elif conf >= 0.65:
            return "HIGH"
        elif conf >= 0.45:
            return "MODERATE"
        elif conf >= 0.25:
            return "LOW"
        return "VERY_LOW"
