"""
OpportunityQuality — learning-loop scaffold for post-trade outcome scoring.

Full UI and persistence live in future sprints; this module defines types and
stub evaluators only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OpportunityQualityScore:
    """Typed outcome score for a closed or paper opportunity."""

    ticker: str
    strategy_id: str = ""
    setup_grade: str = "C"
    opportunity_score: float = 0.0
    execution_score: float = 0.0
    regime_fit_score: float = 0.0
    composite: float = 0.0
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy_id": self.strategy_id,
            "setup_grade": self.setup_grade,
            "opportunity_score": round(self.opportunity_score, 2),
            "execution_score": round(self.execution_score, 2),
            "regime_fit_score": round(self.regime_fit_score, 2),
            "composite": round(self.composite, 2),
            "tags": list(self.tags),
            "notes": self.notes,
        }


def score_opportunity(
    *,
    ticker: str,
    trade: Optional[Dict[str, Any]] = None,
    regime: Optional[Dict[str, Any]] = None,
) -> OpportunityQualityScore:
    """Stub scorer — returns neutral composite until learning loop is wired."""
    _ = regime
    t = trade or {}
    pnl = float(t.get("pnl_pct") or 0.0)
    opp = 50.0 + min(25.0, max(-25.0, pnl))
    exe = 50.0 if t.get("execution_slippage_bps") is None else 45.0
    regime_fit = 50.0
    composite = (opp + exe + regime_fit) / 3.0
    return OpportunityQualityScore(
        ticker=str(ticker or "").upper(),
        strategy_id=str(t.get("strategy_id") or ""),
        setup_grade=str(t.get("setup_grade") or "C"),
        opportunity_score=opp,
        execution_score=exe,
        regime_fit_score=regime_fit,
        composite=composite,
        tags=["scaffold"],
        notes="OpportunityQuality scaffold — not yet affecting capital",
    )


def rank_opportunities(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank opportunity dicts by composite score (stub)."""
    scored = [score_opportunity(ticker=r.get("ticker", ""), trade=r).to_dict() for r in rows]
    return sorted(scored, key=lambda x: x.get("composite", 0.0), reverse=True)
