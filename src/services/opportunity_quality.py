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


def _row_data_quality_pct(row: Dict[str, Any]) -> float:
    ev = row.get("setup_evidence") or row.get("evidence") or {}
    if ev.get("data_quality_pct") is not None:
        return float(ev["data_quality_pct"])
    conf = row.get("confidence") or row.get("data_conf")
    if isinstance(conf, dict):
        data = float(conf.get("data") or conf.get("data_quality") or 0)
        return round(data * 100.0, 0) if data <= 1.0 else round(data, 0)
    if conf is not None and float(conf) <= 1.0:
        return round(float(conf) * 100.0, 0)
    return 0.0


def _row_sample_size(row: Dict[str, Any]) -> int:
    ev = row.get("setup_evidence") or row.get("evidence") or {}
    n = ev.get("sample_size")
    if n is not None:
        return int(n)
    cal = row.get("calibration") or {}
    if cal.get("n_closed") is not None:
        return int(cal["n_closed"])
    return 0


def _row_regime_penalty(truth: Dict[str, Any], row: Dict[str, Any]) -> float:
    regime = str(truth.get("regime_state") or "WAIT").upper()
    if regime in ("NO_TRADE", "WAIT"):
        return 0.15
    if row.get("regime_conflict") or row.get("regime_mismatch"):
        return 0.25
    return 0.0


