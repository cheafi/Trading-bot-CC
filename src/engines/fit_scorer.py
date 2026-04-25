"""
CC — Fit Scoring Engine
========================
Sector-adaptive 8-factor weighted scoring with penalties.

Weights adjust by sector bucket:
  HIGH_GROWTH  → heavier on sector_fit, leader_fit
  CYCLICAL     → heavier on regime_fit, timing_fit
  DEFENSIVE    → heavier on risk_fit, execution_fit
  THEME_HYPE   → heavier on stage_fit, timing_fit

final_score =
  0.18 * setup_quality   + 0.17 * sector_fit
+ 0.17 * regime_fit      + 0.13 * stage_fit
+ 0.10 * leader_fit      + 0.10 * timing_fit
+ 0.10 * risk_fit        + 0.05 * execution_fit
- penalties
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.sector_classifier import SectorBucket, SectorContext

logger = logging.getLogger(__name__)


# ── Sector-adaptive weight profiles ─────────────────────────────────

_WEIGHTS: Dict[SectorBucket, Dict[str, float]] = {
    SectorBucket.HIGH_GROWTH: {
        "setup": 0.15,
        "sector": 0.20,
        "regime": 0.15,
        "stage": 0.13,
        "leader": 0.15,
        "timing": 0.08,
        "risk": 0.09,
        "execution": 0.05,
    },
    SectorBucket.CYCLICAL: {
        "setup": 0.18,
        "sector": 0.14,
        "regime": 0.20,
        "stage": 0.10,
        "leader": 0.08,
        "timing": 0.15,
        "risk": 0.10,
        "execution": 0.05,
    },
    SectorBucket.DEFENSIVE: {
        "setup": 0.18,
        "sector": 0.12,
        "regime": 0.15,
        "stage": 0.08,
        "leader": 0.07,
        "timing": 0.10,
        "risk": 0.18,
        "execution": 0.12,
    },
    SectorBucket.THEME_HYPE: {
        "setup": 0.12,
        "sector": 0.15,
        "regime": 0.12,
        "stage": 0.20,
        "leader": 0.15,
        "timing": 0.15,
        "risk": 0.06,
        "execution": 0.05,
    },
    SectorBucket.UNKNOWN: {
        "setup": 0.18,
        "sector": 0.17,
        "regime": 0.17,
        "stage": 0.13,
        "leader": 0.10,
        "timing": 0.10,
        "risk": 0.10,
        "execution": 0.05,
    },
}


@dataclass
class FitScores:
    """Individual component scores (0-10 each)."""

    setup_quality: float = 5.0
    sector_fit: float = 5.0
    regime_fit: float = 5.0
    stage_fit: float = 5.0
    leader_fit: float = 5.0
    timing_fit: float = 5.0
    risk_fit: float = 5.0
    execution_fit: float = 5.0
    penalties: float = 0.0
    evidence_conflicts: List[str] = field(default_factory=list)
    final_score: float = 5.0
    grade: str = "C"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setup_quality": round(self.setup_quality, 1),
            "sector_fit": round(self.sector_fit, 1),
            "regime_fit": round(self.regime_fit, 1),
            "stage_fit": round(self.stage_fit, 1),
            "leader_fit": round(self.leader_fit, 1),
            "timing_fit": round(self.timing_fit, 1),
            "risk_fit": round(self.risk_fit, 1),
            "execution_fit": round(self.execution_fit, 1),
            "penalties": round(self.penalties, 2),
            "evidence_conflicts": self.evidence_conflicts,
            "final_score": round(self.final_score, 1),
            "grade": self.grade,
        }


class FitScorer:
    """Compute sector-adaptive fit scores for signals."""

    def score(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> FitScores:
        fs = FitScores()
        fs.setup_quality = self._score_setup(signal)
        fs.sector_fit = self._score_sector(signal, sector)
        fs.regime_fit = self._score_regime(signal, regime)
        fs.stage_fit = self._score_stage(signal, sector)
        fs.leader_fit = self._score_leader(signal, sector)
        fs.timing_fit = self._score_timing(signal)
        fs.risk_fit = self._score_risk(signal)
        fs.execution_fit = self._score_execution(signal)

        # Penalties
        fs.penalties, fs.evidence_conflicts = self._compute_penalties(
            signal, sector, regime, fs
        )

        # Weighted final
        w = _WEIGHTS.get(sector.sector_bucket, _WEIGHTS[SectorBucket.UNKNOWN])
        raw = (
            w["setup"] * fs.setup_quality
            + w["sector"] * fs.sector_fit
            + w["regime"] * fs.regime_fit
            + w["stage"] * fs.stage_fit
            + w["leader"] * fs.leader_fit
            + w["timing"] * fs.timing_fit
            + w["risk"] * fs.risk_fit
            + w["execution"] * fs.execution_fit
        )
        fs.final_score = max(0, min(10, raw - fs.penalties))
        fs.grade = self._to_grade(fs.final_score)
        return fs

    # ── Component scorers ────────────────────────────────────────

    def _score_setup(self, sig: Dict) -> float:
        """Pattern quality: VCP contraction, breakout clarity, etc."""
        base = sig.get("score", 5.0)
        rr = sig.get("risk_reward", 1.0)
        # Bonus for good R:R
        if rr >= 3.0:
            base = min(10, base + 1.0)
        elif rr < 1.5:
            base = max(0, base - 1.0)
        return base

    def _score_sector(self, sig: Dict, sector: SectorContext) -> float:
        """How well does this signal fit its sector context?"""
        if sector.sector_bucket == SectorBucket.UNKNOWN:
            return 5.0  # neutral

        score = 6.0
        rs = sector.relative_strength
        if rs > 0.3:
            score += 2.0  # strong sector RS
        elif rs < -0.2:
            score -= 2.0  # weak sector

        # Crowding penalty for growth/hype
        if sector.sector_bucket in (SectorBucket.HIGH_GROWTH, SectorBucket.THEME_HYPE):
            score -= sector.crowding_risk * 3.0

        return max(0, min(10, score))

    def _score_regime(self, sig: Dict, regime: Dict) -> float:
        """Does the market regime support this trade?"""
        should_trade = regime.get("should_trade", True)
        if not should_trade:
            return 2.0

        trend = regime.get("trend", "").upper()
        vix = regime.get("vix", 18)

        score = 6.0
        if trend in ("BULLISH", "RISK_ON", "UPTREND"):
            score += 2.0
        elif trend in ("BEARISH", "RISK_OFF", "DOWNTREND"):
            score -= 2.0

        if vix > 30:
            score -= 1.5
        elif vix < 15:
            score += 1.0

        return max(0, min(10, score))

    def _score_stage(self, sig: Dict, sector: SectorContext) -> float:
        """Is the sector/theme at a tradable stage?"""
        from src.engines.sector_classifier import SectorStage

        stage = sector.sector_stage
        bucket = sector.sector_bucket

        if stage == SectorStage.LAUNCH:
            return 7.0 if bucket == SectorBucket.HIGH_GROWTH else 6.0
        elif stage == SectorStage.ACCELERATION:
            return 8.5
        elif stage == SectorStage.CLIMAX:
            return 4.0 if bucket == SectorBucket.THEME_HYPE else 5.5
        elif stage == SectorStage.DISTRIBUTION:
            return 2.0
        return 5.0

    def _score_leader(self, sig: Dict, sector: SectorContext) -> float:
        """Leader vs laggard scoring."""
        from src.engines.sector_classifier import LeaderStatus

        status = sector.leader_status
        if status == LeaderStatus.LEADER:
            return 9.0
        elif status == LeaderStatus.EARLY_FOLLOWER:
            return 6.5
        elif status == LeaderStatus.LAGGARD:
            return 3.0
        return 5.0

    def _score_timing(self, sig: Dict) -> float:
        """Is the timing right — near pivot, not extended?"""
        timing = sig.get("_timing", sig.get("timing", "ON_TIME"))
        rsi = sig.get("rsi", 50)

        _TIMING_SCORES = {
            "NEAR_PIVOT": 9.0,
            "EARLY": 8.0,
            "ON_TIME": 6.5,
            "EXTENDED": 4.0,
            "LATE": 2.0,
        }
        score = _TIMING_SCORES.get(timing, 5.0)

        # RSI adjustment
        if rsi > 75:
            score -= 1.5
        elif rsi < 30:
            score += 1.0  # oversold bounce potential

        return max(0, min(10, score))

    def _score_risk(self, sig: Dict) -> float:
        """Risk quality — stop quality, ATR, drawdown."""
        rr = sig.get("risk_reward", 1.0)
        atr_pct = sig.get("atr_pct", 2.0)

        score = 5.0
        if rr >= 3.0:
            score += 2.5
        elif rr >= 2.0:
            score += 1.5
        elif rr < 1.0:
            score -= 3.0

        # Tight ATR = better risk control
        if atr_pct < 2.0:
            score += 1.0
        elif atr_pct > 5.0:
            score -= 1.5

        return max(0, min(10, score))

    def _score_execution(self, sig: Dict) -> float:
        """Can this actually be executed cleanly?"""
        vol_ratio = sig.get("vol_ratio", 1.0)

        score = 6.0
        if vol_ratio >= 1.5:
            score += 1.5  # good liquidity
        elif vol_ratio < 0.5:
            score -= 2.0  # thin

        return max(0, min(10, score))

    # ── Penalties ────────────────────────────────────────────────

    def _compute_penalties(
        self, sig: Dict, sector: SectorContext, regime: Dict, fs: FitScores
    ) -> tuple[float, list]:
        """Apply penalties for evidence conflicts."""
        penalty = 0.0
        conflicts: list[str] = []

        # Laggard in climax stage
        from src.engines.sector_classifier import LeaderStatus, SectorStage

        if (
            sector.leader_status == LeaderStatus.LAGGARD
            and sector.sector_stage == SectorStage.CLIMAX
        ):
            penalty += 2.0
            conflicts.append("Laggard chasing in climax stage")

        # Bullish signal in bearish regime
        if fs.regime_fit < 4 and fs.setup_quality > 7:
            penalty += 1.0
            conflicts.append("Strong setup but weak regime")

        # High crowding + late timing
        if sector.crowding_risk > 0.7 and fs.timing_fit < 5:
            penalty += 1.5
            conflicts.append("Crowded + late timing")

        # Theme/hype in distribution
        if (
            sector.sector_bucket == SectorBucket.THEME_HYPE
            and sector.sector_stage == SectorStage.DISTRIBUTION
        ):
            penalty += 2.5
            conflicts.append("Theme in distribution — avoid")

        return penalty, conflicts

    @staticmethod
    def _to_grade(score: float) -> str:
        if score >= 8.5:
            return "A+"
        elif score >= 7.5:
            return "A"
        elif score >= 6.5:
            return "B+"
        elif score >= 5.5:
            return "B"
        elif score >= 4.5:
            return "C"
        elif score >= 3.0:
            return "D"
        return "F"
