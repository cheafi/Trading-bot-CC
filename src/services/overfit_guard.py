"""
Overfit Guard — cap success labels when evidence is thin or fragile.

Checks: low n, filter count, concentration, outlier dominance, walk-forward,
cost erases edge. Caps labels at promising/learning when overfit_risk medium/high.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

MIN_SAMPLES_STABLE = 20
MIN_SAMPLES_LEARNING = 5
MAX_SAFE_FILTERS = 4
MAX_CONCENTRATION = 0.45
OUTLIER_DOMINANCE_THRESHOLD = 0.55


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _count_active_filters(row: Dict[str, Any]) -> int:
    tags = row.get("setup_tags") or row.get("filters") or []
    screens = row.get("screen_labels") or []
    return len(tags) + len(screens)


def _outlier_share(values: Sequence[float]) -> float:
    if len(values) < 3:
        return 0.0
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0
    top = max(abs(v) for v in values)
    return top / total


def assess_overfit_risk(
    *,
    sample_size: int = 0,
    opportunities: Optional[Sequence[Dict[str, Any]]] = None,
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
    filter_count: int = 0,
    sector_concentration: float = 0.0,
    ticker_concentration: float = 0.0,
    walk_forward_stable: Optional[bool] = None,
    cost_erases_edge: bool = False,
    gross_expectancy: Optional[float] = None,
    net_expectancy: Optional[float] = None,
) -> Dict[str, Any]:
    """Return overfit_risk low/medium/high with reason codes and label cap."""
    reasons: List[str] = []
    risk_score = 0

    if sample_size < MIN_SAMPLES_LEARNING:
        reasons.append("LOW_N")
        risk_score += 3
    elif sample_size < MIN_SAMPLES_STABLE:
        reasons.append("THIN_SAMPLE")
        risk_score += 2

    active_filters = filter_count
    if opportunities:
        active_filters = max(active_filters, max((_count_active_filters(r) for r in opportunities), default=0))
    if active_filters > MAX_SAFE_FILTERS:
        reasons.append("HIGH_FILTER_COUNT")
        risk_score += 2

    conc = max(sector_concentration, ticker_concentration)
    if conc > MAX_CONCENTRATION:
        reasons.append("CONCENTRATION")
        risk_score += 2

    fwd_vals = [
        _float(r.get("forward_r") or r.get(f"forward_r_5d"))
        for r in (forward_outcomes or [])
        if r.get("forward_r") is not None or r.get("forward_r_5d") is not None
    ]
    if _outlier_share(fwd_vals) > OUTLIER_DOMINANCE_THRESHOLD:
        reasons.append("OUTLIER_DOMINANCE")
        risk_score += 2

    if walk_forward_stable is False:
        reasons.append("WALK_FORWARD_UNSTABLE")
        risk_score += 3
    elif walk_forward_stable is None and sample_size < MIN_SAMPLES_STABLE:
        reasons.append("WALK_FORWARD_UNTESTED")
        risk_score += 1

    if cost_erases_edge:
        reasons.append("COST_ERASES_EDGE")
        risk_score += 3
    elif gross_expectancy is not None and net_expectancy is not None:
        if gross_expectancy > 0 and net_expectancy < gross_expectancy * 0.55:
            reasons.append("COST_ERASES_EDGE")
            risk_score += 2

    if risk_score >= 5:
        level = "high"
    elif risk_score >= 2:
        level = "medium"
    else:
        level = "low"

    label_cap = "validated"
    if level in ("medium", "high"):
        label_cap = "promising"
    if level == "high" or sample_size < MIN_SAMPLES_LEARNING:
        label_cap = "learning"

    return {
        "overfit_risk": level,
        "reason_codes": reasons[:6],
        "label_cap": label_cap,
        "risk_score": risk_score,
        "sample_size": sample_size,
        "allow_validated_label": level == "low" and sample_size >= MIN_SAMPLES_STABLE,
        "allow_green_ui": level == "low" and sample_size >= MIN_SAMPLES_STABLE,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "evidence_only": True,
    }
