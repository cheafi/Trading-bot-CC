"""
Score families — separate thesis quality, decision confidence, deployability, and rank.

Each family exposes scale, meaning, and source so operators never see mystery numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical families (key → metadata)
SCORE_FAMILIES: Dict[str, Dict[str, str]] = {
    "evidence": {
        "label": "Evidence",
        "meaning": "Data quality + sample depth supporting the setup",
        "scale": "0–1 confidence · calibration n when available",
    },
    "freshness": {
        "label": "Freshness",
        "meaning": "How current quotes and modules are",
        "scale": "tier / minutes stale",
    },
    "board_investability": {
        "label": "Board investability",
        "meaning": "Council fit score on today's board",
        "scale": "0–10 board fit score",
    },
    "setup_quality": {
        "label": "Setup quality",
        "meaning": "Structure, trigger, and pattern quality proxies",
        "scale": "0–10 or engine grade",
    },
    "risk_geometry": {
        "label": "Risk geometry",
        "meaning": "R:R, stop distance, and invalidation clarity",
        "scale": "R:R ratio + gate flags",
    },
    "deployability": {
        "label": "Deployability",
        "meaning": "Passes action tier + execution-ready bar",
        "scale": "boolean + action label",
    },
    "portfolio_contribution": {
        "label": "Portfolio contribution",
        "meaning": "Diversifier vs correlated cluster in the book",
        "scale": "fit label / overlap %",
    },
    "cost_adjusted_edge": {
        "label": "Cost-adjusted edge",
        "meaning": "Net score after turnover and spread drag",
        "scale": "0–10 gross → net",
    },
    "crowding_narrative_heat": {
        "label": "Crowding / narrative heat",
        "meaning": "Extension, consensus, sector cluster risk",
        "scale": "low / medium / high",
    },
    "passive_replacement_risk": {
        "label": "Passive replacement risk",
        "meaning": "Likelihood passive baseline matches this bet",
        "scale": "low / medium / high",
    },
    "simplicity_challenge": {
        "label": "Simplicity challenge",
        "meaning": "Is complexity justified vs doing less?",
        "scale": "justified / marginal / unjustified",
    },
}

# Distinct roles — never collapse these in UI copy
SCORE_ROLES = {
    "thesis_quality": "How strong the bull case evidence is (not permission to trade)",
    "decision_confidence": "Model composite — timing + thesis + execution + data",
    "deployability": "Whether gates permit sizing today",
    "rank": "Sort order on board — action tier first, then board fit score",
}


def _freshness_tier(row: Dict[str, Any]) -> str:
    eq = row.get("evidence_quality") or {}
    fresh = eq.get("freshness") or row.get("data_freshness") or "unknown"
    mins = row.get("data_freshness_minutes")
    if mins is not None and int(mins) > 480:
        return "stale"
    if str(fresh).lower() in ("stale", "degraded", "critical"):
        return "stale"
    if str(fresh).lower() in ("real_time", "fresh", "live"):
        return "fresh"
    return str(fresh)


def extract_families_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build per-family display dict from a playbook or today row."""
    score = float(row.get("score") or row.get("validated_score") or 0)
    float(row.get("thesis_conf") or 0)
    float(row.get("timing_conf") or 0)
    rr = row.get("risk_reward")
    eq = row.get("evidence_quality") or {}
    crowding = row.get("crowding_narrative") or {}

    families: Dict[str, Any] = {
        "evidence": {
            "value": eq.get("data_conf", row.get("data_conf")),
            "display": f"Data {float(eq.get('data_conf') or row.get('data_conf') or 0):.0%}"
            if (eq.get("data_conf") or row.get("data_conf")) is not None
            else "—",
            "note": eq.get("calibration_note", ""),
        },
        "freshness": {
            "value": _freshness_tier(row),
            "display": _freshness_tier(row).replace("_", " "),
        },
        "board_investability": {
            "value": score,
            "display": f"{score:.1f} board score",
            "raw_scanner": eq.get("raw_score"),
        },
        "setup_quality": {
            "value": row.get("trigger_quality") or row.get("grade"),
            "display": str(row.get("grade") or row.get("trigger_quality") or "—"),
        },
        "risk_geometry": {
            "value": rr,
            "display": f"R:R {rr}" if rr else "—",
            "below_trade_gate": bool(row.get("rr_below_trade_threshold")),
        },
        "deployability": {
            "value": row.get("action"),
            "display": (row.get("action") or "WATCH")
            + (" · ready" if row.get("execution_ready") else " · not ready"),
            "execution_ready": bool(row.get("execution_ready")),
        },
        "portfolio_contribution": {
            "value": row.get("portfolio_gate") or row.get("sector_alignment"),
            "display": str(
                row.get("sector_alignment_label") or row.get("sector_alignment") or "—"
            ),
        },
        "cost_adjusted_edge": {
            "value": row.get("net_deploy_score"),
            "display": row.get("net_edge_display")
            or (
                f"Raw {row.get('raw_score')} · Net {row.get('net_deploy_score')}"
                if row.get("net_deploy_score") is not None
                else "—"
            ),
            "weak_after_cost": bool(row.get("weak_edge_after_cost")),
        },
        "crowding_narrative_heat": {
            "value": crowding.get("level", "unknown"),
            "display": crowding.get("summary", "—")[:80],
        },
        "passive_replacement_risk": {
            "value": row.get("passive_replacement_risk", "medium"),
            "display": str(row.get("passive_replacement_risk", "—")),
        },
        "simplicity_challenge": {
            "value": row.get("complexity_verdict", "marginal"),
            "display": str(row.get("complexity_verdict", "—")),
        },
    }
    return families


