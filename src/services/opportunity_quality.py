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


_REPAIR_TO_TRIGGER = {
    "BROKER_OFFLINE": "Broker online — IBKR session + handoff ready",
    "EXEC_BLOCKED": "Clear execution breaker / bracket block",
    "DATA_UNAVAILABLE": "Board fresh — live market data available",
    "DATA_STALE": "Board fresh — refresh ranked scanner",
    "BRIEF_EXPIRED": "Brief <2d — regenerate morning brief",
    "FALLBACK_BRIEF": "Board fresh — exit brief fallback to live scanner",
    "BOARD_STALE": "Board fresh — ranked load from live scanner",
    "NO_VALID_BOARD": "Board fresh — scanner must produce watch candidates",
    "ENGINE_OFF": "Engine on — live scan cycle running",
    "NO_DEPLOY_QUALIFIED": "≥1 deploy-qualified setup (score/R:R/timing gate)",
    "BOARD_WAIT": "Tradeability SELECTIVE+ with execution-ready name",
    "BOARD_CLOSED": "Regime reopens — should_trade true",
    "REGIME_NO_TRADE": "Regime improves — breadth/VIX normalize",
}


def _edge_today_label(truth: Dict[str, Any]) -> str:
    if truth.get("deploy_authority"):
        return "Deploy ready"
    watch_n = int(truth.get("watch_qualified_count") or truth.get("setup_qualified_count") or 0)
    if watch_n >= 1:
        return "Watch only"
    return "None"


def _structure_note(row: Dict[str, Any]) -> str:
    grade = str(row.get("grade") or row.get("setup_grade") or "").strip()
    score = row.get("score")
    parts: List[str] = []
    if grade:
        parts.append(f"{grade} structure")
    elif score is not None:
        parts.append(f"score {score}")
    gaps = row.get("gaps") or []
    if gaps:
        parts.append(f"gap: {gaps[0]}")
    return " · ".join(parts) if parts else "developing setup"


def _blocked_reason_for_row(truth: Dict[str, Any], row: Dict[str, Any]) -> str:
    blockers = truth.get("reason_copy") or []
    if blockers:
        return str(blockers[0])
    if row.get("deploy_authority") is False or truth.get("deploy_authority") is False:
        return str(truth.get("primary_blocker") or "deploy blocked")
    return "monitor only"


def _closest_candidates(
    truth: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    near_miss: List[Dict[str, Any]],
    *,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Top near-miss / watch rows with upgrade path — even when deploy blocked."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def _add(row: Dict[str, Any]) -> None:
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            return
        action = str(row.get("action") or "").upper()
        if action in ("AVOID", "NO_TRADE"):
            return
        seen.add(ticker)
        trigger = (
            row.get("upgrade_trigger")
            or row.get("distance_to_pass")
            or row.get("whats_missing")
            or "confirm R:R + timing"
        )
        out.append(
            {
                "ticker": ticker,
                "action": action or "WATCH",
                "structure": _structure_note(row),
                "blocked": _blocked_reason_for_row(truth, row),
                "upgrade_trigger": str(trigger),
                "score": row.get("score"),
                "gap_count": len(row.get("gaps") or []),
            }
        )

    for nm in sorted(near_miss or [], key=lambda r: len(r.get("gaps") or [])):
        _add(nm)
        if len(out) >= limit:
            break
    if len(out) < limit:
        for row in candidates or []:
            if str(row.get("action") or "").upper() in ("TRADE", "DEPLOY"):
                continue
            _add(row)
            if len(out) >= limit:
                break
    return out[:limit]


def _upgrade_triggers(
    truth: Dict[str, Any],
    unlock_deploy: Optional[Dict[str, Any]] = None,
    *,
    limit: int = 3,
) -> List[str]:
    triggers: List[str] = []
    repair = list(truth.get("repair_priority") or [])
    for code in repair:
        t = _REPAIR_TO_TRIGGER.get(code)
        if t and t not in triggers:
            triggers.append(t)
        if len(triggers) >= limit:
            return triggers[:limit]
    unlock = unlock_deploy or {}
    for cond in unlock.get("conditions") or []:
        if cond.get("met"):
            continue
        label = str(cond.get("label") or "").strip()
        if label and label not in triggers:
            triggers.append(label)
        if len(triggers) >= limit:
            break
    if not triggers:
        watch_n = int(truth.get("watch_qualified_count") or 0)
        triggers.append(
            f"Board fresh → broker online → brief <2d → {max(1, watch_n)} watch candidates unlock"
        )
    return triggers[:limit]


def build_opportunity_status(
    truth: Optional[Dict[str, Any]] = None,
    *,
    candidates: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    unlock_deploy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
  Operator-facing opportunity panel — why no edge today and what unlocks deploy.

    Wired into /api/v7/today as opportunity_status; does not change capital authority.
    """
    t = dict(truth or {})
    blockers = list(t.get("reason_copy") or [])
    if not blockers and t.get("primary_blocker"):
        blockers = [str(t["primary_blocker"])]
    closest = _closest_candidates(t, list(candidates or []), list(near_miss or []))
    edge = _edge_today_label(t)
    deploy_n = int(t.get("deploy_qualified_count") or 0)
    watch_n = int(t.get("watch_qualified_count") or t.get("setup_qualified_count") or 0)
    calibration = {
        "deploy_qualified": deploy_n,
        "watch_qualified": watch_n,
        "deploy_authority": bool(t.get("deploy_authority")),
        "board_gate": str(t.get("board_gate") or ""),
        "brief_freshness": str(t.get("brief_freshness") or ""),
        "ranked_board_freshness": str(t.get("ranked_board_freshness") or ""),
    }
    return {
        "edge_today": edge,
        "edge_today_zh": {
            "Deploy ready": "可部署",
            "Watch only": "僅監察",
            "None": "今日無邊際",
        }.get(edge, edge),
        "blockers": blockers[:5],
        "blockers_headline": blockers[0] if blockers else "No edge today — preserve capital",
        "blockers_headline_zh": "為何今日無可買機會",
        "upgrade_triggers": _upgrade_triggers(t, unlock_deploy),
        "upgrade_triggers_zh": "升級條件",
        "closest_candidates": closest,
        "closest_candidates_zh": "最接近候選",
        "calibration": calibration,
        "healthy": bool(t.get("deploy_authority")) and deploy_n > 0 and watch_n > 7,
        "collapsed": deploy_n > 0 and watch_n > 7,
    }
