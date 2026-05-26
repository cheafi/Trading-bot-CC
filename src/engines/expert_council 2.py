"""
CC — Expert Council: Named Expert System + Sector Pipeline
============================================================
High-level orchestrator that wires:
  ContextAssembler → SectorPipeline → ExpertCommittee → Decision

Five named experts with domain-specific, sector-aware logic:
  1. TechnicalExpert   — price action, RSI, volume, trend
  2. FundamentalExpert  — valuation, growth, sector norms
  3. MacroExpert        — regime, VIX, breadth, rates
  4. RiskExpert         — ATR, drawdown, portfolio heat, correlation
  5. DevilsAdvocateExpert — contrarian view, invalidation, crowding

Usage:
    council = ExpertCouncil()
    result = council.evaluate(signal, regime_ctx, sector_ctx)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from src.engines.expert_committee import CommitteeVerdict, ExpertCommittee, ExpertVote
from src.engines.sector_classifier import SectorBucket, SectorContext
from src.engines.sector_pipeline import PipelineResult, SectorPipeline

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Named Expert Base
# ═══════════════════════════════════════════════════════════════


class NamedExpert(ABC):
    """Abstract base class for domain-specific named experts.

    Subclasses MUST implement ``vote()``.  Any attempt to instantiate
    a subclass that omits ``vote()`` raises ``TypeError`` at construction
    time — not at call time — thanks to the ``@abstractmethod`` decorator.
    """

    name: str = "Base"

    @abstractmethod
    def vote(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> ExpertVote:
        """Produce an expert vote for the given signal/sector/regime context."""
        ...


# ═══════════════════════════════════════════════════════════════
# 1. Technical Expert
# ═══════════════════════════════════════════════════════════════


class TechnicalExpert(NamedExpert):
    name = "Technical"

    def vote(self, signal, sector, regime):
        rsi = signal.get("rsi", 50)
        vol_r = signal.get("vol_ratio", 1.0)
        score = signal.get("score", 0)
        strategy = signal.get("strategy", "")
        trending = regime.get("regime", "") == "UPTREND"
        bucket = sector.sector_bucket

        # Sector-aware RSI interpretation
        if bucket == SectorBucket.DEFENSIVE:
            rsi_bull = 35 < rsi < 60
            rsi_risk = "Mean-reversion failure" if rsi < 30 else "Overbought"
        elif bucket == SectorBucket.HIGH_GROWTH:
            rsi_bull = 45 < rsi < 75
            rsi_risk = "Momentum collapse"
        elif bucket == SectorBucket.THEME_HYPE:
            rsi_bull = 50 < rsi < 80
            rsi_risk = "Narrative exhaustion"
        else:
            rsi_bull = 40 < rsi < 70
            rsi_risk = "Sector rotation"

        conv = min(score * 10, 95)

        if trending and rsi_bull and vol_r > 1.0:
            return ExpertVote(
                self.name,
                "LONG",
                conv,
                f"{strategy} setup with trend+momentum alignment",
                0.8,
                rsi_risk,
                "STRONG",
            )
        elif score >= 6.0:
            return ExpertVote(
                self.name,
                "LONG",
                conv * 0.7,
                f"{strategy} setup — partial confirmation",
                0.5,
                rsi_risk,
                "MODERATE",
            )
        else:
            return ExpertVote(
                self.name,
                "FLAT",
                30,
                "No clear technical setup",
                0.6,
                "False signal",
                "WEAK",
            )


# ═══════════════════════════════════════════════════════════════
# 2. Fundamental Expert
# ═══════════════════════════════════════════════════════════════


class FundamentalExpert(NamedExpert):
    name = "Fundamental"

    def vote(self, signal, sector, regime):
        bucket = sector.sector_bucket
        rr = signal.get("risk_reward", 0)
        score = signal.get("score", 0)

        # ── Real fundamental data (populated by dossier / p9 pipeline) ───────
        fundamentals = signal.get("fundamentals") or {}

        def _f(v, default=None):
            try:
                return float(v) if v is not None else default
            except (TypeError, ValueError):
                return default

        pe = _f(fundamentals.get("pe_ratio") or fundamentals.get("trailingPE"))
        fpe = _f(fundamentals.get("forward_pe") or fundamentals.get("forwardPE"))
        margin = _f(
            fundamentals.get("profit_margin") or fundamentals.get("profitMargins")
        )
        roe_v = _f(fundamentals.get("roe") or fundamentals.get("returnOnEquity"))
        de = _f(fundamentals.get("debt_equity") or fundamentals.get("debtToEquity"))

        # Composite quality score 0–1 from real data; 0.5 neutral when missing
        quality_score = 0.5
        _factors = []
        if pe is not None and 0 < pe < 500:
            _factors.append(max(0.0, min(1.0, (50 - pe) / 50)))  # PE<25 = good
        if fpe is not None and 0 < fpe < 500:
            _factors.append(max(0.0, min(1.0, (40 - fpe) / 40)))
        if margin is not None:
            _factors.append(max(0.0, min(1.0, margin / 0.15)))  # >15% = strong
        if roe_v is not None:
            _factors.append(max(0.0, min(1.0, roe_v / 0.15)))  # >15% = strong
        if de is not None and de >= 0:
            _factors.append(max(0.0, min(1.0, 1.0 - de / 200)))  # low D/E good
        if _factors:
            quality_score = sum(_factors) / len(_factors)

        has_real_data = bool(_factors)
        # ── Sector-specific logic uses quality_score ──────────────────────────

        # Sector-specific valuation heuristics
        if bucket == SectorBucket.HIGH_GROWTH:
            # Growth stocks: R:R and momentum matter more
            if rr >= 3.0 and score >= 7.0:
                return ExpertVote(
                    self.name,
                    "LONG",
                    70,
                    "Growth profile with strong R:R — fundamentals supportive",
                    0.6,
                    "Multiple compression",
                    "STRONG",
                )
            # Growth without strong R:R — check quality_score
            if quality_score >= 0.6 and rr >= 2.0:
                data_note = " (real P/E+margin data)" if has_real_data else ""
                return ExpertVote(
                    self.name,
                    "BUY_SMALL",
                    55,
                    f"Growth quality acceptable{data_note} — moderate position",
                    0.5,
                    "Multiple compression",
                    "MODERATE",
                )
            return ExpertVote(
                self.name,
                "ABSTAIN",
                40,
                "Growth stock — need momentum confirmation",
                0.4,
                "Valuation stretched",
                "NEUTRAL",
            )

        elif bucket == SectorBucket.DEFENSIVE:
            # Defensive: stability + quality score
            qual_threshold = 0.55 if has_real_data else 0.0
            if score >= 6.0 and quality_score >= qual_threshold:
                data_note = f" (quality={quality_score:.2f})" if has_real_data else ""
                return ExpertVote(
                    self.name,
                    "LONG",
                    65,
                    f"Defensive quality — stable earnings profile{data_note}",
                    0.7,
                    "Yield competition from bonds",
                    "STRONG",
                )
            return ExpertVote(
                self.name,
                "FLAT",
                35,
                "Defensive stock below quality threshold",
                0.5,
                "Earnings miss",
                "WEAK",
            )

        elif bucket == SectorBucket.CYCLICAL:
            # Cyclical: macro-dependent + check leverage (D/E)
            should_trade = regime.get("should_trade", True)
            high_leverage = de is not None and de > 150
            if should_trade and rr >= 2.0 and not high_leverage:
                return ExpertVote(
                    self.name,
                    "LONG",
                    60,
                    "Cyclical with supportive macro backdrop",
                    0.5,
                    "Commodity price reversal",
                    "MODERATE",
                )
            reason = "high leverage" if high_leverage else "macro headwinds or weak R:R"
            return ExpertVote(
                self.name,
                "FLAT",
                45,
                f"Cyclical — {reason}",
                0.5,
                "Demand slowdown",
                "CAUTIOUS",
            )

        # THEME_HYPE or UNKNOWN
        return ExpertVote(
            self.name,
            "ABSTAIN",
            35,
            "Thematic/speculative — fundamentals less relevant",
            0.3,
            "Narrative shift",
            "NEUTRAL",
        )


# ═══════════════════════════════════════════════════════════════
# 3. Macro Expert
# ═══════════════════════════════════════════════════════════════


class MacroExpert(NamedExpert):
    name = "Macro"

    def vote(self, signal, sector, regime):
        vix = regime.get("vix", 18)
        breadth = regime.get("breadth", 0.5)
        should_trade = regime.get("should_trade", True)
        vol_label = regime.get("volatility", "NORMAL")
        bucket = sector.sector_bucket

        if vix > 35:
            return ExpertVote(
                self.name,
                "FLAT",
                90,
                f"VIX at {vix:.0f} — crisis conditions, capital preservation",
                0.95,
                "Systemic risk",
                "CRISIS",
            )

        if not should_trade:
            return ExpertVote(
                self.name,
                "FLAT",
                75,
                "Regime guard active — macro unfavorable",
                0.85,
                "Drawdown risk",
                "RISK_OFF",
            )

        if vix > 25:
            # Elevated — defensive sectors OK, growth risky
            if bucket == SectorBucket.DEFENSIVE:
                return ExpertVote(
                    self.name,
                    "LONG",
                    55,
                    "Elevated VIX favors defensive positioning",
                    0.6,
                    "Broad sell-off",
                    "SUPPORTIVE",
                )
            return ExpertVote(
                self.name,
                "FLAT",
                65,
                f"VIX {vix:.0f} — reduce risk exposure",
                0.7,
                "Volatility expansion",
                "CAUTIOUS",
            )

        if breadth < 0.3:
            return ExpertVote(
                self.name,
                "FLAT",
                60,
                f"Narrow breadth ({breadth:.0%}) — rally fragile",
                0.6,
                "Breadth divergence",
                "CAUTIOUS",
            )

        return ExpertVote(
            self.name,
            "LONG",
            55,
            "Macro environment supportive",
            0.5,
            "Policy surprise",
            "SUPPORTIVE",
        )


# ═══════════════════════════════════════════════════════════════
# 4. Risk Expert
# ═══════════════════════════════════════════════════════════════


class RiskExpert(NamedExpert):
    name = "Risk"

    def vote(self, signal, sector, regime):
        atr_pct = signal.get("atr_pct", 0.02)
        rr = signal.get("risk_reward", 0)
        vix = regime.get("vix", 18)
        vol_label = regime.get("volatility", "NORMAL")

        risks = []

        if atr_pct > 0.05:
            risks.append("ATR too wide for standard sizing")
        if rr < 1.5:
            risks.append("R:R below minimum threshold")
        if vix > 30:
            risks.append("VIX elevated — gap risk")
        if vol_label in ("HIGH", "CRISIS"):
            risks.append("Volatility regime dangerous")

        if len(risks) >= 3:
            return ExpertVote(
                self.name,
                "FLAT",
                85,
                "Multiple risk flags — no trade",
                0.9,
                risks[0],
                "NO_TRADE",
            )
        elif len(risks) >= 2:
            return ExpertVote(
                self.name,
                "FLAT",
                65,
                f"Risk concerns: {'; '.join(risks[:2])}",
                0.7,
                risks[0],
                "REDUCE",
            )
        elif len(risks) == 1:
            return ExpertVote(
                self.name,
                "LONG",
                50,
                f"Manageable risk: {risks[0]}",
                0.5,
                risks[0],
                "ACCEPTABLE",
            )
        return ExpertVote(
            self.name,
            "LONG",
            60,
            "Risk parameters within acceptable bounds",
            0.6,
            "Black swan",
            "ACCEPTABLE",
        )


# ═══════════════════════════════════════════════════════════════
# 5. Devil's Advocate Expert
# ═══════════════════════════════════════════════════════════════


class DevilsAdvocateExpert(NamedExpert):
    name = "DevilsAdvocate"

    def vote(self, signal, sector, regime):
        rsi = signal.get("rsi", 50)
        vol_r = signal.get("vol_ratio", 1.0)
        score = signal.get("score", 0)
        bucket = sector.sector_bucket
        stage = sector.sector_stage

        contradictions = []

        # Crowding check
        if vol_r > 3.0:
            contradictions.append("Volume spike may indicate crowded trade")

        # Overbought in any sector
        if rsi > 75:
            contradictions.append(f"RSI {rsi:.0f} overbought — reversal risk")

        # Theme exhaustion
        if bucket == SectorBucket.THEME_HYPE:
            from src.engines.sector_classifier import SectorStage

            if stage in (SectorStage.CLIMAX, SectorStage.DISTRIBUTION):
                contradictions.append(
                    "Theme in late stage — narrative may be priced in"
                )

        # Score doesn't match regime
        if score >= 7.0 and not regime.get("should_trade", True):
            contradictions.append(
                "Strong setup in unfavorable regime — could be a trap"
            )

        # Defensive in risk-on
        regime_label = regime.get("regime", "")
        if bucket == SectorBucket.DEFENSIVE and regime_label == "UPTREND":
            contradictions.append("Defensive play in risk-on — opportunity cost")

        if len(contradictions) >= 2:
            return ExpertVote(
                self.name,
                "FLAT",
                70,
                f"Contrarian concerns: {contradictions[0]}",
                0.7,
                contradictions[1],
                "SKEPTICAL",
            )
        elif contradictions:
            return ExpertVote(
                self.name,
                "LONG",
                45,
                f"Minor concern: {contradictions[0]}",
                0.4,
                contradictions[0],
                "CAUTIOUS",
            )
        return ExpertVote(
            self.name,
            "LONG",
            55,
            "No major contrarian signals — thesis intact",
            0.5,
            "Unknown unknowns",
            "ALIGNED",
        )


# ═══════════════════════════════════════════════════════════════
# Expert Council — orchestrator
# ═══════════════════════════════════════════════════════════════


@dataclass
class CouncilResult:
    """Full council output for a single signal."""

    pipeline: PipelineResult
    verdict: CommitteeVerdict
    expert_votes: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        base = self.pipeline.to_dict()
        base["expert_council"] = {
            "verdict": self.verdict.to_dict(),
            "expert_count": len(self.expert_votes),
            "agreement": self.verdict.agreement_ratio,
            "dominant_risk": self.verdict.dominant_risk,
        }
        return base


class ExpertCouncil:
    """
    Top-level decision orchestrator.

    Flow:
      1. SectorPipeline: classify → fit → confidence → decide → explain
      2. Named Experts: 5 domain experts vote with sector awareness
      3. ExpertCommittee: reliability-weighted aggregation
      4. Final output: pipeline result + expert verdict
    """

    def __init__(self):
        self.pipeline = SectorPipeline()
        self.committee = ExpertCommittee()
        self.experts: List[NamedExpert] = [
            TechnicalExpert(),
            FundamentalExpert(),
            MacroExpert(),
            RiskExpert(),
            DevilsAdvocateExpert(),
        ]

    def evaluate(
        self,
        signal: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> CouncilResult:
        """Run full council evaluation on a single signal."""
        # 1. Sector pipeline
        pr = self.pipeline.process(signal, regime)

        # 2. Named expert votes
        votes = []
        for expert in self.experts:
            try:
                vote = expert.vote(signal, pr.sector, regime)
                votes.append(vote)
            except Exception as e:
                logger.warning(
                    "Expert %s failed for %s: %s",
                    expert.name,
                    signal.get("ticker", "?"),
                    e,
                )

        # 3. Committee deliberation
        regime_label = regime.get("regime", "SIDEWAYS")
        verdict = self.committee.deliberate(votes, regime_label)

        return CouncilResult(
            pipeline=pr,
            verdict=verdict,
            expert_votes=[v.to_dict() for v in votes],
        )

    def evaluate_batch(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[CouncilResult]:
        """Evaluate all signals through the council."""
        results = []
        for sig in signals:
            try:
                r = self.evaluate(sig, regime)
                results.append(r)
            except Exception as e:
                logger.warning(
                    "Council error for %s: %s",
                    sig.get("ticker", "?"),
                    e,
                )
        # Sort by pipeline fit score
        results.sort(
            key=lambda r: r.pipeline.fit.final_score,
            reverse=True,
        )
        return results