def build_score_card(row: Dict[str, Any]) -> Dict[str, Any]:
    """Compact score card separating roles for UI tooltips."""
    families = extract_families_from_row(row)
    return {
        "families": families,
        "family_meta": SCORE_FAMILIES,
        "roles": SCORE_ROLES,
        "thesis_quality": float(row.get("thesis_conf") or 0),
        "decision_confidence": float(row.get("final_conf") or 0),
        "deployability_label": families["deployability"]["display"],
        "rank_inputs": {
            "action": row.get("action"),
            "validated_score": row.get("score"),
            "sector_alignment": row.get("sector_alignment"),
        },
    }


def attach_score_families_to_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate row with score_card for playbook / today surfaces."""
    row = {**row, "score_card": build_score_card(row)}
    return row


SCORE_DIVERGENCE_THRESHOLD = 1.5
DISAGREEMENT_MESSAGE = "Score families disagree — do not size on rank alone"

_WEAK_QUALITY_TIERS = frozenset({"WEAK", "REJECT"})
_STRONG_QUALITY_TIER = "STRONG"
_TOP_RANK_DISAGREE = 3


def _normalize_score_0_10(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f > 20:
        return round(f / 10.0, 2)
    return round(f, 2)


def _resolve_rank(row: Dict[str, Any], *, index: Optional[int] = None) -> int:
    try:
        return int(row.get("rank") or (index + 1 if index is not None else 99))
    except (TypeError, ValueError):
        return 99


def _quality_tier(row: Dict[str, Any]) -> str:
    q = row.get("quality") or {}
    return str(q.get("tier") or row.get("quality_tier") or "—").upper()


def _row_ev_score(row: Dict[str, Any]) -> Optional[float]:
    raw = row.get("ev_score")
    if raw is None:
        raw = (row.get("ev_components") or {}).get("ev_score")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def detect_score_family_disagreement(
    row: Dict[str, Any],
    *,
    rank_total: int = 0,
    peers: Optional[List[Dict[str, Any]]] = None,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
    index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compare rank, quality tier, deploy authority, and EV band.
    Research/display only — never grants deploy from rank.
    """
    reasons: List[str] = []
    rank = _resolve_rank(row, index=index)
    tier = _quality_tier(row)
    tb = str(tradeability or row.get("tradeability") or "WAIT").upper()
    exec_ready = bool(row.get("execution_ready"))
    ev_f = _row_ev_score(row)

    families: Dict[str, Any] = {
        "rank": rank,
        "rank_label": f"#{rank}" + (f" / {rank_total}" if rank_total else ""),
        "quality_tier": tier,
        "authority": "DEPLOY" if exec_ready else "MONITOR",
        "deploy_open": deploy_open,
        "gate": tb,
        "ev_score": ev_f,
        "execution_ready": exec_ready,
    }

    if rank <= 1 and tier in _WEAK_QUALITY_TIERS:
        reasons.append(f"rank #{rank} · quality {tier}")

    if (
        rank <= _TOP_RANK_DISAGREE
        and not exec_ready
        and tier != _STRONG_QUALITY_TIER
        and (not deploy_open or tb in ("WAIT", "NO_TRADE"))
    ):
        reasons.append(f"rank #{rank} · gate {tb} · quality {tier}")

    peer_rows = peers or []
    if peer_rows and rank <= _TOP_RANK_DISAGREE and ev_f is not None:
        peer_evs = [v for v in (_row_ev_score(p) for p in peer_rows) if v is not None]
        if peer_evs:
            median_ev = sorted(peer_evs)[len(peer_evs) // 2]
            max_ev = max(peer_evs)
            if ev_f < median_ev * 0.75 or (rank == 1 and ev_f < max_ev * 0.85):
                reasons.append(f"rank #{rank} · EV {ev_f:.2f} below peers")

    if (
        tier == _STRONG_QUALITY_TIER
        and (tb in ("WAIT", "NO_TRADE") or not deploy_open)
        and not exec_ready
    ):
        reasons.append(f"quality STRONG · gate {tb}")

    if row_has_council_scanner_divergence(row):
        reasons.append("council vs scanner score diverge")

    if str(row.get("conflict_level") or "").upper() in ("HIGH", "CRITICAL"):
        reasons.append("high structural conflict")

    if (brief_stale or row.get("research_context_only")) and rank <= _TOP_RANK_DISAGREE:
        reasons.append(f"rank #{rank} · research context only")

    unique: List[str] = []
    seen: set[str] = set()
    for item in reasons:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    disagree = bool(unique)
    return {
        "disagree": disagree,
        "families": families,
        "message": DISAGREEMENT_MESSAGE if disagree else "",
        "reasons": unique[:4],
    }


def attach_score_families_disagreement_to_row(
    row: Dict[str, Any],
    *,
    rank_total: int = 0,
    peers: Optional[List[Dict[str, Any]]] = None,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
    index: Optional[int] = None,
) -> Dict[str, Any]:
    out = dict(row)
    out["score_families"] = detect_score_family_disagreement(
        out,
        rank_total=rank_total,
        peers=peers,
        deploy_open=deploy_open,
        tradeability=tradeability,
        brief_stale=brief_stale,
        index=index,
    )
    if "score_card" not in out:
        out = attach_score_families_to_row(out)
    return out


def attach_score_families_disagreement_to_rows(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
) -> List[Dict[str, Any]]:
    if not rows:
        return []
    total = len(rows)
    return [
        attach_score_families_disagreement_to_row(
            r,
            rank_total=total,
            peers=rows,
            deploy_open=deploy_open,
            tradeability=tradeability,
            brief_stale=brief_stale,
            index=i,
        )
        for i, r in enumerate(rows)
    ]


def build_score_families_summary(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
) -> Dict[str, Any]:
    """Payload-level summary for board/today APIs."""
    disagree_rows: List[Dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        sf = row.get("score_families")
        if not sf:
            sf = detect_score_family_disagreement(
                row,
                rank_total=len(rows or []),
                peers=rows,
                deploy_open=deploy_open,
                tradeability=tradeability,
                brief_stale=brief_stale,
                index=i,
            )
        if sf.get("disagree"):
            disagree_rows.append(
                {
                    "ticker": row.get("ticker"),
                    "rank": (sf.get("families") or {}).get("rank"),
                    "reasons": sf.get("reasons") or [],
                }
            )
    tickers = [str(d["ticker"]) for d in disagree_rows if d.get("ticker")][:8]
    return {
        "active": bool(disagree_rows),
        "message": DISAGREEMENT_MESSAGE,
        "disagree_count": len(disagree_rows),
        "disagree_rows": disagree_rows[:8],
        "disagree_tickers": tickers,
    }


def row_has_council_scanner_divergence(row: Dict[str, Any]) -> bool:
    """True when council fit score and raw scanner score disagree materially."""
    eq = row.get("evidence_quality") or {}
    council = _normalize_score_0_10(row.get("score") or eq.get("validated_score"))
    scanner = _normalize_score_0_10(eq.get("raw_score"))
    if scanner is None:
        fam = (row.get("score_card") or {}).get("families") or {}
        scanner = _normalize_score_0_10(
            (fam.get("board_investability") or {}).get("raw_scanner")
        )
    if council is None or scanner is None:
        return False
    return abs(council - scanner) >= SCORE_DIVERGENCE_THRESHOLD


def build_score_reconciliation(
    rows: Optional[List[Dict[str, Any]]] = None,
    *,
    cross_asset: Optional[Dict[str, Any]] = None,
    contradiction_flags: Optional[List[str]] = None,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
) -> Dict[str, Any]:
    """
    Dashboard / today payload: warn when score families diverge
    (rank vs quality vs authority vs EV) or explicit contradictions exist.
    """
    rows = rows or []
    divergent: List[str] = []
    disagree_reasons: List[str] = []
    family_disagree_tickers: List[str] = []

    for i, row in enumerate(rows[:20]):
        sf = row.get("score_families")
        if not sf:
            sf = detect_score_family_disagreement(
                row,
                rank_total=len(rows),
                peers=rows,
                deploy_open=deploy_open,
                tradeability=tradeability,
                brief_stale=brief_stale,
                index=i,
            )
        tk = str(row.get("ticker") or "").upper()
        if sf.get("disagree") and tk:
            family_disagree_tickers.append(tk)
            for reason in sf.get("reasons") or []:
                line = f"{tk}: {reason}" if tk not in reason else reason
                if line not in disagree_reasons:
                    disagree_reasons.append(line)
        if row_has_council_scanner_divergence(row) and tk and tk not in divergent:
            divergent.append(tk)

    contradictions: List[str] = list(contradiction_flags or [])
    for row in rows[:20]:
        if str(row.get("conflict_level") or "").upper() in ("HIGH", "CRITICAL"):
            tk = str(row.get("ticker") or "").upper()
            if tk:
                contradictions.append(f"{tk}: high conflict level")
    if cross_asset:
        for item in cross_asset.get("conflicts") or []:
            contradictions.append(str(item))
        if int(cross_asset.get("conflict_count") or 0) >= 2:
            contradictions.append("Macro cross-asset conflicts elevated")
    contradictions = contradictions[:8]
    divergent = divergent[:5]
    merged_tickers = []
    for tk in family_disagree_tickers + divergent:
        if tk and tk not in merged_tickers:
            merged_tickers.append(tk)
    merged_tickers = merged_tickers[:8]
    summary = build_score_families_summary(
        rows,
        deploy_open=deploy_open,
        tradeability=tradeability,
        brief_stale=brief_stale,
    )
    active = bool(merged_tickers or contradictions or summary.get("active"))
    return {
        "active": active,
        "message": DISAGREEMENT_MESSAGE,
        "divergent_tickers": merged_tickers,
        "contradictions": contradictions,
        "council_scanner_divergence": bool(divergent),
        "disagree_reasons": disagree_reasons[:6],
        "score_families_summary": summary,
    }


def complexity_verdict(
    *,
    deployable_count: int,
    module_count: int = 0,
    net_edge: Optional[float] = None,
    tradeability: str = "WAIT",
) -> Dict[str, Any]:
    """
    Dashboard strip: is today's complexity justified?
    """
    tb = (tradeability or "").upper()
    if tb in ("NO_TRADE", "WAIT") and deployable_count < 1:
        verdict = "justified"
        detail = "Simplest correct action is patience — cash is valid."
    elif deployable_count >= 2 and (net_edge or 0) >= 6.5:
        verdict = "justified"
        detail = (
            f"{deployable_count} deploy-grade names — board complexity earns its keep."
        )
    elif module_count > 12 and deployable_count < 1:
        verdict = "unjustified"
        detail = "Many modules firing but no deploy bar cleared — favor doing less."
    elif (net_edge or 0) < 6.0 and deployable_count >= 1:
        verdict = "marginal"
        detail = "Deploy candidate exists but net edge after cost is thin — size down."
    else:
        verdict = "marginal"
        detail = "Mixed board — verify each layer before adding process complexity."
    return {
        "verdict": verdict,
        "display": verdict.replace("_", " "),
        "detail": detail,
        "question": "Is today's complexity justified?",
    }
