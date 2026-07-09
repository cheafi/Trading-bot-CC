"""
Alpha Quality Evaluator — OI control tower report from persisted learning.

Compares OI vs baselines, detects hit-rate trap and payoff degradation.
authority_effect=none; never authorizes deploy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.services.alpha_quality_store import (
    AlphaQualityBySignalFamily,
    AlphaQualityByStage,
    AlphaQualitySnapshot,
    AlphaQualityStore,
    MIN_SAMPLES_LEARNING,
    MIN_SAMPLES_LIFT,
    get_alpha_quality_store,
    make_snapshot_id,
)
from src.services.missed_opportunity_review import review_missed_opportunities
from src.services.opportunity_baseline_comparison import compare_oi_to_baselines
from src.services.overfit_guard import assess_overfit_risk
from src.services.signal_family_attribution import MIN_VALIDATED_SAMPLE

ALPHA_STATUSES: tuple[str, ...] = (
    "learning",
    "improving",
    "stable",
    "noisy",
    "deteriorating",
    "insufficient_data",
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _display_expectancy(mean_r: Optional[float], n: int, *, cost_adj: bool = False) -> str:
    if n < MIN_SAMPLES_LEARNING:
        return "learning"
    if mean_r is None:
        return "insufficient"
    prefix = "net " if cost_adj else ""
    return f"{prefix}{mean_r:+.2f}R"


def _hit_rate_trap(
    hit_rate: Optional[float],
    expectancy: Optional[float],
    *,
    n: int,
) -> bool:
    if n < MIN_SAMPLES_LIFT or hit_rate is None or expectancy is None:
        return False
    return hit_rate > 0.55 and expectancy < 0.15


def _payoff_degradation(
    recent_mean: Optional[float],
    prior_mean: Optional[float],
    *,
    n: int,
) -> bool:
    if n < MIN_SAMPLES_LIFT or recent_mean is None or prior_mean is None:
        return False
    return prior_mean > 0.2 and recent_mean < prior_mean * 0.5


def _resolve_status(
    *,
    n: int,
    overfit_risk: str,
    hit_trap: bool,
    payoff_deg: bool,
    oi_lift: Optional[float],
    false_positive_rate: float,
) -> str:
    if n < MIN_SAMPLES_LEARNING:
        return "learning"
    if n < MIN_SAMPLES_LIFT:
        return "insufficient_data"
    if overfit_risk == "high" or hit_trap:
        return "noisy"
    if payoff_deg or false_positive_rate > 0.25:
        return "deteriorating"
    if oi_lift is not None and oi_lift > 0.15:
        return "improving"
    if oi_lift is not None and abs(oi_lift) < 0.1 and false_positive_rate < 0.15:
        return "stable"
    return "insufficient_data"


def _by_stage_rows(
    opportunities: Sequence[Dict[str, Any]],
    *,
    horizon: int = 5,
) -> List[Dict[str, Any]]:
    by_stage: Dict[str, List[Dict[str, Any]]] = {}
    for row in opportunities:
        stage = str(row.get("stage") or row.get("quality_bucket") or "unknown")
        by_stage.setdefault(stage, []).append(row)
    out: List[Dict[str, Any]] = []
    for stage, rows in sorted(by_stage.items()):
        n = len(rows)
        fwd = [_float(r.get(f"forward_r_{horizon}d") or r.get("forward_r")) for r in rows if r.get("forward_r") is not None or r.get(f"forward_r_{horizon}d") is not None]
        mean_r = round(sum(fwd) / len(fwd), 3) if fwd else None
        hits = sum(1 for v in fwd if v > 0)
        hit_rate = hits / len(fwd) if fwd else None
        row = AlphaQualityByStage(
            stage=stage,
            sample_size=n,
            hit_rate_display="learning" if n < MIN_SAMPLES_LEARNING else (f"{hit_rate:.0%}" if hit_rate is not None else "insufficient"),
            expectancy_display=_display_expectancy(mean_r, n),
            cost_adj_expectancy_display=_display_expectancy(mean_r * 0.85 if mean_r is not None else None, n, cost_adj=True),
            conversion_rate_display="learning" if n < MIN_SAMPLES_LEARNING else None,
            lift_vs_baseline="learning" if n < MIN_SAMPLES_LIFT else None,
        )
        out.append(row.to_dict())
    return out


def _by_family_rows(
    attribution: Optional[Dict[str, Any]],
    *,
    overfit_label_cap: str,
) -> List[Dict[str, Any]]:
    families = (attribution or {}).get("families") or (attribution or {}).get("by_family") or []
    if isinstance(attribution, dict) and not families:
        for key, val in attribution.items():
            if isinstance(val, dict) and val.get("family"):
                families.append(val)
    out: List[Dict[str, Any]] = []
    for fam in families:
        if not isinstance(fam, dict):
            continue
        name = str(fam.get("family") or fam.get("name") or "unknown")
        n = int(fam.get("sample_size") or fam.get("n") or 0)
        mean_r = fam.get("forward_r_mean")
        if mean_r is not None:
            mean_r = _float(mean_r)
        status = str(fam.get("status") or "learning")
        if overfit_label_cap == "learning":
            status = "learning"
        elif overfit_label_cap == "promising" and status == "validated":
            status = "promising"
        row = AlphaQualityBySignalFamily(
            family=name,
            sample_size=n,
            hit_rate_display="learning" if n < MIN_SAMPLES_LEARNING else str(fam.get("hit_rate_display") or "unvalidated"),
            expectancy_display=_display_expectancy(mean_r, n),
            cost_adj_expectancy_display=_display_expectancy(mean_r * 0.85 if mean_r is not None else None, n, cost_adj=True),
            status=status,
            overfit_capped=overfit_label_cap != "validated",
        )
        out.append(row.to_dict())
    return out


def evaluate_alpha_quality(
    *,
    opportunities: Optional[Sequence[Dict[str, Any]]] = None,
    score_snapshots: Optional[Sequence[Dict[str, Any]]] = None,
    stage_transitions: Optional[Sequence[Dict[str, Any]]] = None,
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
    forward_summary: Optional[Dict[str, Any]] = None,
    attribution: Optional[Dict[str, Any]] = None,
    no_edge_tracking: Optional[Dict[str, Any]] = None,
    capital_governor: Optional[Dict[str, Any]] = None,
    discovery_hits: Optional[Sequence[Dict[str, Any]]] = None,
    playbook_rows: Optional[Sequence[Dict[str, Any]]] = None,
    near_miss_rows: Optional[Sequence[Dict[str, Any]]] = None,
    sector_leaders: Optional[Sequence[Dict[str, Any]]] = None,
    window_days: int = 20,
    horizon: int = 5,
    persist: bool = False,
    store: Optional[AlphaQualityStore] = None,
) -> Dict[str, Any]:
    """Build AlphaQualityReport — advisory only."""
    oi_rows = list(opportunities or score_snapshots or forward_outcomes or [])
    fwd = dict(forward_summary or {})
    n = int(fwd.get("sample_size") or len(oi_rows))
    false_positive_rate = _float(fwd.get("false_deploy_rate") or 0)

    baseline = compare_oi_to_baselines(
        oi_outcomes=oi_rows,
        forward_summary=fwd,
        discovery_hits=discovery_hits,
        playbook_rows=playbook_rows,
        near_miss_rows=near_miss_rows,
        sector_leaders=sector_leaders,
        horizon=horizon,
    )
    oi_mean = (baseline.get("oi_cohort") or {}).get("mean_forward_r")
    best_lift = (baseline.get("lifts") or {}).get(baseline.get("best_baseline") or "", {})
    oi_lift = best_lift.get("lift_r")

    gross_exp = oi_mean
    net_exp = oi_mean * 0.85 if oi_mean is not None else None
    cost_erases = gross_exp is not None and net_exp is not None and gross_exp > 0 and net_exp < gross_exp * 0.55

    overfit = assess_overfit_risk(
        sample_size=n,
        opportunities=oi_rows,
        forward_outcomes=forward_outcomes or oi_rows,
        sector_concentration=_float((capital_governor or {}).get("sector_concentration")),
        cost_erases_edge=cost_erases,
        gross_expectancy=gross_exp,
        net_expectancy=net_exp,
        walk_forward_stable=n >= MIN_VALIDATED_SAMPLE,
    )

    missed = review_missed_opportunities(
        near_miss_rows=near_miss_rows,
        truth=(capital_governor or {}).get("truth"),
        forward_outcomes=forward_outcomes,
    )

    recent_fwd = [_float(r.get("forward_r")) for r in (forward_outcomes or oi_rows)[-10:] if r.get("forward_r") is not None]
    prior_fwd = [_float(r.get("forward_r")) for r in (forward_outcomes or oi_rows)[:-10] if r.get("forward_r") is not None]
    recent_mean = round(sum(recent_fwd) / len(recent_fwd), 3) if recent_fwd else None
    prior_mean = round(sum(prior_fwd) / len(prior_fwd), 3) if prior_fwd else None

    hit_vals = [1 for v in recent_fwd if v > 0]
    hit_rate = len(hit_vals) / len(recent_fwd) if recent_fwd else None
    hit_trap = _hit_rate_trap(hit_rate, recent_mean, n=n)
    payoff_deg = _payoff_degradation(recent_mean, prior_mean, n=n)

    status = _resolve_status(
        n=n,
        overfit_risk=overfit["overfit_risk"],
        hit_trap=hit_trap,
        payoff_deg=payoff_deg,
        oi_lift=oi_lift,
        false_positive_rate=false_positive_rate,
    )

    conversion_quality = "learning"
    if n >= MIN_SAMPLES_LIFT:
        conv = fwd.get("watch_to_deploy_conversion")
        if conv is not None:
            conversion_quality = "strong" if _float(conv) > 0.35 else "weak" if _float(conv) < 0.15 else "moderate"
        else:
            conversion_quality = "insufficient_data"

    by_stage = _by_stage_rows(oi_rows, horizon=horizon)
    by_family = _by_family_rows(attribution, overfit_label_cap=overfit["label_cap"])

    governor_qa = {
        "qa_adjustment": None,
        "qa_reason_codes": [],
        "human_review_suggested": missed.get("human_review_suggested", False),
        "can_loosen_automatically": False,
        "authority_effect": "none",
    }

    report = {
        "title": "Alpha Quality",
        "status": status,
        "status_label": status.replace("_", " "),
        "sample_size": n,
        "window_days": window_days,
        "oi_lift_display": baseline.get("oi_lift_display", "learning"),
        "cost_adj_expectancy_display": _display_expectancy(net_exp, n, cost_adj=True),
        "conversion_quality": conversion_quality,
        "overfit_risk": overfit["overfit_risk"],
        "overfit_reason_codes": overfit.get("reason_codes", []),
        "hit_rate_trap": hit_trap,
        "payoff_degradation": payoff_deg,
        "by_stage": by_stage,
        "by_signal_family": by_family,
        "baseline_comparison": baseline,
        "missed_opportunity_review": missed,
        "governor_qa": governor_qa,
        "learning_mode": n < MIN_SAMPLES_LEARNING,
        "allow_green_ui": overfit.get("allow_green_ui", False) and n >= MIN_SAMPLES_LIFT,
        "false_positive_rate": false_positive_rate if n >= MIN_SAMPLES_LEARNING else None,
        "collapsed": True,
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "labels": {
            "no_fake_precision": True,
            "study_label": "forward outcome study",
        },
    }

    if persist:
        st = store or get_alpha_quality_store()
        snap = AlphaQualitySnapshot(
            snapshot_id=make_snapshot_id(),
            session_id=str((no_edge_tracking or {}).get("session_id") or ""),
            window_days=window_days,
            sample_size=n,
            status=status,
            oi_lift_display=report["oi_lift_display"],
            cost_adj_expectancy_display=report["cost_adj_expectancy_display"],
            conversion_quality=conversion_quality,
            overfit_risk=overfit["overfit_risk"],
            hit_rate_trap=hit_trap,
            payoff_degradation=payoff_deg,
            by_stage=by_stage,
            by_signal_family=by_family,
            baseline_comparison=baseline,
            missed_opportunity_summary={
                "dominant_classification": missed.get("dominant_classification"),
                "too_conservative_count": missed.get("too_conservative_count", 0),
            },
            governor_qa=governor_qa,
        )
        st.append_snapshot(snap)
        report["snapshot_id"] = snap.snapshot_id

    return report