def build_grade_calibration(
    candidates: List[Dict[str, Any]],
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Explain why grades look low — data quality, sample size, regime penalty.
    Heuristic-only when uncalibrated; does not inflate deploy authority.
    """
    t = dict(truth or {})
    rows = list(candidates or [])[:5]
    samples = [_row_sample_size(r) for r in rows]
    qualities = [_row_data_quality_pct(r) for r in rows if _row_data_quality_pct(r) > 0]
    avg_quality = round(sum(qualities) / len(qualities), 0) if qualities else None
    max_sample = max(samples) if samples else 0
    regime_penalty = _row_regime_penalty(t, rows[0] if rows else {})
    calibrated = max_sample >= 20 and (avg_quality or 0) >= 55
    why_low: List[str] = []
    if avg_quality is not None and avg_quality < 60:
        why_low.append(f"data quality ~{int(avg_quality)}%")
    if max_sample < 20:
        why_low.append(f"sample n={max_sample} (need ≥20 for calibration)")
    if regime_penalty > 0:
        why_low.append(f"regime penalty {int(regime_penalty * 100)}% ({t.get('regime_state', 'WAIT')})")
    council_note = ""
    try:
        from src.services.decision_truth_model import (
            _council_deploy_conf_min,
            _council_deploy_rr_min,
            _council_deploy_score_min,
        )

        council_note = (
            f"Council bar: score ≥{_council_deploy_score_min():.1f}, "
            f"conf ≥{_council_deploy_conf_min():.2f}, R:R ≥{_council_deploy_rr_min():.1f}"
        )
    except Exception:
        council_note = "Council bar: score ≥7.5, conf ≥0.60, R:R ≥2.0"
    return {
        "data_quality_pct": avg_quality,
        "sample_size": max_sample,
        "regime_penalty_pct": round(regime_penalty * 100.0, 0),
        "calibrated": calibrated,
        "heuristic_only": not calibrated,
        "why_low": why_low,
        "why_low_zh": " · ".join(
            [
                f"資料品質 ~{int(avg_quality)}%" if avg_quality is not None and avg_quality < 60 else "",
                f"樣本 n={max_sample}" if max_sample < 20 else "",
                f"市況折讓 {int(regime_penalty * 100)}%" if regime_penalty > 0 else "",
            ]
        ).strip(" · ") or "評分為啟發式 — 未校準前勿用於倉位",
        "heuristic_banner": "Heuristic only · do not size",
        "heuristic_banner_zh": "啟發式評分 · 勿用於倉位",
        "b_plus_note_zh": "為何 B+ 仍不可部署：需 execution_ready + 看板開放 + IBKR 在線",
        "council_thresholds": council_note,
        "title_zh": "評分說明",
    }


def _research_rank_score(row: Dict[str, Any], truth: Dict[str, Any]) -> float:
    score = float(row.get("score") or row.get("net_deploy_score") or 0)
    rr = float(row.get("risk_reward") or row.get("rr_ratio") or row.get("rr") or 0)
    dq = _row_data_quality_pct(row) / 100.0
    liq = float(row.get("liquidity_score") or row.get("options_liquidity_score") or 0.5)
    regime_fit = 0.5
    regime = str(truth.get("regime_state") or "").upper()
    leadership = str(truth.get("leadership_state") or "").lower()
    if leadership == "defensive" and row.get("sector", "").upper() in ("XLP", "XLU", "XLV"):
        regime_fit = 0.85
    elif leadership == "momentum" and float(row.get("rs") or 0) >= 70:
        regime_fit = 0.8
    elif regime in ("TRADE", "SELECTIVE"):
        regime_fit = 0.65
    penalty = _row_regime_penalty(truth, row)
    composite = (
        0.35 * min(10.0, score) / 10.0
        + 0.25 * min(3.0, rr) / 3.0
        + 0.20 * dq
        + 0.10 * liq
        + 0.10 * regime_fit
    ) * (1.0 - penalty)
    return round(composite * 100.0, 2)


def rank_opportunities(
    candidates: List[Dict[str, Any]],
    truth: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Research-only ranker — regime fit, R:R, data quality, liquidity.
    Does not grant deploy authority.
    """
    t = dict(truth or {})
    ranked: List[Dict[str, Any]] = []
    for row in candidates or []:
        sym = str(row.get("ticker") or "").upper().strip()
        if not sym:
            continue
        research_score = _research_rank_score(row, t)
        ranked.append(
            {
                "ticker": sym,
                "research_score": research_score,
                "grade": row.get("grade") or row.get("setup_grade"),
                "action": row.get("action"),
                "score": row.get("score"),
                "risk_reward": row.get("risk_reward") or row.get("rr_ratio"),
                "data_quality_pct": _row_data_quality_pct(row),
                "tags": ["research_rank"],
            }
        )
    return sorted(ranked, key=lambda x: x.get("research_score", 0.0), reverse=True)


def ai_opportunity_brief(
    candidates: List[Dict[str, Any]],
    truth: Optional[Dict[str, Any]] = None,
    *,
    limit: int = 3,
) -> List[str]:
    """Three-bullet evidence summary — research only, not deploy permission."""
    t = dict(truth or {})
    ranked = rank_opportunities(candidates, t)[:limit]
    bullets: List[str] = []
    if ranked:
        top = ranked[0]
        bullets.append(
            f"Top research rank: {top['ticker']} "
            f"(score {top.get('score', '—')}, R:R {top.get('risk_reward', '—')})"
        )
    watch_n = int(t.get("watch_qualified_count") or t.get("setup_qualified_count") or 0)
    if watch_n:
        bullets.append(f"{watch_n} watch-qualified names — monitor pool, not deploy")
    if not t.get("deploy_authority"):
        primary = str(t.get("primary_blocker") or "deploy blocked")
        bullets.append(f"Deploy blocked: {primary} — research signals only")
    else:
        bullets.append("Deploy path open — confirm execution_ready on Playbook")
    return bullets[:3]


def _is_pilot_watch_row(row: Dict[str, Any]) -> bool:
    grade = str(row.get("grade") or row.get("setup_grade") or "").upper()
    score = float(row.get("score") or 0)
    rr = float(row.get("risk_reward") or row.get("rr_ratio") or row.get("rr") or 0)
    if row.get("execution_ready"):
        return False
    if grade in ("B+", "B") or score >= 7.0:
        if rr >= 2.0 or row.get("pilot_eligible"):
            return True
    return bool(row.get("pilot_eligible") and not row.get("execution_ready"))


def _sector_rotation_watchlist(
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """Defensive + cyclical sector leaders for research buckets when deploy blocked."""
    out: List[Dict[str, Any]] = []
    defensive = {"XLP", "XLU", "XLV", "GLD", "TLT"}
    cyclical = {"XLE", "XLI", "XLB", "XLF", "XLK"}
    for row in sector_leaders or []:
        sector = str(row.get("sector") or row.get("name") or row.get("ticker") or "").upper()
        ticker = str(row.get("ticker") or row.get("leader") or "").upper()
        bucket = "defensive" if sector in defensive or ticker in defensive else "cyclical"
        if sector in cyclical or ticker in cyclical:
            bucket = "cyclical"
        out.append(
            {
                "sector": sector or ticker,
                "ticker": ticker or sector,
                "bucket": bucket,
                "label": str(row.get("label") or row.get("headline") or "sector leader"),
                "research_only": True,
            }
        )
        if len(out) >= limit:
            break
    return out


def _deploy_blocker_diagnosis(truth: Dict[str, Any]) -> Dict[str, Any]:
    """Classify top blockers: infra vs threshold vs empty universe."""
    codes = list(truth.get("reason_codes") or [])
    infra = {
        "BROKER_OFFLINE",
        "EXEC_BLOCKED",
        "DATA_UNAVAILABLE",
        "DATA_STALE",
        "BRIEF_EXPIRED",
        "FALLBACK_BRIEF",
        "BOARD_STALE",
        "NO_VALID_BOARD",
        "ENGINE_OFF",
    }
    threshold = {"NO_DEPLOY_QUALIFIED", "BOARD_WAIT", "BOARD_CLOSED", "REGIME_NO_TRADE"}
    infra_hits = [c for c in codes if c in infra]
    threshold_hits = [c for c in codes if c in threshold]
    category = "mixed"
    if infra_hits and not threshold_hits:
        category = "infra"
    elif threshold_hits and not infra_hits:
        category = "threshold_or_regime"
    elif not codes:
        category = "unknown"
    empty_universe = "NO_VALID_BOARD" in codes or int(truth.get("watch_qualified_count") or 0) < 1
    return {
        "category": category,
        "infra_blockers": infra_hits[:4],
        "threshold_blockers": threshold_hits[:4],
        "empty_universe": empty_universe,
        "summary": (
            "Fix infra first (broker, brief, board freshness)"
            if category == "infra"
            else (
                "Regime/threshold — watch pool may still have names"
                if category == "threshold_or_regime"
                else "Mixed infra + council/regime gates"
            )
        ),
    }


def _monitor_only_guide_zh(
    truth: Dict[str, Any],
    closest: List[Dict[str, Any]],
) -> str:
    tickers = ", ".join(c["ticker"] for c in closest[:3] if c.get("ticker"))
    return (
        "今日：僅監察（非無機會）\n"
        "可做：研究 Watch 名單 · 期權流動性查閱 · 建立監察規則\n"
        "解鎖部署需：看板更新 + IBKR 在線 + 有 execution-ready 標的\n"
        + (f"最接近機會：{tickers}" if tickers else "最接近機會：暫無 — 刷新看板或擴大掃描")
    )


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
                "tier": "pilot_watch" if _is_pilot_watch_row(row) else "watch",
                "structure": _structure_note(row),
                "blocked": _blocked_reason_for_row(truth, row),
                "upgrade_trigger": str(trigger),
                "score": row.get("score"),
                "gap_count": len(row.get("gaps") or []),
                "pilot_watch": _is_pilot_watch_row(row),
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
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    options_signals: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Operator-facing opportunity panel — why no edge today and what unlocks deploy.

    Wired into /api/v7/today as opportunity_status; does not change capital authority.
    """
    t = dict(truth or {})
    blockers = list(t.get("reason_copy") or [])
    if not blockers and t.get("primary_blocker"):
        blockers = [str(t["primary_blocker"])]
    cand = list(candidates or [])
    closest = _closest_candidates(t, cand, list(near_miss or []))
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
    grade_cal = build_grade_calibration(cand, t)
    ranked = rank_opportunities(cand, t)
    brief = ai_opportunity_brief(cand, t)
    diagnosis = _deploy_blocker_diagnosis(t)
    sector_watch = _sector_rotation_watchlist(sector_leaders)
    deploy_blocked = not bool(t.get("deploy_authority"))
    return {
        "edge_today": edge,
        "edge_today_zh": {
            "Deploy ready": "可部署",
            "Watch only": "僅監察（非無機會）",
            "None": "今日無邊際",
        }.get(edge, edge),
        "blockers": blockers[:5],
        "blockers_headline": blockers[0] if blockers else "No edge today — preserve capital",
        "blockers_headline_zh": "為何今日無可買機會",
        "upgrade_triggers": _upgrade_triggers(t, unlock_deploy),
        "upgrade_triggers_zh": "升級條件",
        "closest_candidates": closest,
        "closest_candidates_zh": "最接近候選",
        "options_signals": options_signals or [],
        "options_research_label": "Options research available" if deploy_blocked else "Options context",
        "options_research_label_zh": "期權研究可查閱" if deploy_blocked else "期權背景",
        "sector_rotation_watchlist": sector_watch,
        "sector_rotation_watchlist_zh": "板塊輪動研究名單",
        "ranked_opportunities": ranked[:5],
        "ai_opportunity_brief": brief,
        "grade_calibration": grade_cal,
        "deploy_blocker_diagnosis": diagnosis,
        "monitor_only_guide_zh": _monitor_only_guide_zh(t, closest),
        "calibration": calibration,
        "healthy": bool(t.get("deploy_authority")) and deploy_n > 0 and watch_n > 7,
        "collapsed": deploy_n > 0 and watch_n > 7,
    }
