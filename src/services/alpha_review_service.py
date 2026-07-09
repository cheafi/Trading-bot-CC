"""
Alpha Review Service — synthesize Alpha QA snapshots into a review report.

Inputs: alpha QA snapshots, baselines, overfit, missed opp, no-edge, attribution,
stage transitions, rule loop, governor QA.
Outputs: AlphaReviewReport — advisory only, authority_effect=none.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.services.alpha_quality_store import MIN_SAMPLES_LEARNING, MIN_SAMPLES_LIFT
from src.services.alpha_review_items import (
    ReviewItem,
    make_review_item,
    review_items_summary,
    sort_review_items,
)
from src.services.alpha_review_store import (
    AlphaReviewReport,
    AlphaReviewStore,
    get_alpha_review_store,
    make_report_id,
)
from src.services.human_review_queue import (
    HumanReviewQueue,
    get_human_review_queue,
    tasks_from_review_items,
)
from src.services.rule_learning_loop import apply_alpha_review_to_rules
from src.services.signal_family_attribution import MIN_VALIDATED_SAMPLE

ALPHA_REVIEW_STATUSES: tuple[str, ...] = (
    "learning",
    "insufficient_evidence",
    "mixed",
    "improving",
    "deteriorating",
    "needs_human_review",
    "stable",
)

EVIDENCE_LEVELS: tuple[str, ...] = (
    "learning",
    "thin",
    "moderate",
    "strong",
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _parse_cost_adj_expectancy(display: Optional[str]) -> Optional[float]:
    if not display or display in ("learning", "insufficient"):
        return None
    s = str(display).replace("net ", "").replace("R", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _overfit_pass(overfit: Dict[str, Any]) -> bool:
    return (
        str(overfit.get("overfit_risk") or "high") == "low"
        and bool(overfit.get("allow_validated_label") or overfit.get("allow_green_ui"))
    )


def _evidence_level(
    *,
    n: int,
    overfit: Dict[str, Any],
    min_sample: int,
) -> str:
    if n < MIN_SAMPLES_LEARNING:
        return "learning"
    if n < min_sample:
        return "thin"
    if not _overfit_pass(overfit):
        return "thin"
    if n >= MIN_VALIDATED_SAMPLE:
        return "strong"
    return "moderate"


def _delta_snapshots(
    snapshots: Sequence[Dict[str, Any]],
) -> tuple[List[str], List[str]]:
    if len(snapshots) < 2:
        return [], []
    prior = snapshots[-2]
    latest = snapshots[-1]
    improved: List[str] = []
    deteriorated: List[str] = []
    status_order = {
        "deteriorating": 0,
        "noisy": 1,
        "insufficient_data": 2,
        "learning": 3,
        "stable": 4,
        "improving": 5,
    }
    p_status = str(prior.get("status") or "learning")
    l_status = str(latest.get("status") or "learning")
    if status_order.get(l_status, 3) > status_order.get(p_status, 3):
        improved.append(f"status {p_status} → {l_status}")
    elif status_order.get(l_status, 3) < status_order.get(p_status, 3):
        deteriorated.append(f"status {p_status} → {l_status}")

    p_n = int(prior.get("sample_size") or 0)
    l_n = int(latest.get("sample_size") or 0)
    if l_n > p_n:
        improved.append(f"sample +{l_n - p_n}")
    elif l_n < p_n:
        deteriorated.append(f"sample {l_n - p_n}")

    p_over = str(prior.get("overfit_risk") or "medium")
    l_over = str(latest.get("overfit_risk") or "medium")
    risk_order = {"high": 0, "medium": 1, "low": 2}
    if risk_order.get(l_over, 1) > risk_order.get(p_over, 1):
        improved.append(f"overfit {p_over} → {l_over}")
    elif risk_order.get(l_over, 1) < risk_order.get(p_over, 1):
        deteriorated.append(f"overfit {p_over} → {l_over}")

    p_lift = str(prior.get("oi_lift_display") or "learning")
    l_lift = str(latest.get("oi_lift_display") or "learning")
    if p_lift == "learning" and l_lift not in ("learning", "insufficient"):
        improved.append(f"OI lift now {l_lift}")
    elif l_lift == "learning" and p_lift not in ("learning", "insufficient"):
        deteriorated.append("OI lift back to learning")

    return improved[:5], deteriorated[:5]


def _stage_conversion(
    transitions: Optional[Sequence[Dict[str, Any]]],
    *,
    alpha_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rows = list(transitions or [])
    by_from: Dict[str, int] = {}
    by_to: Dict[str, int] = {}
    for row in rows:
        fr = str(row.get("from_stage") or row.get("from") or "unknown")
        to = str(row.get("to_stage") or row.get("to") or "unknown")
        by_from[fr] = by_from.get(fr, 0) + 1
        by_to[to] = by_to.get(to, 0) + 1
    stages = (alpha_report or {}).get("by_stage") or []
    return {
        "transition_count": len(rows),
        "from_stages": dict(sorted(by_from.items())),
        "to_stages": dict(sorted(by_to.items())),
        "stage_rows": stages[:6],
        "conversion_quality": (alpha_report or {}).get("conversion_quality", "learning"),
        "authority_effect": "none",
    }


def _signal_family_review(
    attribution: Optional[Dict[str, Any]],
    *,
    alpha_report: Optional[Dict[str, Any]] = None,
    overfit: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    families = (alpha_report or {}).get("by_signal_family") or []
    if not families and attribution:
        families = (attribution.get("families") or attribution.get("by_family") or [])[:8]
    cap = str((overfit or {}).get("label_cap") or "learning")
    out: List[Dict[str, Any]] = []
    for fam in families:
        if not isinstance(fam, dict):
            continue
        status = str(fam.get("status") or "learning")
        if cap == "learning":
            status = "learning"
        elif cap == "promising" and status == "validated":
            status = "promising"
        out.append(
            {
                "family": fam.get("family") or fam.get("name"),
                "sample_size": int(fam.get("sample_size") or fam.get("n") or 0),
                "status": status,
                "expectancy_display": fam.get("expectancy_display", "learning"),
                "cost_adj_expectancy_display": fam.get(
                    "cost_adj_expectancy_display", "learning"
                ),
                "overfit_capped": cap != "validated",
                "authority_effect": "none",
            }
        )
    return out[:8]


def _build_review_items(
    *,
    n: int,
    min_sample: int,
    alpha_report: Dict[str, Any],
    overfit: Dict[str, Any],
    baselines: Dict[str, Any],
    missed: Dict[str, Any],
    no_edge: Dict[str, Any],
    governor_qa: Dict[str, Any],
    rule_summary: Dict[str, Any],
) -> List[ReviewItem]:
    items: List[ReviewItem] = []
    cost_adj = _parse_cost_adj_expectancy(alpha_report.get("cost_adj_expectancy_display"))
    net_positive = cost_adj is not None and cost_adj > 0

    if n < MIN_SAMPLES_LEARNING:
        items.append(
            make_review_item(
                title="Sample below learning threshold",
                category="sample",
                severity="info",
                summary=f"n={n} — collect more forward outcomes before lift labels",
                recommended_action="collect_more_samples",
                allowed_action="collect_more_samples",
            )
        )
    elif n < min_sample:
        items.append(
            make_review_item(
                title="Thin sample for review conclusions",
                category="sample",
                severity="warning",
                summary=f"n={n} < min_sample={min_sample}",
                recommended_action="collect_more_samples",
            )
        )

    if not _overfit_pass(overfit):
        items.append(
            make_review_item(
                title="Overfit guard not passed",
                category="overfit",
                severity="warning" if overfit.get("overfit_risk") == "medium" else "critical",
                summary=f"risk={overfit.get('overfit_risk')} codes={overfit.get('reason_codes', [])}",
                recommended_action="tighten",
                requires_human_review=overfit.get("overfit_risk") == "high",
            )
        )

    if n >= min_sample and not net_positive:
        items.append(
            make_review_item(
                title="Cost-adjusted expectancy not positive",
                category="baseline",
                severity="warning",
                summary=str(alpha_report.get("cost_adj_expectancy_display") or "learning"),
                recommended_action="tighten",
            )
        )

    lift = str(baselines.get("oi_lift_display") or alpha_report.get("oi_lift_display") or "learning")
    if lift == "learning" and n >= MIN_SAMPLES_LIFT:
        items.append(
            make_review_item(
                title="OI lift still in learning display",
                category="baseline",
                severity="info",
                recommended_action="collect_more_samples",
            )
        )

    if alpha_report.get("hit_rate_trap"):
        items.append(
            make_review_item(
                title="Hit-rate trap detected",
                category="baseline",
                severity="warning",
                summary="High hit rate with weak expectancy — payoff review",
                recommended_action="tighten",
            )
        )
    if alpha_report.get("payoff_degradation"):
        items.append(
            make_review_item(
                title="Payoff degradation",
                category="baseline",
                severity="warning",
                recommended_action="tighten",
            )
        )

    if missed.get("human_review_suggested") or int(missed.get("too_conservative_count") or 0) > 2:
        items.append(
            make_review_item(
                title="Missed opportunity pattern",
                category="missed_opportunity",
                severity="warning",
                summary=str(missed.get("dominant_classification") or "review pattern"),
                recommended_action="human_review",
                requires_human_review=True,
            )
        )

    if governor_qa.get("human_review_suggested") or governor_qa.get("qa_adjustment"):
        items.append(
            make_review_item(
                title="Governor QA review",
                category="governor",
                severity="warning",
                summary=str(governor_qa.get("qa_adjustment") or governor_qa.get("qa_reason_codes")),
                recommended_action="human_review",
                requires_human_review=bool(governor_qa.get("human_review_suggested")),
            )
        )
    if governor_qa.get("can_loosen_automatically"):
        items.append(
            make_review_item(
                title="Blocked auto-loosen path",
                category="governor",
                severity="critical",
                summary="Auto-loosen is disabled — tighten-only governor",
                recommended_action="monitor",
                blocked_action="auto_loosen",
            )
        )

    ne_label = str(no_edge.get("quality_label") or "")
    if ne_label in ("weak", "harmful"):
        items.append(
            make_review_item(
                title="No-edge quality concern",
                category="no_edge",
                severity="warning",
                summary=ne_label,
                recommended_action="tighten",
            )
        )

    for rule in (rule_summary.get("suggest_retire") or [])[:2]:
        items.append(
            make_review_item(
                title=f"Rule {rule.get('name') or rule.get('rule_id')} noisy",
                category="rule",
                severity="warning",
                summary=str(rule.get("notes") or "suggest retire"),
                recommended_action="retire",
                allowed_action="retire",
            )
        )

    return sort_review_items(items)


def _resolve_status(
    *,
    n: int,
    min_sample: int,
    alpha_status: str,
    overfit: Dict[str, Any],
    cost_adj_positive: bool,
    human_count: int,
    improved: List[str],
    deteriorated: List[str],
) -> str:
    if human_count > 0:
        return "needs_human_review"
    if n < MIN_SAMPLES_LEARNING:
        return "learning"
    if n < min_sample or not _overfit_pass(overfit):
        return "insufficient_evidence"
    if deteriorated and improved:
        return "mixed"
    if deteriorated or alpha_status in ("deteriorating", "noisy"):
        return "deteriorating"
    if improved or alpha_status == "improving":
        return "improving"
    if alpha_status == "stable" and cost_adj_positive:
        return "stable"
    return "insufficient_evidence"


def _next_actions(
    *,
    status: str,
    items: List[ReviewItem],
    rule_actions: List[Dict[str, Any]],
) -> List[str]:
    actions: List[str] = []
    if status == "learning":
        actions.append("Continue collecting forward outcomes — review remains in learning mode")
    elif status == "needs_human_review":
        actions.append("Operator human review queue has open items — no automatic threshold changes")
    elif status == "deteriorating":
        actions.append("Governor tighten-only path — review deteriorating signals before any deploy discussion")
    elif status == "improving":
        actions.append("Monitor improving cohort — still no deploy authority from Alpha Review")
    elif status == "stable":
        actions.append("Stable evidence window — continue monitoring; authority effect remains none")
    else:
        actions.append("Insufficient evidence — collect more samples and re-run review")

    for item in items[:3]:
        if item.recommended_action == "collect_more_samples":
            actions.append("Collect more forward outcome samples before lift or success labels")
            break
    for ra in rule_actions[:2]:
        sug = ra.get("agent_suggestion") or ra.get("suggested_action")
        if sug:
            actions.append(f"Rule loop suggestion: {sug} (advisory only)")
    actions.append("authority_effect=none — Alpha Review cannot open trading authority")
    return actions[:6]


def build_alpha_review(
    *,
    alpha_snapshots: Optional[Sequence[Dict[str, Any]]] = None,
    alpha_quality_report: Optional[Dict[str, Any]] = None,
    baselines: Optional[Dict[str, Any]] = None,
    overfit: Optional[Dict[str, Any]] = None,
    missed_opportunity: Optional[Dict[str, Any]] = None,
    no_edge_tracking: Optional[Dict[str, Any]] = None,
    attribution: Optional[Dict[str, Any]] = None,
    stage_transitions: Optional[Sequence[Dict[str, Any]]] = None,
    rule_summary: Optional[Dict[str, Any]] = None,
    governor_qa: Optional[Dict[str, Any]] = None,
    window_days: int = 20,
    min_sample: int = MIN_SAMPLES_LIFT,
    persist: bool = False,
    supersede_prior: bool = False,
    store: Optional[AlphaReviewStore] = None,
    human_queue: Optional[HumanReviewQueue] = None,
) -> Dict[str, Any]:
    """Build AlphaReviewReport from Alpha QA inputs — advisory only."""
    snaps = list(alpha_snapshots or [])
    aq = dict(alpha_quality_report or (snaps[-1] if snaps else {}))
    bl = dict(baselines or aq.get("baseline_comparison") or {})
    of = dict(overfit or {"overfit_risk": aq.get("overfit_risk", "medium")})
    missed = dict(missed_opportunity or aq.get("missed_opportunity_review") or {})
    no_edge = dict(no_edge_tracking or {})
    gov = dict(governor_qa or aq.get("governor_qa") or {})
    rules = dict(rule_summary or {})

    n = int(aq.get("sample_size") or 0)
    cost_adj = _parse_cost_adj_expectancy(aq.get("cost_adj_expectancy_display"))
    cost_adj_positive = cost_adj is not None and cost_adj > 0

    improved, deteriorated = _delta_snapshots(snaps) if snaps else ([], [])
    if aq.get("status") == "improving" and not improved:
        improved.append("alpha QA status improving")
    if aq.get("status") in ("deteriorating", "noisy") and not deteriorated:
        deteriorated.append(f"alpha QA status {aq.get('status')}")

    items = _build_review_items(
        n=n,
        min_sample=min_sample,
        alpha_report=aq,
        overfit=of,
        baselines=bl,
        missed=missed,
        no_edge=no_edge,
        governor_qa=gov,
        rule_summary=rules,
    )
    item_summary = review_items_summary(items)
    human_items = item_summary["human_review_items"]

    rule_actions = apply_alpha_review_to_rules(
        rule_summary=rules,
        review_status=aq.get("status", "learning"),
        sample_size=n,
        min_sample=min_sample,
        overfit_pass=_overfit_pass(of),
        cost_adj_positive=cost_adj_positive,
    )

    evidence_level = _evidence_level(n=n, overfit=of, min_sample=min_sample)
    status = _resolve_status(
        n=n,
        min_sample=min_sample,
        alpha_status=str(aq.get("status") or "learning"),
        overfit=of,
        cost_adj_positive=cost_adj_positive,
        human_count=len(human_items),
        improved=improved,
        deteriorated=deteriorated,
    )

    families = _signal_family_review(attribution, alpha_report=aq, overfit=of)
    stage_conv = _stage_conversion(stage_transitions, alpha_report=aq)
    next_actions = _next_actions(status=status, items=items, rule_actions=rule_actions)

    report = {
        "title": "Alpha Review",
        "report_id": make_report_id(),
        "window_days": window_days,
        "status": status,
        "status_label": status.replace("_", " "),
        "evidence_level": evidence_level,
        "sample_size": n,
        "what_improved": improved,
        "what_deteriorated": deteriorated,
        "signal_families": families,
        "stage_conversion": stage_conv,
        "rule_actions": rule_actions,
        "human_review_items": human_items,
        "human_review_count": len(human_items),
        "review_items": item_summary["items"],
        "governor_review": {
            "qa_adjustment": gov.get("qa_adjustment"),
            "qa_reason_codes": gov.get("qa_reason_codes", []),
            "human_review_suggested": gov.get("human_review_suggested", False),
            "can_loosen_automatically": False,
            "authority_effect": "none",
        },
        "next_actions": next_actions,
        "alpha_snapshot_id": aq.get("snapshot_id", ""),
        "learning_mode": n < MIN_SAMPLES_LEARNING,
        "overfit_pass": _overfit_pass(of),
        "cost_adj_positive": cost_adj_positive,
        "collapsed": True,
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
        "labels": {
            "no_deploy": True,
            "no_auto_loosen": True,
            "no_fake_precision": True,
        },
    }

    if persist:
        st = store or get_alpha_review_store()
        prior = st.latest_report()
        ar = AlphaReviewReport(
            report_id=report["report_id"],
            window_days=window_days,
            status=status,
            evidence_level=evidence_level,
            sample_size=n,
            what_improved=improved,
            what_deteriorated=deteriorated,
            signal_families=families,
            stage_conversion=stage_conv,
            rule_actions=rule_actions,
            human_review_items=human_items,
            review_items=item_summary["items"],
            governor_review=report["governor_review"],
            next_actions=next_actions,
            alpha_snapshot_id=str(aq.get("snapshot_id") or ""),
        )
        if supersede_prior and prior:
            st.supersede_report(ar, prior_report_id=str(prior.get("report_id") or ""))
        else:
            st.append_report(ar)
        hq = human_queue or get_human_review_queue()
        for task in tasks_from_review_items(human_items, report_id=report["report_id"]):
            hq.enqueue(task)

    return report


def alpha_review_summary_for_dashboard(report: Dict[str, Any]) -> Dict[str, Any]:
    """Compact summary for decision_quality payload."""
    return {
        "status": report.get("status", "learning"),
        "status_label": report.get("status_label", "learning"),
        "evidence_level": report.get("evidence_level", "learning"),
        "human_review_count": int(report.get("human_review_count") or 0),
        "what_improved": (report.get("what_improved") or [])[:3],
        "what_deteriorated": (report.get("what_deteriorated") or [])[:3],
        "top_items": (report.get("review_items") or [])[:3],
        "governor_review": report.get("governor_review") or {},
        "next_actions": (report.get("next_actions") or [])[:4],
        "collapsed": True,
        "authority_effect": "none",
        "may_authorize_deploy": False,
    }
