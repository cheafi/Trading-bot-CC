"""
CC — Multi-Layer Ranking System
=================================
Three independent ranking perspectives:

  1. Discovery Rank  — Is this worth putting on radar?
  2. Action Rank     — Is this actionable right now?
  3. Conviction Rank — Is this top-conviction today?

A ticker can rank high on Discovery but low on Action
(e.g., hot topic, big volume, but timing is wrong).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class MultiRank:
    """Three-layer ranking for a single signal."""

    ticker: str = ""
    discovery_score: float = 0.0  # 0-100
    discovery_rank: int = 0
    action_score: float = 0.0  # 0-100
    action_rank: int = 0
    conviction_score: float = 0.0  # 0-100
    conviction_rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "discovery": {
                "score": round(self.discovery_score, 1),
                "rank": self.discovery_rank,
            },
            "action": {
                "score": round(self.action_score, 1),
                "rank": self.action_rank,
            },
            "conviction": {
                "score": round(self.conviction_score, 1),
                "rank": self.conviction_rank,
            },
        }


class MultiLayerRanker:
    """Compute 3-layer rankings for pipeline results."""

    # Hard floor: signals with explicit MTF score below this are pre-filtered
    MTF_FLOOR = 0.25

    def pre_filter(self, results: List[Any]) -> tuple[List[Any], List[str]]:
        """
        MTF pre-filter: remove signals where mtf_confluence_score is explicitly
        provided AND below MTF_FLOOR.  Returns (passing, filtered_tickers).
        Signals without an mtf_confluence_score (None) are not filtered.
        """
        passing = []
        filtered: List[str] = []
        for r in results:
            score = r.signal.get("mtf_confluence_score")
            if score is not None and score < self.MTF_FLOOR:
                ticker = r.signal.get("ticker", "?")
                filtered.append(ticker)
                logger.info(
                    "[MTF-PreFilter] %s dropped — confluence %.2f < floor %.2f",
                    ticker,
                    score,
                    self.MTF_FLOOR,
                )
            else:
                passing.append(r)
        return passing, filtered

    def rank_batch(self, results: List[Any]) -> Dict[str, MultiRank]:
        """Rank all pipeline results on 3 dimensions.

        Applies MTF pre-filter first: signals with explicit mtf_confluence_score
        below MTF_FLOOR are dropped before ranking.
        Sprint 108: applies staleness decay penalty to action_score and
        conviction_score based on signal age (data_freshness_minutes).

        Args:
            results: List of PipelineResult objects
        Returns:
            ticker → MultiRank mapping
        """
        try:
            from src.engines.signal_decay import apply_decay_penalty  # noqa: PLC0415

            _decay_available = True
        except Exception:
            _decay_available = False

        results, filtered = self.pre_filter(results)
        if filtered:
            logger.info(
                "[MTF-PreFilter] dropped %d signal(s): %s", len(filtered), filtered
            )
        ranks: Dict[str, MultiRank] = {}

        for r in results:
            ticker = r.signal.get("ticker", "")
            mr = MultiRank(ticker=ticker)
            mr.discovery_score = self._discovery(r)
            mr.action_score = self._action(r)
            mr.conviction_score = self._conviction(r)

            # Sprint 108: stale-signal penalty on action + conviction
            if _decay_available:
                _, decay_frac = apply_decay_penalty(r.signal)
                if decay_frac > 0:
                    penalty = decay_frac * 10  # up to -10 pts on action/conviction
                    mr.action_score = max(0.0, mr.action_score - penalty)
                    mr.conviction_score = max(0.0, mr.conviction_score - penalty)
                    if decay_frac > 0.25:
                        logger.debug(
                            "[DecayPenalty] %s: decay=%.1f%% action=%.1f conv=%.1f",
                            ticker,
                            decay_frac * 100,
                            mr.action_score,
                            mr.conviction_score,
                        )

            ranks[ticker] = mr

        # Assign ordinal ranks
        by_disc = sorted(
            ranks.values(),
            key=lambda x: x.discovery_score,
            reverse=True,
        )
        for i, mr in enumerate(by_disc, 1):
            mr.discovery_rank = i

        by_act = sorted(
            ranks.values(),
            key=lambda x: x.action_score,
            reverse=True,
        )
        for i, mr in enumerate(by_act, 1):
            mr.action_rank = i

        by_conv = sorted(
            ranks.values(),
            key=lambda x: x.conviction_score,
            reverse=True,
        )
        for i, mr in enumerate(by_conv, 1):
            mr.conviction_rank = i

        return ranks

    def _discovery(self, r) -> float:
        """Discovery: is this worth looking at?

        Weights: abnormality, novelty, volume, RS, catalyst.
        """
        sig = r.signal
        vol = sig.get("vol_ratio", 1.0)
        rs = sig.get("rs_rank", 50)
        score = sig.get("score", 5)

        d = 0.0
        # Volume abnormality (0-25)
        d += min(25, vol * 8)
        # RS rank (0-25)
        d += rs / 4
        # Setup score (0-25)
        d += score * 2.5
        # Catalyst / novelty (0-25)
        if sig.get("has_catalyst", False):
            d += 15
        if sig.get("insider_buy", False):
            d += 10
        if sig.get("options_bullish", False):
            d += 8

        return min(100, d)

    def _action(self, r) -> float:
        """Action: is this tradable right now?

        Weights: timing, sector fit, execution, risk/reward.
        """
        fit = r.fit
        conf = r.confidence

        a = 0.0
        # Timing fit (0-25)
        a += fit.timing_fit * 2.5
        # Sector + regime fit (0-25)
        a += (fit.sector_fit + fit.regime_fit) * 1.25
        # Execution quality (0-20)
        a += fit.execution_fit * 2.0
        # Risk quality (0-15)
        a += fit.risk_fit * 1.5
        # Confidence bonus (0-15)
        a += conf.final * 15

        # MTF confluence bonus/penalty (Sprint 99) — stored in signal dict
        mtf_score = r.signal.get("mtf_confluence_score")
        if mtf_score is not None:
            # +10 if fully aligned (1.0), −10 if fully opposed (0.0)
            a += (mtf_score - 0.5) * 20

        # Penalties
        if fit.evidence_conflicts:
            a -= len(fit.evidence_conflicts) * 5

        return max(0, min(100, a))

    def _conviction(self, r) -> float:
        """Conviction: is this top-conviction today?

        Weights: thesis quality, confidence consistency,
        historical analog support.
        """
        fit = r.fit
        conf = r.confidence
        decision = r.decision

        c = 0.0
        # Thesis confidence (0-30)
        c += conf.thesis * 30
        # Final confidence (0-25)
        c += conf.final * 25
        # Score quality (0-20)
        c += fit.final_score * 2.0
        # Leader bonus (0-12)
        if r.sector.leader_status.value == "LEADER":
            c += 12
        elif r.sector.leader_status.value == "EARLY_FOLLOWER":
            c += 6
        # Action bonus (0-18) — TRADE must outweigh LEADER status
        if decision.action == "TRADE":
            c += 18
        elif decision.action == "WATCH":
            c += 3

        # MTF confluence boost (Sprint 99): +8 if score >= 0.75, −8 if < 0.25
        mtf_score = r.signal.get("mtf_confluence_score")
        if mtf_score is not None:
            if mtf_score >= 0.75:
                c += 8
            elif mtf_score < 0.25:
                c -= 8

        # Conflict penalty
        if fit.evidence_conflicts:
            c -= len(fit.evidence_conflicts) * 7

        return max(0, min(100, c))
