"""
Evidence Scoring Matrix — 19 evidence families with authority-safe grading.

Brief-expired excludes brief-dependent families. AI narrative capped.
Execution/data freshness required for deploy_review grade (never deploy authority).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

EVIDENCE_FAMILIES: tuple[str, ...] = (
    "regime",
    "breadth",
    "relative_strength",
    "trend",
    "volatility",
    "volume",
    "sector_leadership",
    "setup_quality",
    "timing",
    "rr_quality",
    "execution_readiness",
    "fundamental_quality",
    "options_flow",
    "insider_ownership",
    "institutional_ownership",
    "catalyst",
    "portfolio_fit",
    "liquidity",
    "ai_narrative",
)

_BRIEF_DEPENDENT = frozenset({"setup_quality", "timing", "catalyst", "sector_leadership"})
_AI_NARRATIVE_CAP = 0.15
_DEPLOY_REVIEW_FAMILIES = frozenset(
    {"execution_readiness", "liquidity", "rr_quality", "setup_quality"}
)

_GRADE_THRESHOLDS = (
    ("A", 0.75),
    ("B", 0.55),
    ("C", 0.35),
    ("D", 0.0),
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _family_score(family: str, row: Dict[str, Any], truth: Dict[str, Any]) -> float:
    if family == "setup_quality":
        return min(1.0, _float(row.get("score")) / 10.0)
    if family == "rr_quality":
        rr = _float(row.get("risk_reward") or row.get("rr_ratio"))
        return min(1.0, rr / 3.0) if rr > 0 else 0.2
    if family == "timing":
        return _float(row.get("timing_conf"), 0.5)
    if family == "relative_strength":
        rs = _float(row.get("rs") or row.get("rs_score"))
        return min(1.0, rs / 100.0) if rs > 1 else rs
    if family == "execution_readiness":
        return 1.0 if row.get("execution_ready") else 0.25
    if family == "regime":
        tb = str(truth.get("tradeability") or truth.get("regime_state") or "WAIT").upper()
        return 0.75 if tb in ("TRADE", "SELECTIVE", "STRONG_TRADE") else 0.3
    if family == "breadth":
        b = truth.get("breadth") or truth.get("market_breadth")
        return _float(b, 0.5)
    if family == "trend":
        return _float(row.get("trend_score"), 0.5)
    if family == "volatility":
        vix = _float(truth.get("vix"), 20.0)
        return max(0.2, 1.0 - min(1.0, (vix - 12) / 30.0))
    if family == "volume":
        return min(1.0, _float(row.get("volume_score"), 0.5))
    if family == "sector_leadership":
        return 0.7 if row.get("sector_leader") or row.get("sector_type") == "leader" else 0.4
    if family == "fundamental_quality":
        return _float(row.get("fundamental_score"), 0.5)
    if family == "options_flow":
        return 0.6 if row.get("options_flow") or row.get("flow_confirm") else 0.1
    if family == "insider_ownership":
        return 0.25 if row.get("insider_signal") else 0.05
    if family == "institutional_ownership":
        return 0.2 if row.get("institutional_signal") else 0.05
    if family == "catalyst":
        return 0.6 if row.get("catalyst") or row.get("event_risk") else 0.2
    if family == "portfolio_fit":
        fit = str(row.get("portfolio_fit") or "").lower()
        return 0.8 if fit in ("allowed", "diversifier") else 0.35
    if family == "liquidity":
        return min(1.0, _float(row.get("liquidity_score"), 0.5))
    if family == "ai_narrative":
        raw = 0.5 if row.get("ai_hint") or row.get("ai_narrative") else 0.0
        return min(_AI_NARRATIVE_CAP, raw)
    return 0.5


def _resolve_grade(composite: float) -> str:
    for label, threshold in _GRADE_THRESHOLDS:
        if composite >= threshold:
            return label
    return "D"


def _freshness_ok(row: Dict[str, Any], truth: Dict[str, Any]) -> bool:
    mins = row.get("data_freshness_minutes")
    if mins is not None and int(mins) > 480:
        return False
    if truth.get("brief_expired") or str(truth.get("brief_freshness") or "").lower() == "expired":
        return False
    if row.get("partial") or row.get("module_errors"):
        return False
    return True


def score_evidence_matrix(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    stage: str = "",
) -> Dict[str, Any]:
    r = dict(row or {})
    t = dict(truth or {})
    brief_expired = bool(t.get("brief_expired")) or str(t.get("brief_freshness") or "").lower() == "expired"
    st = str(stage or r.get("stage") or "")
    families_out: List[Dict[str, Any]] = []
    active_weights: List[float] = []
    excluded: List[str] = []

    for family in EVIDENCE_FAMILIES:
        if brief_expired and family in _BRIEF_DEPENDENT:
            excluded.append(family)
            families_out.append(
                {
                    "family": family,
                    "score": None,
                    "status": "excluded_brief_expired",
                    "weight": 0.0,
                }
            )
            continue
        score = _family_score(family, r, t)
        if family == "ai_narrative":
            score = min(score, _AI_NARRATIVE_CAP)
        weight = 1.0
        if family in ("insider_ownership", "institutional_ownership", "options_flow"):
            weight = 0.6
        if family == "ai_narrative":
            weight = 0.4
        families_out.append(
            {
                "family": family,
                "score": round(score, 3),
                "status": "active",
                "weight": weight,
            }
        )
        active_weights.append(score * weight)

    composite = (
        sum(active_weights) / max(len(active_weights), 1) if active_weights else 0.0
    )
    grade = _resolve_grade(composite)

    deploy_review_ready = False
    if st == "deploy_review":
        deploy_review_ready = _freshness_ok(r, t) and all(
            any(f["family"] == fam and (f.get("score") or 0) >= 0.4 for f in families_out)
            for fam in _DEPLOY_REVIEW_FAMILIES
        )

    return {
        "families": families_out,
        "family_count": len(EVIDENCE_FAMILIES),
        "active_count": len(active_weights),
        "excluded_families": excluded,
        "composite_score": round(composite, 3),
        "grade": grade,
        "ai_narrative_capped": True,
        "brief_expired_excludes": list(_BRIEF_DEPENDENT) if brief_expired else [],
        "deploy_review_evidence_ready": deploy_review_ready,
        "deploy_review_note": (
            "Execution/data freshness gate for deploy_review grade only — not deploy permission"
            if st == "deploy_review"
            else ""
        ),
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
    }
