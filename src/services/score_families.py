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
    thesis = float(row.get("thesis_conf") or 0)
    timing = float(row.get("timing_conf") or 0)
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
            "display": (row.get("action") or "WATCH") + (
                " · ready" if row.get("execution_ready") else " · not ready"
            ),
            "execution_ready": bool(row.get("execution_ready")),
        },
        "portfolio_contribution": {
            "value": row.get("portfolio_gate") or row.get("sector_alignment"),
            "display": str(row.get("sector_alignment_label") or row.get("sector_alignment") or "—"),
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
) -> Dict[str, Any]:
    """
    Dashboard / today payload: warn when council vs scanner families diverge
    or explicit contradiction flags are present.
    """
    rows = rows or []
    divergent: List[str] = []
    for row in rows[:20]:
        if not row_has_council_scanner_divergence(row):
            continue
        tk = str(row.get("ticker") or "").upper()
        if tk:
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
    active = bool(divergent or contradictions)
    return {
        "active": active,
        "message": "Score families disagree — do not size on rank alone",
        "divergent_tickers": divergent,
        "contradictions": contradictions,
        "council_scanner_divergence": bool(divergent),
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
        detail = f"{deployable_count} deploy-grade names — board complexity earns its keep."
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
