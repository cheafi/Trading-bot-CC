"""Expert committee — reliability-weighted multi-expert ensemble.

Each expert (trend, mean-reversion, macro, volatility, execution, portfolio,
risk) emits a fixed-schema vote.  The arbiter weights experts by their
realized regime-specific accuracy, not by equal voting or rhetoric.

Architecture reference: QuantConnect's separation of alpha → portfolio
construction → risk → execution, plus scikit-learn's calibration docs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

__all__ = [
    "Expert",
    "ExpertVote",
    "ExpertCommittee",
    "CommitteeVerdict",
    "Regime",
]


# ═══════════════════════════════════════════════════════════════
# Regime enum
# ═══════════════════════════════════════════════════════════════


class Regime(str, Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS = "SIDEWAYS"
    CRISIS = "CRISIS"
    TRANSITION = "TRANSITION"


# ═══════════════════════════════════════════════════════════════
# Expert vote schema (fixed — every expert emits this)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExpertVote:
    """Fixed-schema vote emitted by every expert."""

    expert_name: str
    direction: str  # LONG / SHORT / FLAT / ABSTAIN
    conviction: float  # 0-100
    reasoning: str  # one-sentence rationale
    confidence_in_own_view: float  # 0-1, how certain the expert is
    key_risk: str  # biggest risk to this view
    regime_fit: str  # how well this view fits current regime

    def to_dict(self) -> dict:
        return {
            "expert": self.expert_name,
            "direction": self.direction,
            "conviction": round(self.conviction, 1),
            "reasoning": self.reasoning,
            "confidence": round(self.confidence_in_own_view, 2),
            "key_risk": self.key_risk,
            "regime_fit": self.regime_fit,
        }


# ═══════════════════════════════════════════════════════════════
# Expert base
# ═══════════════════════════════════════════════════════════════


@dataclass
class Expert:
    """A single expert with tracked accuracy by regime."""

    name: str
    domain: str  # trend, mean_reversion, macro, volatility, execution, portfolio, risk
    # Accuracy tracking by regime
    accuracy_by_regime: dict[str, float] = field(
        default_factory=lambda: {r.value: 0.5 for r in Regime}
    )
    total_votes: int = 0
    correct_votes: int = 0

    @property
    def overall_accuracy(self) -> float:
        return self.correct_votes / self.total_votes if self.total_votes > 0 else 0.5

    def weight_for_regime(self, regime: str) -> float:
        """Regime-specific reliability weight."""
        base = self.accuracy_by_regime.get(regime, 0.5)
        # Shrink toward 0.5 with low sample size (Bayesian-ish)
        n = max(self.total_votes, 1)
        shrinkage = min(n / 50.0, 1.0)  # fully trust after 50 votes
        return 0.5 * (1 - shrinkage) + base * shrinkage

    def record_outcome(self, regime: str, correct: bool) -> None:
        """Update accuracy tracking after a trade resolves."""
        self.total_votes += 1
        if correct:
            self.correct_votes += 1
        # Exponential moving average for regime accuracy
        alpha = 0.1
        old = self.accuracy_by_regime.get(regime, 0.5)
        self.accuracy_by_regime[regime] = old * (1 - alpha) + (1.0 if correct else 0.0) * alpha

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "overall_accuracy": round(self.overall_accuracy, 3),
            "total_votes": self.total_votes,
            "accuracy_by_regime": {
                k: round(v, 3) for k, v in self.accuracy_by_regime.items()
            },
        }


# ═══════════════════════════════════════════════════════════════
# Committee verdict
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CommitteeVerdict:
    """Aggregated verdict from the expert committee."""

    direction: str  # consensus direction
    composite_conviction: float  # weighted average conviction
    agreement_ratio: float  # fraction of experts agreeing with consensus
    dissenting_views: list[dict]  # experts who disagree
    all_votes: list[dict]  # every expert's vote
    dominant_risk: str  # most-cited risk
    regime: str
    verdict_summary: str  # one-sentence summary

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "composite_conviction": round(self.composite_conviction, 1),
            "agreement_ratio": round(self.agreement_ratio, 2),
            "dissenting_views": self.dissenting_views,
            "all_votes": self.all_votes,
            "dominant_risk": self.dominant_risk,
            "regime": self.regime,
            "verdict_summary": self.verdict_summary,
        }


# ═══════════════════════════════════════════════════════════════
# Expert committee (arbiter)
# ═══════════════════════════════════════════════════════════════


class ExpertCommittee:
    """Reliability-weighted expert committee.

    Aggregates votes from multiple domain experts, weighting each by
    their realized regime-specific accuracy.
    """

    def __init__(self) -> None:
        self.experts: list[Expert] = [
            Expert(name="Trend", domain="trend"),
            Expert(name="MeanReversion", domain="mean_reversion"),
            Expert(name="Macro", domain="macro"),
            Expert(name="Volatility", domain="volatility"),
            Expert(name="Execution", domain="execution"),
            Expert(name="Portfolio", domain="portfolio"),
            Expert(name="Risk", domain="risk"),
        ]

    def collect_votes(
        self,
        regime: str,
        rsi: float,
        vol_ratio: float,
        trending: bool,
        rr_ratio: float,
        atr_pct: float,
        portfolio_heat: float = 0.5,
        vix: float = 18.0,
    ) -> list[ExpertVote]:
        """Collect votes from all experts based on market state."""
        votes: list[ExpertVote] = []

        # ── Trend expert ──
        if trending and rsi > 50:
            votes.append(ExpertVote("Trend", "LONG", min(rsi, 90), "Trend alignment confirmed", 0.8, "Trend reversal", "STRONG"))
        elif trending:
            votes.append(ExpertVote("Trend", "LONG", 55, "Trend intact but momentum fading", 0.5, "Momentum loss", "MODERATE"))
        else:
            votes.append(ExpertVote("Trend", "FLAT", 30, "No clear trend", 0.6, "Whipsaw", "WEAK"))

        # ── Mean reversion expert ──
        if rsi < 30:
            votes.append(ExpertVote("MeanReversion", "LONG", 75, "RSI oversold — reversion likely", 0.7, "Continued selling", "STRONG"))
        elif rsi > 70:
            votes.append(ExpertVote("MeanReversion", "FLAT", 60, "RSI overbought — caution", 0.6, "Blow-off top", "MODERATE"))
        else:
            votes.append(ExpertVote("MeanReversion", "ABSTAIN", 40, "RSI neutral — no edge", 0.4, "N/A", "NEUTRAL"))

        # ── Macro expert ──
        if vix > 35:
            votes.append(ExpertVote("Macro", "FLAT", 80, "VIX crisis — capital preservation", 0.9, "Systemic risk", "CRISIS"))
        elif vix > 25:
            votes.append(ExpertVote("Macro", "FLAT", 60, "VIX elevated — reduce exposure", 0.7, "Volatility expansion", "CAUTIOUS"))
        else:
            votes.append(ExpertVote("Macro", "LONG", 55, "Macro environment supportive", 0.5, "Policy surprise", "SUPPORTIVE"))

        # ── Volatility expert ──
        if atr_pct > 0.04:
            votes.append(ExpertVote("Volatility", "FLAT", 65, "High ATR — wide stops needed", 0.6, "Gap risk", "HIGH_VOL"))
        elif vol_ratio > 1.5:
            votes.append(ExpertVote("Volatility", "LONG", 70, "Volume surge — institutional interest", 0.7, "False breakout", "STRONG"))
        else:
            votes.append(ExpertVote("Volatility", "ABSTAIN", 40, "Normal volatility — no signal", 0.4, "N/A", "NEUTRAL"))

        # ── Execution expert ──
        if vol_ratio < 0.5:
            votes.append(ExpertVote("Execution", "FLAT", 70, "Thin volume — poor fill quality", 0.8, "Slippage", "POOR"))
        elif rr_ratio < 1.5:
            votes.append(ExpertVote("Execution", "FLAT", 55, "R:R below threshold", 0.6, "Insufficient reward", "MARGINAL"))
        else:
            votes.append(ExpertVote("Execution", "LONG", 65, "Adequate liquidity and R:R", 0.6, "Market impact", "ACCEPTABLE"))

        # ── Portfolio expert ──
        if portfolio_heat > 0.8:
            votes.append(ExpertVote("Portfolio", "FLAT", 80, "Portfolio heat critical — no new risk", 0.9, "Concentration", "OVERHEATED"))
        elif portfolio_heat > 0.6:
            votes.append(ExpertVote("Portfolio", "LONG", 50, "Portfolio has room but limited", 0.5, "Correlation spike", "WARM"))
        else:
            votes.append(ExpertVote("Portfolio", "LONG", 65, "Portfolio has capacity", 0.6, "Sector overlap", "COOL"))

        # ── Risk expert ──
        if vix > 35 or portfolio_heat > 0.8:
            votes.append(ExpertVote("Risk", "FLAT", 85, "Risk conditions prohibitive", 0.9, "Drawdown", "NO_TRADE"))
        elif atr_pct > 0.05:
            votes.append(ExpertVote("Risk", "FLAT", 60, "ATR too wide for standard sizing", 0.7, "Stop distance", "REDUCE"))
        else:
            votes.append(ExpertVote("Risk", "LONG", 55, "Risk within parameters", 0.5, "Black swan", "ACCEPTABLE"))

        return votes

    def deliberate(
        self,
        votes: list[ExpertVote],
        regime: str,
    ) -> CommitteeVerdict:
        """Aggregate votes into a weighted verdict."""
        if not votes:
            return CommitteeVerdict(
                direction="ABSTAIN",
                composite_conviction=0,
                agreement_ratio=0,
                dissenting_views=[],
                all_votes=[],
                dominant_risk="No votes",
                regime=regime,
                verdict_summary="No expert votes collected",
            )

        # Weight by regime-specific accuracy
        expert_map = {e.name: e for e in self.experts}
        weighted_scores: dict[str, float] = {}
        total_weight = 0.0

        for vote in votes:
            expert = expert_map.get(vote.expert_name)
            w = expert.weight_for_regime(regime) if expert else 0.5
            w *= vote.confidence_in_own_view
            d = vote.direction
            if d in ("LONG", "SHORT"):
                weighted_scores[d] = weighted_scores.get(d, 0) + vote.conviction * w
            total_weight += w

        # Consensus direction
        if not weighted_scores:
            consensus = "ABSTAIN"
        else:
            consensus = max(weighted_scores, key=weighted_scores.get)  # type: ignore[arg-type]

        # Agreement
        agreeing = [v for v in votes if v.direction == consensus]
        agreement_ratio = len(agreeing) / len(votes) if votes else 0

        # Composite conviction (weighted average of agreeing votes)
        if agreeing and total_weight > 0:
            composite = sum(
                v.conviction * (expert_map.get(v.expert_name, Expert("?", "?")).weight_for_regime(regime))
                for v in agreeing
            ) / total_weight
        else:
            composite = 0

        # Dissenting views
        dissenting = [v.to_dict() for v in votes if v.direction != consensus and v.direction != "ABSTAIN"]

        # Dominant risk
        risks = [v.key_risk for v in votes if v.key_risk != "N/A"]
        dominant_risk = max(set(risks), key=risks.count) if risks else "None identified"

        # Summary
        n_agree = len(agreeing)
        n_total = len(votes)
        summary = (
            f"{n_agree}/{n_total} experts favor {consensus} "
            f"(conviction {composite:.0f}/100, "
            f"dominant risk: {dominant_risk})"
        )

        return CommitteeVerdict(
            direction=consensus,
            composite_conviction=composite,
            agreement_ratio=agreement_ratio,
            dissenting_views=dissenting,
            all_votes=[v.to_dict() for v in votes],
            dominant_risk=dominant_risk,
            regime=regime,
            verdict_summary=summary,
        )
