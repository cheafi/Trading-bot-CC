"""
Opportunity Calibration — hit rate ranges, expectancy, cost-adjusted outcomes.

Uses forward outcomes + signal attribution + no-edge tracking. Learning mode when n low.
No validated status without walk-forward evidence.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.signal_family_attribution import MIN_VALIDATED_SAMPLE, MIN_IMPROVING_SAMPLE

MIN_WALK_FORWARD_SAMPLE = 20
MIN_LEARNING_SAMPLE = 5


def _float(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _hit_rate_range(
    *,
    sample_size: int,
    win_rate: Optional[float],
    learning_mode: bool,
) -> Dict[str, Any]:
    if sample_size < MIN_LEARNING_SAMPLE or win_rate is None:
        return {
            "low": None,
            "high": None,
            "display": "learning",
            "sample_size": sample_size,
        }
    spread = 0.25 if learning_mode or sample_size < MIN_VALIDATED_SAMPLE else 0.12
    low = max(0.0, round(win_rate - spread, 2))
    high = min(1.0, round(win_rate + spread, 2))
    return {
        "low": low,
        "high": high,
        "display": f"{int(low * 100)}–{int(high * 100)}%",
        "sample_size": sample_size,
    }


def _expectancy_range(
    *,
    sample_size: int,
    mean_r: Optional[float],
    learning_mode: bool,
) -> Dict[str, Any]:
    if sample_size < MIN_LEARNING_SAMPLE or mean_r is None:
        return {
            "low": None,
            "high": None,
            "display": "learning",
            "sample_size": sample_size,
        }
    spread = 0.8 if learning_mode or sample_size < MIN_VALIDATED_SAMPLE else 0.4
    low = round(max(-3.0, mean_r - spread), 1)
    high = round(min(6.0, mean_r + spread), 1)
    return {
        "low": low,
        "high": high,
        "display": f"{low}–{high}R",
        "sample_size": sample_size,
    }


def _resolve_calibration_state(
    *,
    sample_size: int,
    walk_forward_n: int,
    learning_mode: bool,
    evidence_source: str = "live_forward",
) -> str:
    if evidence_source == "backtest":
        return "backtest_isolated"
    if sample_size < MIN_LEARNING_SAMPLE:
        return "learning"
    if walk_forward_n < MIN_WALK_FORWARD_SAMPLE:
        return "insufficient_walk_forward"
    if sample_size >= MIN_VALIDATED_SAMPLE and walk_forward_n >= MIN_WALK_FORWARD_SAMPLE:
        return "validated"
    if sample_size >= MIN_IMPROVING_SAMPLE:
        return "improving"
    return "learning"


def calibrate_opportunity(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    forward_summary: Optional[Dict[str, Any]] = None,
    attribution_calibrations: Optional[Dict[str, Any]] = None,
    no_edge_tracking: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    r = dict(row or {})
    fwd = dict(forward_summary or {})
    attr = dict(attribution_calibrations or {})
    ne = dict(no_edge_tracking or {})

    ev = r.get("setup_evidence") or r.get("evidence") or {}
    sample_size = _int(ev.get("sample_size") or ev.get("n_closed"))
    if not sample_size:
        sample_size = _int(fwd.get("sample_size"))

    family = str(r.get("setup_family") or r.get("family") or r.get("scanner") or "")
    fam_cal = {}
    if family and isinstance(attr.get(family), dict):
        fam_cal = attr[family]
    elif isinstance(attr, dict):
        for _k, v in attr.items():
            if isinstance(v, dict) and v.get("sample_size"):
                fam_cal = v
                break

    if fam_cal:
        sample_size = max(sample_size, _int(fam_cal.get("sample_size")))

    win_rate = _float(fam_cal.get("win_rate") or fwd.get("win_rate"))
    mean_r = _float(
        fam_cal.get("forward_r_mean")
        or fwd.get("avg_forward_r_5d")
        or r.get("expected_r")
    )
    walk_forward_n = _int(fam_cal.get("walk_forward_n") or fwd.get("walk_forward_n"))
    evidence_source = str(fam_cal.get("evidence_source") or fwd.get("outcome_source") or "live_forward")

    learning_mode = sample_size < MIN_VALIDATED_SAMPLE or walk_forward_n < MIN_WALK_FORWARD_SAMPLE
    state = _resolve_calibration_state(
        sample_size=sample_size,
        walk_forward_n=walk_forward_n,
        learning_mode=learning_mode,
        evidence_source=evidence_source,
    )

    from src.services.cost_slippage_model import estimate_cost_adjusted_r

    cost_adj = estimate_cost_adjusted_r(r, expected_r=mean_r, truth=truth)
    cost_drag_r = cost_adj.get("cost_drag_r")

    no_edge_label = ne.get("quality_label")
    attribution_note = ""
    if evidence_source == "backtest":
        attribution_note = "Backtest isolated — not live proof"
    elif no_edge_label in ("infra_blocked", "quality_blocked"):
        attribution_note = f"No-edge context: {no_edge_label}"

    return {
        "state": state,
        "learning_mode": learning_mode,
        "sample_size": sample_size,
        "walk_forward_n": walk_forward_n,
        "hit_rate_range": _hit_rate_range(
            sample_size=sample_size,
            win_rate=win_rate,
            learning_mode=learning_mode,
        ),
        "expectancy_range": _expectancy_range(
            sample_size=sample_size,
            mean_r=mean_r,
            learning_mode=learning_mode,
        ),
        "cost_drag_r": cost_drag_r,
        "cost_adjusted_expected_r": cost_adj.get("cost_adjusted_expected_r"),
        "evidence_source": evidence_source,
        "attribution_note": attribution_note,
        "no_edge_quality": no_edge_label,
        "validated_requires_walk_forward": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "display_note": (
            "Learning mode — ranges widen until walk-forward n≥20"
            if learning_mode
            else "Cost-adjusted expectancy from live forward study"
        ),
    }
