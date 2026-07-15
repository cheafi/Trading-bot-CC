"""
Opportunity Quality Engine — rank by decision quality, not excitement.

Recommended actions are gated by page authority. No deploy_candidate unless
authority chain permits. Low sample widens confidence band.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.signal_family_attribution import (
    MIN_VALIDATED_SAMPLE,
    attribute_families_for_row,
    extract_active_families,
)

QUALITY_BUCKETS: tuple[str, ...] = (
    "no_edge",
    "research_only",
    "monitor",
    "near_miss",
    "paper_candidate",
    "deploy_candidate",
    "retire_signal",
)

RECOMMENDED_ACTIONS: tuple[str, ...] = (
    "do_nothing",
    "monitor",
    "create_alert",
    "review_dossier",
    "promote_to_playbook_review",
    "paper_test",
    "deploy_review",
    "reduce_exposure",
    "retire_rule",
)

_RESEARCH_SURFACES = frozenset({"dossier", "research", "strategy_lab", "backtest", "guide"})


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _sample_size(row: Dict[str, Any]) -> int:
    ev = row.get("setup_evidence") or row.get("evidence") or {}
    n = ev.get("sample_size") or ev.get("n_closed")
    if n is not None:
        return int(n)
    cal = row.get("calibration") or {}
    return int(cal.get("n_closed") or 0)


def _evidence_conflicts(row: Dict[str, Any], families: List[Dict[str, Any]]) -> bool:
    if row.get("evidence_conflict") or row.get("regime_conflict"):
        return True
    statuses = {str(f.get("status")) for f in families}
    return "noisy" in statuses and "validated" in statuses


def _cost_erases_edge(row: Dict[str, Any]) -> bool:
    gross = _float(row.get("score") or row.get("gross_edge_score"))
    net = _float(row.get("net_deploy_score") or row.get("net_edge_score"), gross)
    if gross > 0 and net < gross * 0.55:
        return True
    slip = row.get("execution_slippage_bps")
    if slip is not None and float(slip) > 35:
        return True
    return bool(row.get("cost_erases_edge"))


def _expected_r_range(row: Dict[str, Any], rr: float) -> Dict[str, Any]:
    """Range not point — avoid fake precision."""
    n = _sample_size(row)
    if n < 5:
        return {"low": None, "high": None, "display": "learning", "sample_size": n}
    base = _float(row.get("expected_r"), rr * 0.35 if rr > 0 else 0.0)
    spread = 0.6 if n < MIN_VALIDATED_SAMPLE else 0.35
    low = round(max(-2.0, base - spread), 1)
    high = round(min(5.0, base + spread), 1)
    return {
        "low": low,
        "high": high,
        "display": f"{low}–{high}R",
        "sample_size": n,
    }


def _confidence_band(row: Dict[str, Any], *, conflicts: bool, n: int) -> str:
    if n < 5:
        return "wide — learning"
    if n < MIN_VALIDATED_SAMPLE or conflicts:
        return "wide"
    thesis = _float(row.get("thesis_conf"), 0.5)
    data = _float(row.get("data_conf"), 0.5)
    spread = abs(thesis - data)
    if spread > 0.3:
        return "wide"
    return "moderate" if n < MIN_VALIDATED_SAMPLE else "narrow"


def _quality_bucket(
    row: Dict[str, Any],
    *,
    truth: Dict[str, Any],
    surface: str,
    conflicts: bool,
    cost_fail: bool,
) -> str:
    action = str(row.get("action") or "WATCH").upper()
    if action in ("AVOID", "NO_TRADE", "BLOCKED", "PASS", "EXIT"):
        return "retire_signal" if row.get("retire_signal") else "no_edge"
    if surface in _RESEARCH_SURFACES:
        return "research_only"
    if not truth.get("deploy_authority"):
        if row.get("near_miss") or str(row.get("bucket")) == "near_miss":
            return "near_miss"
        return "monitor"
    er = truth.get("execution_readiness") or {}
    if not er.get("broker_connected"):
        return "monitor"
    if cost_fail or conflicts:
        return "near_miss"
    if action in ("TRADE", "DEPLOY", "STRONG_TRADE") and row.get("execution_ready"):
        return "deploy_candidate"
    if action == "PILOT" and er.get("broker_connected"):
        return "paper_candidate"
    if _float(row.get("score")) >= 7.0:
        return "near_miss"
    return "monitor"


def _recommended_action(
    bucket: str,
    *,
    truth: Dict[str, Any],
    surface: str,
) -> str:
    if surface in _RESEARCH_SURFACES:
        return "review_dossier"
    if not truth.get("deploy_authority"):
        if bucket == "near_miss":
            return "promote_to_playbook_review"
        return "monitor"
    if bucket == "deploy_candidate":
        return "deploy_review"
    if bucket == "paper_candidate":
        return "paper_test"
    if bucket in ("no_edge", "retire_signal"):
        return "do_nothing"
    if bucket == "near_miss":
        return "promote_to_playbook_review"
    return "monitor"


def evaluate_opportunity_quality(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    surface: str = "playbook",
    forward_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate decision quality for one candidate row."""
    t = dict(truth or {})
    brief_expired = bool(t.get("brief_expired"))
    families = attribute_families_for_row(row, truth=t)
    if brief_expired:
        families = [f for f in families if f.get("family") not in ("setup_quality", "timing", "catalyst")]
    conflicts = _evidence_conflicts(row, families)
    cost_fail = _cost_erases_edge(row)
    n = _sample_size(row)
    rr = _float(row.get("risk_reward") or row.get("rr_ratio"))
    bucket = _quality_bucket(row, truth=t, surface=surface, conflicts=conflicts, cost_fail=cost_fail)
    er = t.get("execution_readiness") or {}
    if not er.get("broker_connected"):
        bucket = "monitor" if bucket == "deploy_candidate" else bucket
    if surface in _RESEARCH_SURFACES and bucket == "deploy_candidate":
        bucket = "research_only"
    rec = _recommended_action(bucket, truth=t, surface=surface)
    if bucket == "deploy_candidate" and not t.get("deploy_authority"):
        bucket = "monitor"
        rec = "monitor"
    r_range = _expected_r_range(row, rr)
    primary_edge = extract_active_families(row, truth=t)[:2]
    missing: List[str] = []
    if n < MIN_VALIDATED_SAMPLE:
        missing.append(f"sample n={n} — need ≥{MIN_VALIDATED_SAMPLE}")
    if not row.get("invalidation"):
        missing.append("invalidation not explicit")
    if conflicts:
        missing.append("signal family conflict")
    if cost_fail:
        missing.append("cost/slippage erases edge")
    if brief_expired:
        missing.append("brief expired — brief features excluded")
    quality = round(
        0.30 * min(10.0, _float(row.get("score"))) / 10.0
        + 0.25 * min(3.0, rr) / 3.0
        + 0.20 * _float(row.get("data_conf"), 0.5)
        + 0.15 * (0.0 if conflicts else 0.8)
        + 0.10 * (0.0 if cost_fail else 0.7),
        2,
    )
    if conflicts:
        quality = round(quality * 0.75, 2)
    if cost_fail:
        quality = round(quality * 0.7, 2)
    grade = "C"
    if quality >= 0.72 and n >= MIN_VALIDATED_SAMPLE and not conflicts:
        grade = "B"
    elif quality >= 0.55:
        grade = "B-"
    elif quality < 0.35 or bucket == "no_edge":
        grade = "D"
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "opportunity_quality": quality,
        "expected_r": r_range,
        "confidence_band": _confidence_band(row, conflicts=conflicts, n=n),
        "quality_bucket": bucket,
        "evidence_grade": grade,
        "sample_size": n,
        "primary_edge": primary_edge,
        "primary_risk": missing[:2],
        "missing_evidence": missing,
        "recommended_action": rec,
        "no_edge_reason": str(t.get("primary_blocker") or "") if bucket == "no_edge" else "",
        "signal_families": families,
        "cost_adjusted_pass": not cost_fail,
        "portfolio_fit_pass": str(row.get("portfolio_fit") or "").lower() in ("allowed", "diversifier", ""),
        "evidence_conflict": conflicts,
        "authority_gated": not t.get("deploy_authority"),
        "may_authorize_deploy": False,
        "forward_stats": forward_stats or {},
    }


