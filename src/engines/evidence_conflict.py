"""
CC — Evidence Conflict Engine
===============================
Detects contradictions between bullish/bearish signals.
Not just a penalty — a structured conflict analysis that helps
the trader understand WHY the signal is uncertain.

Also includes the Better Alternative Engine that suggests
cleaner setups when available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.sector_classifier import (
    LeaderStatus,
    SectorBucket,
    SectorContext,
    SectorStage,
)

logger = logging.getLogger(__name__)


# ── Evidence Conflict Engine ─────────────────────────────────────────


@dataclass
class ConflictReport:
    """Structured conflict analysis for a signal."""

    bullish_evidence: List[str] = field(default_factory=list)
    bearish_evidence: List[str] = field(default_factory=list)
    conflict_level: str = "LOW"  # LOW / MEDIUM / HIGH / EXTREME
    conflict_score: float = 0.0  # 0-1, higher = more conflict
    penalty: float = 0.0  # score penalty to apply
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bullish_evidence": self.bullish_evidence,
            "bearish_evidence": self.bearish_evidence,
            "conflict_level": self.conflict_level,
            "conflict_score": round(self.conflict_score, 2),
            "penalty": round(self.penalty, 2),
            "summary": self.summary,
        }


class EvidenceConflictEngine:
    """Detect and quantify contradictions in signal evidence."""

    def analyze(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> ConflictReport:
        report = ConflictReport()

        # Collect bullish evidence
        self._collect_bullish(signal, sector, regime, report)
        # Collect bearish evidence
        self._collect_bearish(signal, sector, regime, report)

        # Score conflict
        bull = len(report.bullish_evidence)
        bear = len(report.bearish_evidence)
        total = bull + bear

        if total == 0:
            report.conflict_score = 0.0
        else:
            # Conflict = how balanced the evidence is
            ratio = min(bull, bear) / max(bull, bear, 1)
            report.conflict_score = ratio * min(1.0, bear / 3)

        # Level
        cs = report.conflict_score
        if cs >= 0.7:
            report.conflict_level = "EXTREME"
            report.penalty = 2.5
        elif cs >= 0.5:
            report.conflict_level = "HIGH"
            report.penalty = 1.5
        elif cs >= 0.3:
            report.conflict_level = "MEDIUM"
            report.penalty = 0.5
        else:
            report.conflict_level = "LOW"
            report.penalty = 0.0

        # Summary
        if bear == 0:
            report.summary = "Clean — no contradictory evidence"
        elif bear <= 1:
            report.summary = f"Minor conflict: {report.bearish_evidence[0]}"
        else:
            report.summary = f"{bear} contradictory signals vs {bull} supportive"

        return report

    def _collect_bullish(self, sig, sector, regime, report):
        """Identify bullish evidence."""
        score = sig.get("score", 0)
        rsi = sig.get("rsi", 50)
        vol_ratio = sig.get("vol_ratio", 1.0)
        rs = sector.relative_strength

        if score >= 7:
            report.bullish_evidence.append("Strong setup score")
        if rsi < 35:
            report.bullish_evidence.append("Oversold RSI — bounce potential")
        if vol_ratio > 1.5:
            report.bullish_evidence.append("Above-average volume")
        if rs > 0.3:
            report.bullish_evidence.append("Strong relative strength")
        if sector.leader_status == LeaderStatus.LEADER:
            report.bullish_evidence.append("Sector leader")
        if sector.sector_stage == SectorStage.ACCELERATION:
            report.bullish_evidence.append("Sector in acceleration")

        trend = regime.get("trend", "").upper()
        if trend in ("BULLISH", "RISK_ON", "UPTREND"):
            report.bullish_evidence.append("Supportive market regime")

        if sig.get("insider_buy", False):
            report.bullish_evidence.append("Insider buying detected")
        if sig.get("institutional_buy", False):
            report.bullish_evidence.append("Institutional accumulation")
        if sig.get("options_bullish", False):
            report.bullish_evidence.append("Bullish options flow")

    def _collect_bearish(self, sig, sector, regime, report):
        """Identify bearish/contradictory evidence."""
        rsi = sig.get("rsi", 50)
        vol_ratio = sig.get("vol_ratio", 1.0)
        atr_pct = sig.get("atr_pct", 2.0)

        # Chart bullish but sector late
        if sector.sector_stage in (SectorStage.CLIMAX, SectorStage.DISTRIBUTION):
            report.bearish_evidence.append(
                f"Sector in {sector.sector_stage.value} stage"
            )

        # Regime contradiction
        trend = regime.get("trend", "").upper()
        if trend in ("BEARISH", "RISK_OFF", "DOWNTREND"):
            report.bearish_evidence.append("Bearish market regime")

        # Overbought
        if rsi > 75:
            report.bearish_evidence.append("RSI overbought")

        # Extended
        dist_ma = sig.get("distance_from_50ma_pct", 0)
        if dist_ma > 15:
            report.bearish_evidence.append(f"Extended {dist_ma:.0f}% above 50MA")

        # Crowded
        if sector.crowding_risk > 0.6:
            report.bearish_evidence.append("High crowding risk")

        # Laggard
        if sector.leader_status == LeaderStatus.LAGGARD:
            report.bearish_evidence.append("Laggard — not leading")

        # Wide stop
        if atr_pct > 5.0:
            report.bearish_evidence.append(f"Wide ATR ({atr_pct:.1f}%)")

        # Earnings proximity
        dte = sig.get("days_to_earnings", 30)
        if dte < 7:
            report.bearish_evidence.append(f"Earnings in {dte} days")

        # Futures divergence (cyclicals)
        if sig.get("futures_aligned") is False:
            report.bearish_evidence.append("Futures/equity divergence")

        # Defensive quality issue
        if (
            sector.sector_bucket == SectorBucket.DEFENSIVE
            and sig.get("debt_equity", 0) > 2.0
        ):
            report.bearish_evidence.append("Weak balance sheet for defensive")

        # Volume climax (potential exhaustion)
        if vol_ratio > 4.0 and rsi > 70:
            report.bearish_evidence.append("Volume climax — exhaustion risk")


# ── Better Alternative Engine ────────────────────────────────────────


@dataclass
class Alternative:
    """A suggested better alternative to the current signal."""

    ticker: str
    reason: str
    advantage: str  # What makes it better


class BetterAlternativeEngine:
    """Suggest cleaner alternatives when available.

    Compares signals within the same sector/theme
    and identifies if there's a better setup.
    """

    def suggest(
        self,
        current_signal: Dict[str, Any],
        current_sector: SectorContext,
        all_results: List[Any],
    ) -> str:
        """Return a better alternative suggestion string.

        Args:
            current_signal: The signal being evaluated
            current_sector: Its sector context
            all_results: All PipelineResults from the batch
        """
        ticker = current_signal.get("ticker", "")
        best_alt = None
        best_reason = ""

        for result in all_results:
            alt_ticker = result.signal.get("ticker", "")
            if alt_ticker == ticker:
                continue

            # Same sector bucket
            if result.sector.sector_bucket != current_sector.sector_bucket:
                continue

            # Better score?
            alt_score = result.fit.final_score
            cur_score = current_signal.get("final_score", 0)
            if alt_score <= cur_score:
                continue

            # Check specific advantages
            advantages = []
            if result.sector.leader_status == LeaderStatus.LEADER:
                if current_sector.leader_status != LeaderStatus.LEADER:
                    advantages.append("sector leader")

            if result.fit.timing_fit > 7 and current_signal.get("timing_fit", 5) < 5:
                advantages.append("better timing")

            if result.confidence.final > 0.65:
                advantages.append("higher confidence")

            if advantages:
                best_alt = alt_ticker
                best_reason = ", ".join(advantages)

        if best_alt:
            return (
                f"Consider {best_alt} instead — {best_reason}. "
                f"Same sector, cleaner setup."
            )
        return ""
