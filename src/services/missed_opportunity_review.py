"""
Missed Opportunity Review — classify why names were not promoted.

Never auto-loosen thresholds. authority_effect=none.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

MISS_CLASSIFICATIONS: tuple[str, ...] = (
    "authority_block",
    "broker_offline",
    "evidence_gap",
    "model_too_conservative",
    "cost_erases_edge",
    "regime_wait",
    "brief_expired",
    "concentration_limit",
    "runtime_degraded",
    "insufficient_data",
    "good_avoidance",
    "unknown",
)

INFRA_MISS = frozenset({"authority_block", "broker_offline", "runtime_degraded"})
QUALITY_MISS = frozenset(
    {
        "evidence_gap",
        "model_too_conservative",
        "cost_erases_edge",
        "regime_wait",
        "brief_expired",
        "concentration_limit",
        "insufficient_data",
    }
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def classify_missed_opportunity(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    forward_r: Optional[float] = None,
) -> Dict[str, Any]:
    """Classify one near-miss / rejected row."""
    t = dict(truth or {})
    ticker = str(row.get("ticker") or "").upper()
    fwd = forward_r if forward_r is not None else _float(row.get("forward_r_5d") or row.get("forward_r"))
    er = t.get("execution_readiness") or {}
    codes = [str(c).upper() for c in (t.get("reason_codes") or row.get("reason_codes") or [])]
    primary = str(t.get("primary_blocker") or row.get("primary_blocker") or "").upper()

    classification = "unknown"
    if not t.get("deploy_authority"):
        classification = "authority_block"
    elif not er.get("broker_connected"):
        classification = "broker_offline"
    elif str(t.get("runtime_state") or "").lower() in ("degraded", "critical"):
        classification = "runtime_degraded"
    elif t.get("brief_expired") or "BRIEF_EXPIRED" in codes:
        classification = "brief_expired"
    elif "REGIME_WAIT" in codes or "REGIME" in primary:
        classification = "regime_wait"
    elif row.get("cost_erases_edge") or row.get("cost_adjusted_pass") is False:
        classification = "cost_erases_edge"
    elif row.get("evidence_conflict") or not row.get("invalidation"):
        classification = "evidence_gap"
    elif fwd is not None and fwd > 0.5 and int(t.get("deploy_qualified_count") or 0) < 1:
        classification = "model_too_conservative"
    elif fwd is not None and fwd < 0:
        classification = "good_avoidance"
    elif int(row.get("sample_size") or 0) < 5:
        classification = "insufficient_data"
    elif "CORRELATION" in primary or "CONCENTRATION" in primary:
        classification = "concentration_limit"

    return {
        "ticker": ticker,
        "classification": classification,
        "forward_r": fwd,
        "infrastructure_miss": classification in INFRA_MISS,
        "quality_miss": classification in QUALITY_MISS,
        "auto_loosen_forbidden": True,
        "authority_effect": "none",
        "may_authorize_deploy": False,
    }


def review_missed_opportunities(
    *,
    near_miss_rows: Optional[Sequence[Dict[str, Any]]] = None,
    rejected_rows: Optional[Sequence[Dict[str, Any]]] = None,
    truth: Optional[Dict[str, Any]] = None,
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Summarize missed opportunity review — never suggests loosening."""
    fwd_by_ticker: Dict[str, float] = {}
    for r in forward_outcomes or []:
        sym = str(r.get("ticker") or "").upper()
        if sym and r.get("forward_r") is not None:
            fwd_by_ticker[sym] = _float(r["forward_r"])

    rows = list(near_miss_rows or []) + list(rejected_rows or [])
    classified: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {k: 0 for k in MISS_CLASSIFICATIONS}

    for row in rows:
        sym = str(row.get("ticker") or "").upper()
        item = classify_missed_opportunity(
            row,
            truth=truth,
            forward_r=fwd_by_ticker.get(sym),
        )
        classified.append(item)
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1

    too_conservative = counts.get("model_too_conservative", 0)
    infra = sum(counts.get(c, 0) for c in INFRA_MISS)
    quality = sum(counts.get(c, 0) for c in QUALITY_MISS)
    human_review = too_conservative > 0 or counts.get("evidence_gap", 0) > 2

    dominant = "unknown"
    if counts:
        dominant = max(
            ((k, v) for k, v in counts.items() if v > 0),
            key=lambda x: x[1],
            default=("unknown", 0),
        )[0]

    return {
        "total_reviewed": len(classified),
        "by_classification": {k: v for k, v in counts.items() if v > 0},
        "dominant_classification": dominant,
        "infrastructure_misses": infra,
        "quality_misses": quality,
        "too_conservative_count": too_conservative,
        "human_review_suggested": human_review,
        "auto_loosen_forbidden": True,
        "never_auto_loosen": True,
        "samples": classified[:10],
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "evidence_only": True,
    }