def build_playbook_quality_chip(
    row: Dict[str, Any],
    quality: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact chip payload for Playbook rows."""
    q = quality or evaluate_opportunity_quality(row)
    n = int(q.get("sample_size") or 0)
    r_disp = (q.get("expected_r") or {}).get("display") or "learning"
    roi_range = (q.get("expected_r") or {}).get("display") or "learning"
    fam_status = "learning"
    families = q.get("signal_families") or []
    if families:
        statuses = [str(f.get("status")) for f in families]
        if "validated" in statuses:
            fam_status = "validated"
        elif "noisy" in statuses:
            fam_status = "noisy"
        elif n < 5:
            fam_status = "learning"
        else:
            fam_status = "unvalidated"
    action = str(q.get("recommended_action") or "monitor")
    oie = row.get("opportunity_intel") or row.get("opportunity_intelligence") or {}
    evidence_grade = str(oie.get("evidence_grade") or row.get("evidence_grade") or "ungraded")
    pattern_status = str(oie.get("pattern_status") or row.get("pattern_status") or fam_status)
    labels = [f"grade {evidence_grade}", f"ROI {roi_range}", f"n={n}"]
    if q.get("evidence_conflict"):
        labels.append("conflict")
    elif pattern_status in ("successful_pattern", "promising_pattern"):
        labels.append(pattern_status.replace("_", " "))
    elif fam_status == "learning":
        labels.append("learning")
    else:
        labels.append(fam_status)
    labels.append("cost ✓" if q.get("cost_adjusted_pass") else "cost ✗")
    labels.append("fit ✓" if q.get("portfolio_fit_pass") else "fit ✗")
    labels.append(action.replace("_", " "))
    return {
        "chips": labels,
        "expected_r_display": r_disp,
        "roi_range": roi_range,
        "evidence_grade": evidence_grade,
        "pattern_status": pattern_status,
        "sample_size": n,
        "family_status": fam_status,
        "cost_adjusted": q.get("cost_adjusted_pass"),
        "portfolio_fit": q.get("portfolio_fit_pass"),
        "action_label": action.replace("_", " "),
        "learning": n < 5,
        "conflict": bool(q.get("evidence_conflict")),
        "not_permission": True,
        "advanced_evidence_collapsed": True,
    }


def rank_by_decision_quality(
    candidates: List[Dict[str, Any]],
    *,
    truth: Optional[Dict[str, Any]] = None,
    surface: str = "playbook",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Rank candidates by decision quality — not excitement."""
    t = dict(truth or {})
    ranked: List[Dict[str, Any]] = []
    for row in candidates or []:
        sym = str(row.get("ticker") or "").upper().strip()
        if not sym:
            continue
        q = evaluate_opportunity_quality(row, truth=t, surface=surface)
        ranked.append({**q, "research_rank": q["opportunity_quality"]})
    return sorted(ranked, key=lambda x: x.get("opportunity_quality", 0), reverse=True)[:limit]


def attach_quality_to_rows(
    rows: List[Dict[str, Any]],
    *,
    truth: Optional[Dict[str, Any]] = None,
    surface: str = "playbook",
) -> List[Dict[str, Any]]:
    """Attach quality_chip to each row for Playbook UI."""
    t = dict(truth or {})
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        r = dict(row)
        q = evaluate_opportunity_quality(r, truth=t, surface=surface)
        r["opportunity_quality_eval"] = q
        r["quality_chip"] = build_playbook_quality_chip(r, q)
        fams = extract_active_families(r, truth=t)
        r["signal_families"] = fams
        out.append(r)
    return out


def build_decision_quality_dashboard(
    *,
    truth: Optional[Dict[str, Any]] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    journal: Optional[Dict[str, Any]] = None,
    forward_summary: Optional[Dict[str, Any]] = None,
    family_health: Optional[Dict[str, Any]] = None,
    capital: Optional[Dict[str, Any]] = None,
    rule_summary: Optional[Dict[str, Any]] = None,
    no_edge_tracking: Optional[Dict[str, Any]] = None,
    journal_store_summary: Optional[Dict[str, Any]] = None,
    outcome_store_summary: Optional[Dict[str, Any]] = None,
    alpha_quality: Optional[Dict[str, Any]] = None,
    alpha_review: Optional[Dict[str, Any]] = None,
    threshold_governance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact Dashboard decision_quality block."""
    t = dict(truth or {})
    fwd = dict(forward_summary or {})
    fh = dict(family_health or {})
    cap = dict(capital or {})
    ne = dict(no_edge_tracking or {})
    js = dict(journal_store_summary or {})
    os_ = dict(outcome_store_summary or fwd)
    n = int(fwd.get("sample_size") or 0)
    agg_n = int(fh.get("aggregate_sample_size") or 0)
    journal_n = int(js.get("total") or (journal or {}).get("summary", {}).get("total") or 0)
    outcome_n = int(os_.get("total_outcomes") or os_.get("distinct_events") or 0)
    no_edge_n = int(ne.get("no_edge_samples") or 0)
    learning = n < 5 and agg_n < MIN_VALIDATED_SAMPLE
    state = "learning"
    if n >= MIN_VALIDATED_SAMPLE:
        state = "validated"
    elif n >= 5 or agg_n >= 8:
        state = "insufficient_evidence"
    deploy_events = [
        e
        for e in (journal or {}).get("events") or []
        if e.get("event_type") == "DEPLOY_CANDIDATE"
    ][-20:]
    useful_families = fh.get("useful_families") or []
    noisy_families = fh.get("noisy_families") or []
    aq = dict(alpha_quality or {})
    ar = dict(alpha_review or {})
    tg = dict(threshold_governance or {})
    return {
        "title": "Decision Quality",
        "state": state,
        "state_label": (
            "Learning mode"
            if learning
            else "Validated"
            if state == "validated"
            else "Insufficient evidence"
        ),
        "banner": (
            "Learning mode — not enough live forward outcomes for calibration"
            if learning
            else fwd.get("display_note") or "Forward outcome study active"
        ),
        "metrics": {
            "deploy_candidates_tracked": len(deploy_events),
            "journal_events_n": journal_n,
            "forward_outcomes_n": outcome_n,
            "no_edge_samples_n": no_edge_n,
            "forward_r_5d": fwd.get("avg_forward_r_5d") if n >= 5 else None,
            "watch_to_deploy_conversion": fwd.get("watch_to_deploy_conversion"),
            "false_deploy_rate": fwd.get("false_deploy_rate") if n >= 5 else None,
            "avoided_loss_count": fwd.get("avoided_loss_count"),
            "no_edge_days_protected": 1 if int(t.get("deploy_qualified_count") or 0) < 1 else 0,
            "best_validated_family": fh.get("best_validated_family"),
            "noisy_family": fh.get("noisy_family"),
            "useful_families": useful_families[:3],
            "noisy_families": noisy_families[:3],
            "sample_size": max(n, agg_n),
            "learning_mode": learning,
            "outcome_source": fwd.get("outcome_source", "forward_outcome_backfill"),
            "authority_effect": "none",
        },
        "capital_mode": cap.get("capital_mode"),
        "capital_deploy_allowed": bool(cap.get("deploy_allowed")),
        "governor_adjustment": cap.get("learning_adjustment_reason"),
        "risk_mode_adjustment": cap.get("risk_mode_adjustment"),
        "requires_human_review": bool(cap.get("requires_human_review")),
        "no_edge_quality": ne.get("quality_label"),
        "rule_learning": rule_summary or {},
        "top_ranked_by_quality": rank_by_decision_quality(
            (candidates or []) + list(near_miss or []),
            truth=t,
            limit=3,
        ),
        "collapsed": True,
        "details_available": True,
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "labels": {
            "forward_study": "forward outcome study",
            "cash_protected": "cash protected",
            "no_fake_precision": True,
        },
        "alpha_quality": aq
        if aq
        else {
            "sample_size": 0,
            "status": "learning",
            "status_label": "learning",
            "oi_lift_display": "learning",
            "cost_adj_expectancy_display": "learning",
            "conversion_quality": "learning",
            "overfit_risk": "medium",
            "allow_green_ui": False,
            "learning_mode": True,
            "empty_message": "Learning — not enough forward outcomes yet",
        },
        "alpha_review": ar
        if ar
        else {
            "status": "learning",
            "status_label": "learning",
            "evidence_level": "learning",
            "human_review_count": 0,
            "what_improved": [],
            "what_deteriorated": [],
            "top_items": [],
            "governor_review": {},
            "next_actions": [],
            "threshold_review_line": "Review only · no live changes",
            "empty_message": "No review items yet",
            "collapsed": True,
            "authority_effect": "none",
            "may_authorize_deploy": False,
        },
        "threshold_governance": tg
        if tg
        else {
            "open_count": 0,
            "shadow_count": 0,
            "registry_count": 0,
            "status_line": "Threshold Review: 0 open · 0 shadow · Review only · no live changes",
            "empty_message": "No threshold proposals yet",
        },
    }
