"""
Opportunity Intake — normalize rows from Discovery/RS/Flow/Playbook/etc. into funnel stages.

Per-surface stage caps enforced. Dedupe: ticker+setup_tags+regime+source_family+date_bucket.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.services.opportunity_intelligence_store import (
    FUNNEL_STAGES,
    OpportunityCandidate,
    OpportunityIntelligenceStore,
    OpportunityScoreSnapshot,
    OpportunityStageTransition,
    SURFACE_STAGE_CAPS,
    _new_id,
    cap_stage_for_surface,
    get_opportunity_intelligence_store,
)

_SOURCE_FAMILY_MAP: Dict[str, str] = {
    "discovery": "scanner",
    "scanners": "scanner",
    "rs": "relative_strength",
    "flow": "options_flow",
    "playbook": "playbook",
    "signals": "playbook",
    "dossier": "dossier",
    "rejections": "rejection",
    "watchlist": "watchlist",
    "funds": "fund",
    "agent": "agent",
    "strategy": "strategy",
    "strategy_lab": "strategy",
    "portfolio": "portfolio",
    "dashboard": "dashboard",
}

_STAGE_FROM_BUCKET: Dict[str, str] = {
    "deploy": "deploy_review",
    "pilot": "playbook_review",
    "watch": "watch_candidate",
    "near_miss": "near_miss",
    "near-miss": "near_miss",
    "rejected": "near_miss",
    "research": "research_hit",
    "research_hit": "research_hit",
    "evidence": "evidence_candidate",
    "capital": "capital_candidate",
}


def _date_bucket(ts: Optional[str] = None) -> str:
    if ts:
        return str(ts)[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("setup_tags", "playbook_tags", "tags", "scanner"):
        val = row.get(key)
        if isinstance(val, list):
            tags.extend(str(t) for t in val if t)
        elif val:
            tags.append(str(val))
    fam = row.get("setup_family") or row.get("family") or row.get("signal_source")
    if fam:
        tags.append(str(fam))
    return sorted({t.lower().strip() for t in tags if t})


def build_dedupe_key(
    *,
    ticker: str,
    setup_tags: List[str],
    regime: str,
    source_family: str,
    date_bucket: str,
) -> str:
    raw = "|".join(
        [
            str(ticker or "").upper().strip(),
            ",".join(sorted(setup_tags)),
            str(regime or "").lower(),
            str(source_family or "").lower(),
            str(date_bucket or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def infer_stage_from_row(
    row: Dict[str, Any],
    *,
    surface: str = "dashboard",
    near_miss: bool = False,
) -> str:
    if near_miss:
        return "near_miss"
    bucket = str(row.get("primary_bucket") or row.get("bucket") or "").lower()
    if bucket in _STAGE_FROM_BUCKET:
        return _STAGE_FROM_BUCKET[bucket]
    action = str(row.get("action") or "").upper()
    if action in ("TRADE", "BUY", "PILOT", "SCALE"):
        return "playbook_review"
    if action in ("WATCH", "MONITOR"):
        return "watch_candidate"
    if row.get("rejected") or row.get("excluded"):
        return "near_miss"
    if surface in ("discovery", "scanners"):
        return "research_hit"
    if surface in ("rs", "flow", "dossier"):
        return "evidence_candidate"
    if surface in ("playbook", "signals"):
        return "playbook_review"
    if surface in ("funds",):
        return "capital_candidate"
    return "evidence_candidate"


def normalize_intake_row(
    row: Dict[str, Any],
    *,
    surface: str = "dashboard",
    truth: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    near_miss: bool = False,
) -> OpportunityCandidate:
    t = dict(truth or {})
    sym = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
    tags = _normalize_tags(row)
    regime = str(
        row.get("regime")
        or t.get("regime_state")
        or t.get("effective_state")
        or ""
    ).upper()
    source_family = _SOURCE_FAMILY_MAP.get(str(surface).lower(), surface)
    date_bucket = _date_bucket(row.get("as_of") or row.get("recorded_at"))
    stage = infer_stage_from_row(row, surface=surface, near_miss=near_miss)
    stage = cap_stage_for_surface(stage, surface)
    dedupe = build_dedupe_key(
        ticker=sym,
        setup_tags=tags,
        regime=regime,
        source_family=source_family,
        date_bucket=date_bucket,
    )
    return OpportunityCandidate(
        candidate_id=_new_id("cand"),
        ticker=sym,
        stage=stage,
        source_surface=surface,
        source_family=source_family,
        setup_tags=tags,
        regime=regime,
        sector=str(row.get("sector") or row.get("sector_type") or ""),
        theme=str(row.get("theme") or row.get("sector_theme") or ""),
        dedupe_key=dedupe,
        session_id=session_id or date_bucket.replace("-", ""),
        metadata={
            "score": row.get("score"),
            "action": row.get("action"),
            "scanner": row.get("scanner") or row.get("signal_source"),
        },
    )


def intake_from_surface(
    rows: List[Dict[str, Any]],
    *,
    surface: str,
    truth: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    near_miss: bool = False,
) -> List[OpportunityCandidate]:
    out: List[OpportunityCandidate] = []
    seen: set[str] = set()
    for row in rows or []:
        sym = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
        if not sym:
            continue
        cand = normalize_intake_row(
            row,
            surface=surface,
            truth=truth,
            session_id=session_id,
            near_miss=near_miss,
        )
        if cand.dedupe_key in seen:
            continue
        seen.add(cand.dedupe_key)
        out.append(cand)
    return out


def intake_batch(
    *,
    truth: Optional[Dict[str, Any]] = None,
    discovery_hits: Optional[List[Dict[str, Any]]] = None,
    playbook_rows: Optional[List[Dict[str, Any]]] = None,
    near_miss_rows: Optional[List[Dict[str, Any]]] = None,
    watchlist_rows: Optional[List[Dict[str, Any]]] = None,
    rejection_rows: Optional[List[Dict[str, Any]]] = None,
    rs_rows: Optional[List[Dict[str, Any]]] = None,
    flow_rows: Optional[List[Dict[str, Any]]] = None,
    dossier_rows: Optional[List[Dict[str, Any]]] = None,
    fund_rows: Optional[List[Dict[str, Any]]] = None,
    agent_rows: Optional[List[Dict[str, Any]]] = None,
    strategy_rows: Optional[List[Dict[str, Any]]] = None,
    portfolio_rows: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "",
) -> List[OpportunityCandidate]:
    """Collect normalized candidates from all surfaces."""
    batches: List[Tuple[str, List[Dict[str, Any]], bool]] = [
        ("discovery", list(discovery_hits or []), False),
        ("rs", list(rs_rows or []), False),
        ("flow", list(flow_rows or []), False),
        ("playbook", list(playbook_rows or []), False),
        ("rejections", list(rejection_rows or []), True),
        ("watchlist", list(watchlist_rows or []), False),
        ("dossier", list(dossier_rows or []), False),
        ("funds", list(fund_rows or []), False),
        ("agent", list(agent_rows or []), False),
        ("strategy", list(strategy_rows or []), False),
        ("portfolio", list(portfolio_rows or []), False),
    ]
    near = list(near_miss_rows or [])
    if near:
        batches.append(("playbook", near, True))
    all_cands: List[OpportunityCandidate] = []
    global_seen: set[str] = set()
    for surface, rows, nm in batches:
        for cand in intake_from_surface(
            rows,
            surface=surface,
            truth=truth,
            session_id=session_id,
            near_miss=nm,
        ):
            if cand.dedupe_key in global_seen:
                continue
            global_seen.add(cand.dedupe_key)
            all_cands.append(cand)
    return all_cands


def persist_intake_batch(
    candidates: List[OpportunityCandidate],
    *,
    store: Optional[OpportunityIntelligenceStore] = None,
    deploy_authority: bool = False,
) -> Dict[str, Any]:
    st = store or get_opportunity_intelligence_store()
    persisted: List[Dict[str, Any]] = []
    for cand in candidates:
        existing = st.find_by_dedupe_key(cand.dedupe_key)
        if existing:
            from_stage = str(existing.get("stage") or "raw_universe")
            if from_stage != cand.stage:
                st.persist_transition(
                    OpportunityStageTransition(
                        transition_id=_new_id("trans"),
                        candidate_id=str(existing.get("candidate_id") or cand.candidate_id),
                        ticker=cand.ticker,
                        from_stage=from_stage,
                        to_stage=cand.stage,
                        reason="intake_stage_update",
                        source_surface=cand.source_surface,
                        session_id=cand.session_id,
                    ),
                    deploy_authority=deploy_authority,
                )
            cand.candidate_id = str(existing.get("candidate_id") or cand.candidate_id)
        persisted.append(st.persist_candidate(cand, deploy_authority=deploy_authority))
    return {"persisted": len(persisted), "candidates": persisted}


def build_opportunity_intelligence_block(
    *,
    truth: Optional[Dict[str, Any]] = None,
    discovery_hits: Optional[List[Dict[str, Any]]] = None,
    playbook_rows: Optional[List[Dict[str, Any]]] = None,
    near_miss_rows: Optional[List[Dict[str, Any]]] = None,
    forward_summary: Optional[Dict[str, Any]] = None,
    attribution_calibrations: Optional[Dict[str, Any]] = None,
    no_edge_tracking: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    persist: bool = True,
    store: Optional[OpportunityIntelligenceStore] = None,
) -> Dict[str, Any]:
    """Assemble opportunity_intelligence payload block for API surfaces."""
    from src.services.evidence_scoring_matrix import score_evidence_matrix
    from src.services.opportunity_calibration import calibrate_opportunity
    from src.services.opportunity_portfolio_builder import build_opportunity_portfolio
    from src.services.successful_opportunity_screener import screen_opportunity

    t = dict(truth or {})
    deploy_authority = bool(t.get("deploy_authority"))
    st = store or get_opportunity_intelligence_store()
    candidates = intake_batch(
        truth=t,
        discovery_hits=discovery_hits,
        playbook_rows=playbook_rows,
        near_miss_rows=near_miss_rows,
        session_id=session_id,
    )
    if persist:
        persist_intake_batch(candidates, store=st, deploy_authority=deploy_authority)

    scored_rows: List[Dict[str, Any]] = []
    for cand in candidates:
        row = {**cand.metadata, "ticker": cand.ticker, "stage": cand.stage}
        evidence = score_evidence_matrix(row, truth=t)
        calibration = calibrate_opportunity(
            row,
            truth=t,
            forward_summary=forward_summary,
            attribution_calibrations=attribution_calibrations,
            no_edge_tracking=no_edge_tracking,
        )
        screens = screen_opportunity(row, evidence=evidence, calibration=calibration, truth=t)
        snapshot = OpportunityScoreSnapshot(
            snapshot_id=_new_id("snap"),
            candidate_id=cand.candidate_id,
            ticker=cand.ticker,
            stage=cand.stage,
            evidence_grade=evidence.get("grade") or "ungraded",
            evidence_score=float(evidence.get("composite_score") or 0),
            calibration_state=str(calibration.get("state") or "learning"),
            sample_size=int(calibration.get("sample_size") or 0),
            hit_rate_range=calibration.get("hit_rate_range"),
            expectancy_range=calibration.get("expectancy_range"),
            cost_drag_r=calibration.get("cost_drag_r"),
            cost_adjusted_expected_r=calibration.get("cost_adjusted_expected_r"),
            pattern_status=str(screens.get("pattern_status") or "unvalidated"),
            screen_labels=list(screens.get("labels") or []),
            session_id=session_id,
        )
        if persist:
            st.persist_snapshot(snapshot)
        scored_rows.append(
            {
                "candidate": cand.to_dict(),
                "evidence": evidence,
                "calibration": calibration,
                "screens": screens,
                "snapshot": snapshot.to_dict(),
            }
        )

    portfolio = build_opportunity_portfolio(scored_rows, truth=t)
    by_stage = {s: 0 for s in FUNNEL_STAGES}
    for cand in candidates:
        by_stage[cand.stage] = by_stage.get(cand.stage, 0) + 1

    themes: Dict[str, int] = {}
    for cand in candidates:
        th = cand.theme or cand.sector or "unclassified"
        themes[th] = themes.get(th, 0) + 1
    best_theme = max(themes, key=themes.get) if themes else None

    best_action = "monitor"
    if by_stage.get("playbook_review", 0) > 0:
        best_action = "review_dossier"
    elif by_stage.get("research_hit", 0) > 0:
        best_action = "promote_to_playbook_review"
    elif by_stage.get("near_miss", 0) > 0:
        best_action = "create_alert"

    candidate_chips: List[str] = []
    for s in FUNNEL_STAGES:
        n = by_stage.get(s, 0)
        if n:
            candidate_chips.append(f"{s.replace('_', ' ')}:{n}")

    from src.services.cc_live_policy import INTELLIGENCE_EMPTY_NO_RESEARCH

    empty = len(candidates) < 1
    return {
        "title": "Opportunity Intelligence",
        "funnel_stages": list(FUNNEL_STAGES),
        "by_stage": by_stage,
        "counts": {
            "total": len(candidates),
            "research_hit": by_stage.get("research_hit", 0),
            "evidence_candidate": by_stage.get("evidence_candidate", 0),
            "watch_candidate": by_stage.get("watch_candidate", 0),
            "near_miss": by_stage.get("near_miss", 0),
            "playbook_review": by_stage.get("playbook_review", 0),
            "deploy_review": by_stage.get("deploy_review", 0),
            "capital_candidate": by_stage.get("capital_candidate", 0),
        },
        "best_theme": best_theme,
        "best_action": INTELLIGENCE_EMPTY_NO_RESEARCH if empty else best_action,
        "candidate_chips": candidate_chips[:8],
        "portfolio": portfolio,
        "scored_sample": scored_rows[:5],
        "store_summary": st.summary(),
        "surface_stage_caps": dict(SURFACE_STAGE_CAPS),
        "learning_mode": empty
        or any(r.get("calibration", {}).get("learning_mode") for r in scored_rows),
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "research_note": INTELLIGENCE_EMPTY_NO_RESEARCH if empty else "Evidence study — not deploy permission",
        "empty_message": INTELLIGENCE_EMPTY_NO_RESEARCH if empty else None,
    }
