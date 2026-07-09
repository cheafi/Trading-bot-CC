"""
Signal Family Attribution — group evidence into families with validation status.

No family becomes validated without minimum sample size and forward outcome evidence.
AI narrative and options flow start unvalidated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SIGNAL_FAMILIES: tuple[str, ...] = (
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
    "sentiment",
    "ai_narrative",
)

FAMILY_STATUSES: tuple[str, ...] = (
    "unvalidated",
    "noisy",
    "improving",
    "validated",
    "retired",
)

MIN_VALIDATED_SAMPLE = 20
MIN_IMPROVING_SAMPLE = 8

_DEFAULT_UNVALIDATED = frozenset(
    {"ai_narrative", "options_flow", "insider_ownership", "institutional_ownership", "sentiment"}
)
_LAGGED_FAMILIES = frozenset({"insider_ownership", "institutional_ownership"})


def _float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _family_contribution(family: str, row: Dict[str, Any], truth: Dict[str, Any]) -> float:
    """Heuristic contribution 0–1 — not deploy authority."""
    if family == "setup_quality":
        score = _float_or_none(row.get("score")) or 0.0
        return min(1.0, score / 10.0)
    if family == "rr_quality":
        rr = _float_or_none(row.get("risk_reward") or row.get("rr_ratio")) or 0.0
        return min(1.0, rr / 3.0)
    if family == "timing":
        return _float_or_none(row.get("timing_conf")) or 0.5
    if family == "relative_strength":
        rs = _float_or_none(row.get("rs") or row.get("rs_score")) or 0.0
        return min(1.0, rs / 100.0) if rs > 1 else rs
    if family == "execution_readiness":
        return 1.0 if row.get("execution_ready") else 0.2
    if family == "regime":
        tb = str(truth.get("tradeability") or truth.get("regime_state") or "WAIT").upper()
        return 0.8 if tb in ("TRADE", "SELECTIVE", "STRONG_TRADE") else 0.3
    if family == "ai_narrative":
        return 0.15 if row.get("ai_hint") or row.get("ai_narrative") else 0.0
    if family == "options_flow":
        return 0.2 if row.get("options_flow") or row.get("flow_confirm") else 0.0
    if family == "liquidity":
        liq = _float_or_none(row.get("liquidity_score")) or 0.5
        return min(1.0, liq)
    if family == "portfolio_fit":
        fit = str(row.get("portfolio_fit") or "").lower()
        return 0.8 if fit in ("allowed", "diversifier") else 0.4
    return 0.5


def resolve_family_status(
    *,
    family: str,
    sample_size: int,
    forward_r_mean: Optional[float] = None,
    false_positive_rate: Optional[float] = None,
    live_calibration: bool = False,
    brief_expired: bool = False,
) -> str:
    if family in _DEFAULT_UNVALIDATED and not live_calibration:
        if sample_size >= MIN_IMPROVING_SAMPLE and forward_r_mean is not None and forward_r_mean > 0:
            return "improving"
        return "unvalidated"
    if brief_expired and family in ("setup_quality", "timing", "catalyst"):
        return "unvalidated"
    if sample_size < MIN_IMPROVING_SAMPLE:
        return "unvalidated"
    if false_positive_rate is not None and false_positive_rate > 0.45:
        return "noisy"
    if sample_size >= MIN_VALIDATED_SAMPLE and forward_r_mean is not None and forward_r_mean > 0.2:
        return "validated"
    if sample_size >= MIN_IMPROVING_SAMPLE:
        return "improving"
    return "unvalidated"


def attribute_family(
    family: str,
    *,
    row: Optional[Dict[str, Any]] = None,
    truth: Optional[Dict[str, Any]] = None,
    sample_size: int = 0,
    forward_r_mean: Optional[float] = None,
    forward_r_median: Optional[float] = None,
    win_rate: Optional[float] = None,
    false_positive_rate: Optional[float] = None,
    false_negative_rate: Optional[float] = None,
    live_calibration: bool = False,
) -> Dict[str, Any]:
    r = dict(row or {})
    t = dict(truth or {})
    brief_expired = bool(t.get("brief_expired")) or str(t.get("brief_freshness") or "").lower() == "expired"
    contrib = _family_contribution(family, r, t)
    status = resolve_family_status(
        family=family,
        sample_size=sample_size,
        forward_r_mean=forward_r_mean,
        false_positive_rate=false_positive_rate,
        live_calibration=live_calibration,
        brief_expired=brief_expired,
    )
    confidence = "low"
    if sample_size >= MIN_VALIDATED_SAMPLE:
        confidence = "medium"
    elif sample_size >= MIN_IMPROVING_SAMPLE:
        confidence = "low"
    else:
        confidence = "insufficient"
    may_boost_deploy = (
        status == "validated"
        and family not in _LAGGED_FAMILIES
        and family not in _DEFAULT_UNVALIDATED
    )
    return {
        "family": family,
        "contribution_score": round(contrib, 2),
        "confidence": confidence,
        "sample_size": int(sample_size),
        "forward_r_mean": forward_r_mean,
        "forward_r_median": forward_r_median,
        "win_rate": win_rate,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "regime_conditioned_result": None,
        "cost_adjusted_result": None,
        "status": status,
        "may_boost_deploy": False,
        "may_authorize_deploy": False,
        "lagged": family in _LAGGED_FAMILIES,
        "note": (
            "lagged — cannot directly boost deploy"
            if family in _LAGGED_FAMILIES
            else "unvalidated until live calibration"
            if family in _DEFAULT_UNVALIDATED and not live_calibration
            else ""
        ),
    }


def extract_active_families(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    threshold: float = 0.35,
) -> List[str]:
    """Return families with meaningful contribution on this row."""
    t = dict(truth or {})
    active: List[str] = []
    for fam in SIGNAL_FAMILIES:
        if _family_contribution(fam, row, t) >= threshold:
            active.append(fam)
    return active or ["setup_quality"]


def attribute_families_for_row(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    calibration: Optional[Dict[str, Any]] = None,
    store_calibration: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    cal = dict(calibration or {})
    store_cal = dict(store_calibration or {})
    ev = row.get("setup_evidence") or row.get("evidence") or {}
    active = extract_active_families(row, truth=truth)
    results: List[Dict[str, Any]] = []
    for fam in active:
        fam_store = store_cal.get(fam) or {}
        sample = int(
            fam_store.get("sample_size")
            or ev.get("sample_size")
            or cal.get("n_closed")
            or 0
        )
        fwd_mean = _float_or_none(
            fam_store.get("forward_r_mean") or ev.get("avg_r") or cal.get("forward_r_mean")
        )
        fp = _float_or_none(fam_store.get("false_positive_rate") or cal.get("false_positive_rate"))
        live_cal = bool(
            fam_store.get("live_calibration")
            or cal.get("live_calibration")
            or ev.get("calibrated")
        )
        attr = attribute_family(
            fam,
            row=row,
            truth=truth,
            sample_size=sample,
            forward_r_mean=fwd_mean,
            win_rate=_float_or_none(ev.get("win_rate")),
            false_positive_rate=fp,
            live_calibration=live_cal and fam == "options_flow",
        )
        if fam_store.get("status"):
            store_status = str(fam_store["status"])
            status_map = {
                "useful": "validated",
                "harmful": "noisy",
                "learning": "unvalidated",
            }
            attr["status"] = status_map.get(store_status, store_status)
            attr["store_status"] = store_status
            attr["evidence_source"] = fam_store.get("evidence_source", "live_forward")
            attr["learning_mode"] = bool(fam_store.get("learning_mode", sample < MIN_VALIDATED_SAMPLE))
        results.append(attr)
    return results


def summarize_family_health(
    attributions: List[List[Dict[str, Any]]],
    *,
    store_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dashboard-level family health — sample required before validated label."""
    counts: Dict[str, Dict[str, int]] = {}
    for group in attributions or []:
        for a in group or []:
            fam = str(a.get("family") or "")
            st = str(a.get("status") or "unvalidated")
            counts.setdefault(fam, {})
            counts[fam][st] = counts[fam].get(st, 0) + 1
    ss = dict(store_summary or {})
    best_validated = ss.get("best_validated_family") or ""
    noisiest = ss.get("noisy_family") or ""
    if not best_validated:
        for fam, sts in counts.items():
            if sts.get("validated", 0) > 0 and not best_validated:
                best_validated = fam
    if not noisiest:
        for fam, sts in counts.items():
            if sts.get("noisy", 0) > 0:
                noisiest = fam
    total_n = int(ss.get("aggregate_sample_size") or 0) or sum(
        int(a.get("sample_size") or 0)
        for group in (attributions or [])
        for a in (group or [])
    )
    return {
        "families_tracked": ss.get("families_tracked") or len(counts),
        "best_validated_family": best_validated or None,
        "noisy_family": noisiest or None,
        "useful_families": ss.get("useful_families") or [],
        "noisy_families": ss.get("noisy_families") or [],
        "harmful_families": ss.get("harmful_families") or [],
        "aggregate_sample_size": total_n,
        "learning_mode": total_n < MIN_VALIDATED_SAMPLE,
        "evidence_source": ss.get("evidence_source", "live_forward"),
        "may_authorize_deploy": False,
        "authority_effect": "none",
    }
