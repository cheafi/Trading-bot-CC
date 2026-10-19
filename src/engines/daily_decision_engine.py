"""
Daily decision pipeline — regime → rank → TradeDecision.

Reuses OpportunityEnsembler and TradeRecommendation; no broker I/O.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.models import TradeRecommendation
from src.core.trade_decision import (
    DailyDecisionPipelineResult,
    TradeDecision,
    normalize_regime_state,
    trade_decision_from_recommendation,
)
from src.engines.opportunity_ensembler import OpportunityEnsembler
from src.engines.regime_router import RegimeRouter

logger = logging.getLogger(__name__)


class DailyDecisionEngine:
    """Rank candidates and emit typed TradeDecision rows."""

    def __init__(
        self,
        *,
        ensembler: Optional[OpportunityEnsembler] = None,
        regime_router: Optional[RegimeRouter] = None,
        max_decisions: int = 10,
        top_n: int = 3,
    ) -> None:
        self._ensembler = ensembler or OpportunityEnsembler()
        self._regime_router = regime_router or RegimeRouter()
        self._max_decisions = max(1, min(30, max_decisions))
        self._top_n = max(1, min(10, top_n))

    def classify_regime(
        self, regime_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if regime_input:
            return normalize_regime_state(regime_input)
        return normalize_regime_state(None)

    def _dicts_to_recommendations(
        self, rows: List[Dict[str, Any]]
    ) -> List[TradeRecommendation]:
        out: List[TradeRecommendation] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
            if not ticker:
                continue
            rec = TradeRecommendation.from_dict(row)
            if row.get("stop_price") or row.get("stop"):
                rec.stop_price = float(row.get("stop_price") or row.get("stop") or 0)
            if row.get("entry_price") or row.get("entry"):
                rec.entry_price = float(
                    row.get("entry_price") or row.get("entry") or rec.entry_price
                )
            if row.get("target_price") or row.get("target"):
                tp = float(row.get("target_price") or row.get("target") or 0)
                if tp > 0 and rec.entry_price > 0 and rec.stop_price > 0:
                    risk = abs(rec.entry_price - rec.stop_price)
                    if risk > 0:
                        rec.risk_reward_ratio = round(abs(tp - rec.entry_price) / risk, 2)
            if isinstance(row.get("trust"), dict):
                rec.trust = dict(row["trust"])
            from src.core.quote_provenance import (
                apply_provenance_to_metadata,
                provenance_from_mapping,
            )

            prov = provenance_from_mapping(row)
            apply_provenance_to_metadata(rec.metadata, prov)
            rec.recommendation_id = str(row.get("recommendation_id") or rec.recommendation_id)
            rec.why_now = str(row.get("why_now") or rec.why_now or "")
            out.append(rec)
        return out

    def build(
        self,
        candidates: List[Dict[str, Any]],
        *,
        regime: Optional[Dict[str, Any]] = None,
        strategy_health: Optional[Dict[str, float]] = None,
    ) -> DailyDecisionPipelineResult:
        regime_state = self.classify_regime(regime)
        recs = self._dicts_to_recommendations(candidates)
        if not recs:
            return DailyDecisionPipelineResult(
                market_regime=str(regime_state.get("regime") or "UNKNOWN"),
                regime_should_trade=bool(regime_state.get("should_trade", False)),
                no_trade=True,
                no_trade_summary="No candidates supplied — valid NO TRADE / HOLD CASH state.",
            )

        ranked = self._ensembler.rank_opportunities(
            recs, regime_state, strategy_health=strategy_health
        )
        decisions: List[TradeDecision] = [
            trade_decision_from_recommendation(r, regime=regime_state)
            for r in ranked[: self._max_decisions]
        ]
        actionable = [d for d in decisions if d.is_actionable]
        watchlist = [d for d in decisions if not d.is_actionable]
        top_3 = actionable[: self._top_n]
        no_trade = len(actionable) == 0
        if no_trade:
            summary = (
                "No qualifying setups after regime, quote provenance, and evidence gates."
            )
            if not regime_state.get("should_trade", False):
                summary = (
                    "NO TRADE — market regime not actionable "
                    f"({regime_state.get('no_trade_reason') or 'should_trade=False'})."
                )
        else:
            summary = (
                f"{len(actionable)} setup(s) require explicit human approval "
                "(not broker execution authorization)."
            )
        return DailyDecisionPipelineResult(
            market_regime=str(regime_state.get("regime") or "UNKNOWN"),
            regime_should_trade=bool(regime_state.get("should_trade", False)),
            no_trade=no_trade,
            no_trade_summary=summary,
            decisions=decisions,
            top_3=top_3,
            watchlist=watchlist,
        )


daily_decision_engine = DailyDecisionEngine()
