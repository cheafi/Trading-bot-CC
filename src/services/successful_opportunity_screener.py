"""
Successful Opportunity Screener — 10 screen categories with sample-gated labels.

Promising vs successful labels require minimum sample thresholds; never inflate hit rates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SCREEN_CATEGORIES: tuple[str, ...] = (
    "setup_structure",
    "risk_reward",
    "regime_alignment",
    "liquidity",
    "sector_theme",
    "momentum_follow_through",
    "volume_confirmation",
    "catalyst_proximity",
    "portfolio_fit",
    "cost_survival",
)

PROMISING_MIN_SAMPLE = 8
SUCCESSFUL_MIN_SAMPLE = 20


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _screen_result(
    category: str,
    passed: bool,
    *,
    sample_size: int,
    note: str = "",
) -> Dict[str, Any]:
    label = "insufficient"
    if sample_size >= SUCCESSFUL_MIN_SAMPLE and passed:
        label = "successful"
    elif sample_size >= PROMISING_MIN_SAMPLE and passed:
        label = "promising"
    elif passed:
        label = "heuristic_pass"
    else:
        label = "fail"
    return {
        "category": category,
        "passed": passed,
        "label": label,
        "sample_size": sample_size,
        "note": note,
    }


def screen_opportunity(
    row: Dict[str, Any],
    *,
    evidence: Optional[Dict[str, Any]] = None,
    calibration: Optional[Dict[str, Any]] = None,
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    r = dict(row or {})
    ev = dict(evidence or {})
    cal = dict(calibration or {})
    t = dict(truth or {})
    n = int(cal.get("sample_size") or 0)

    fam_scores = {f["family"]: f.get("score") or 0 for f in (ev.get("families") or []) if f.get("family")}
    rr = _float(r.get("risk_reward") or r.get("rr_ratio"))
    score = _float(r.get("score"))

    screens: List[Dict[str, Any]] = [
        _screen_result(
            "setup_structure",
            score >= 6.0 and fam_scores.get("setup_quality", 0) >= 0.5,
            sample_size=n,
            note="Structure score threshold",
        ),
        _screen_result(
            "risk_reward",
            rr >= 2.0 and fam_scores.get("rr_quality", 0) >= 0.45,
            sample_size=n,
            note="R:R gate",
        ),
        _screen_result(
            "regime_alignment",
            fam_scores.get("regime", 0) >= 0.5,
            sample_size=n,
            note=str(t.get("regime_state") or t.get("tradeability") or ""),
        ),
        _screen_result(
            "liquidity",
            fam_scores.get("liquidity", 0) >= 0.45,
            sample_size=n,
        ),
        _screen_result(
            "sector_theme",
            bool(r.get("sector") or r.get("theme") or r.get("sector_type")),
            sample_size=n,
        ),
        _screen_result(
            "momentum_follow_through",
            fam_scores.get("relative_strength", 0) >= 0.5 or fam_scores.get("trend", 0) >= 0.5,
            sample_size=n,
        ),
        _screen_result(
            "volume_confirmation",
            fam_scores.get("volume", 0) >= 0.45,
            sample_size=n,
        ),
        _screen_result(
            "catalyst_proximity",
            fam_scores.get("catalyst", 0) >= 0.4,
            sample_size=n,
        ),
        _screen_result(
            "portfolio_fit",
            fam_scores.get("portfolio_fit", 0) >= 0.5,
            sample_size=n,
        ),
        _screen_result(
            "cost_survival",
            not cal.get("cost_drag_r") or float(cal.get("cost_drag_r") or 0) < 0.5,
            sample_size=n,
            note="Cost drag below 0.5R",
        ),
    ]

    passed_count = sum(1 for s in screens if s["passed"])
    successful_count = sum(1 for s in screens if s["label"] == "successful")
    promising_count = sum(1 for s in screens if s["label"] == "promising")

    if n >= SUCCESSFUL_MIN_SAMPLE and successful_count >= 6:
        pattern_status = "successful_pattern"
    elif n >= PROMISING_MIN_SAMPLE and promising_count >= 5:
        pattern_status = "promising_pattern"
    elif passed_count >= 5:
        pattern_status = "heuristic_pass"
    else:
        pattern_status = "unvalidated"

    labels = [f"{s['category']}:{s['label']}" for s in screens if s["passed"]][:6]

    return {
        "categories": screens,
        "passed_count": passed_count,
        "total_categories": len(SCREEN_CATEGORIES),
        "pattern_status": pattern_status,
        "labels": labels,
        "promising_threshold": PROMISING_MIN_SAMPLE,
        "successful_threshold": SUCCESSFUL_MIN_SAMPLE,
        "evidence_only": True,
        "may_authorize_deploy": False,
    }
