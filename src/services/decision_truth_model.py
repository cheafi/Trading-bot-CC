"""
Institutional decision truth model — separates macro / opportunity / execution.

Keeps dashboard and playbook aligned: tradeability follows council-validated
scores, not raw scanner thresholds alone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.utils.numeric_parse import parse_ratio

TRADE_RR_THRESHOLD = 2.5

_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT"})
_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE"})
_SCALE_ACTIONS = frozenset({"SCALE", "ADD", "SCALE_IN"})

_AVOID_GROUP_ORDER = (
    "weak_thesis",
    "laggard",
    "low_data_quality",
    "poor_rr",
    "regime_conflict",
    "execution_weak",
    "other",
)

DASHBOARD_KPI_PIPELINE_LABELS: Tuple[str, str, str] = (
    "scanned",
    "watch-qualified",
    "deploy-qualified",
)

FLOW_OVERLAY_DEGRADED_HEADLINES: Dict[str, str] = {
    "synthetic": "No live flow overlay",
    "offline": "Flow overlay unavailable",
    "uncalibrated": "Flow overlay unavailable",
}

FLOW_OVERLAY_DEGRADED_SHORT: Dict[str, str] = {
    "synthetic": "Fallback only",
    "offline": "No live overlay",
    "uncalibrated": "Unavailable",
}


PLAYBOOK_FUNNEL_LAYER_DEFINITIONS: Dict[str, str] = {
    "scanned": "Universe evaluated by the scan pipeline.",
    "watch_qualified": "Met the monitor bar — near-miss pool; not deploy-ready.",
    "deploy_qualified": "Execution-ready — passed timing, R:R, and handoff gates.",
    "near_miss": "Upgrade layer — closest monitor upgrade; still not deploy-ready.",
    "monitor_ranking": "Relative scan priority on WAIT days — rank ≠ deploy permission.",
}


def playbook_funnel_layer_note() -> str:
    """One-line helper for Playbook funnel strip and section headers."""
    return (
        "Scanned = universe evaluated · Watch-qualified = monitor / near-miss pool · "
        "Deploy-qualified = execution-ready · Near-miss = upgrade layer (not deploy) · "
        "Monitor ranking = priority only, not permission."
    )


def playbook_scan_ranked_count(
    funnel: Optional[Dict[str, Any]],
    *,
    opportunity_count: int = 0,
) -> int:
    """Audit-layer names on the board when none are watch-qualified."""
    f = funnel or {}
    if int(f.get("watch_qualified_setups") or 0) > 0:
        return 0
    for key in ("triggered_setups", "high_score_setups", "raw_signal_candidates"):
        n = int(f.get(key) or 0)
        if n > 0:
            return n
    if opportunity_count > 0:
        return opportunity_count
    return int(f.get("universe_scanned") or f.get("universe") or 0)


def format_board_quality_detail(
    watch_qualified: int,
    *,
    scan_ranked: int = 0,
    scanner_degraded: bool = False,
) -> str:
    """Unlock board condition — never label scan-only names as watch-qualified."""
    wq = max(0, int(watch_qualified or 0))
    sr = max(0, int(scan_ranked or 0))
    suffix = " · data STALE" if scanner_degraded else ""
    if wq >= 1:
        return f"{wq} watch-qualified{suffix}"
    if sr >= 1:
        return f"{sr} scan-ranked (not watch-qualified){suffix}"
    return f"0 watch-qualified{suffix}"


def rejection_clusters_reconcile_note(
    rejection_clusters: Optional[List[Dict[str, Any]]],
    avoid_grouped: Optional[Dict[str, Any]],
) -> str:
    """Short line when cluster totals and filtered-name totals diverge."""
    clusters = rejection_clusters or []
    if not clusters:
        return ""
    cluster_sum = sum(int(c.get("count") or 0) for c in clusters)
    filtered = int((avoid_grouped or {}).get("total") or 0)
    if filtered <= 0 or cluster_sum == filtered:
        return ""
    return (
        f"Cluster counts ({cluster_sum}) group by blocker theme; "
        f"{filtered} names in the filtered list — themes can overlap."
    )


def _pr(cr: Any) -> Any:
    return cr.pipeline


def _action(cr: Any) -> str:
    try:
        return (cr.pipeline.decision.action or "WATCH").upper()
    except Exception:
        return "WATCH"


def _score(cr: Any) -> float:
    try:
        return float(cr.pipeline.fit.final_score)
    except Exception:
        return 0.0


def _conf(cr: Any) -> float:
    try:
        return float(cr.pipeline.confidence.final)
    except Exception:
        return 0.0


def is_below_trade_rr_threshold(rr_value: Any) -> bool:
    """True when R:R is present but below full-size TRADE gate (2.5)."""
    rr = parse_ratio(rr_value, 0.0) or 0.0
    return 0 < rr < TRADE_RR_THRESHOLD


def _rr(cr: Any) -> float:
    try:
        sig = cr.pipeline.signal
        raw = sig.get("risk_reward") or cr.pipeline.decision.risk_reward or 0
        return parse_ratio(raw, 0.0) or 0.0
    except Exception:
        return 0.0


def _pipeline_invalidation(pr: Any) -> str:
    """Invalidation text lives on explanation/signal, not sector Decision."""
    inv = getattr(pr.decision, "invalidation", None)
    if inv:
        return str(inv)
    expl = getattr(pr, "explanation", None)
    if expl and getattr(expl, "invalidation", None):
        return str(expl.invalidation)
    sig = pr.signal if hasattr(pr, "signal") else {}
    return str(sig.get("invalidation") or "")


def _pipeline_risk_reward(pr: Any) -> float:
    """R:R on sector Decision is risk_reward; legacy rows may use risk_reward_ratio."""
    sig = pr.signal if hasattr(pr, "signal") else {}
    raw = (
        sig.get("risk_reward")
        or getattr(pr.decision, "risk_reward", None)
        or getattr(pr.decision, "risk_reward_ratio", None)
        or 0
    )
    return parse_ratio(raw, 0.0) or 0.0


def _has_levels(cr: Any) -> bool:
    try:
        sig = cr.pipeline.signal
        return all(
            float(sig.get(k) or 0) > 0
            for k in ("entry_price", "stop_price", "target_price")
        )
    except Exception:
        return False


def is_execution_ready(cr: Any) -> bool:
    """Fully deployable: TRADE-grade with levels, R:R, and confidence."""
    act = _action(cr)
    if act not in _TRADE_ACTIONS:
        return False
    if _score(cr) < 7.5 or _conf(cr) < 0.60:
        return False
    if _rr(cr) > 0 and _rr(cr) < 2.0:
        return False
    return _has_levels(cr)


def is_pilot_eligible(cr: Any) -> bool:
    """Real partial edge — not a default for mediocre setups."""
    act = _action(cr)
    if act in _AVOID_ACTIONS:
        return False
    score = _score(cr)
    conf = _conf(cr)
    if score < 6.5 or conf < 0.50:
        return False
    try:
        pr = cr.pipeline
        timing = float(pr.confidence.timing)
        thesis = float(pr.confidence.thesis)
        execution = float(pr.confidence.execution)
        data = float(pr.confidence.data)
    except Exception:
        return False
    if thesis < 0.50 and timing < 0.45:
        return False
    if execution < 0.35 or data < 0.35:
        return False
    rr = _rr(cr)
    if rr > 0 and rr < 1.8:
        return False
    sig = pr.signal
    stop = float(sig.get("stop_price") or 0)
    if stop <= 0:
        return False
    return True


def build_pilot_explanations(cr: Any) -> Dict[str, str]:
    """Required fields when labeling PILOT."""
    pr = cr.pipeline
    gaps: List[str] = []
    if float(pr.confidence.timing) < 0.55:
        gaps.append("timing not fully confirmed")
    if float(pr.confidence.thesis) < 0.70:
        gaps.append("thesis incomplete vs full TRADE bar")
    if _score(pr) < 8.0:
        gaps.append(f"fit score {_score(pr):.1f} below A-grade (8.0+)")
    rr = _rr(cr)
    if rr > 0 and rr < 2.5:
        gaps.append(f"R:R {rr:.1f} below full-size 2.5 gate")
    if not _has_levels(cr):
        gaps.append("entry/stop/target incomplete")
    why = (
        "; ".join(gaps)
        if gaps
        else "Partial edge with defined stop — size at half risk only"
    )
    upgrade_parts = []
    if float(pr.confidence.timing) < 0.55:
        upgrade_parts.append("timing ≥55% with volume at trigger")
    if _score(pr) < 8.0:
        upgrade_parts.append("board fit score ≥8.0")
    if rr > 0 and rr < 2.5:
        upgrade_parts.append("R:R ≥2.5 with clean fill")
    upgrade = (
        " · ".join(upgrade_parts)
        if upgrade_parts
        else "Reclaim entry on volume; thesis+timing both ≥65%"
    )
    downgrade_parts = []
    if float(pr.confidence.thesis) < 0.45:
        downgrade_parts.append("thesis breaks → WATCH")
    if float(pr.confidence.data) < 0.35:
        downgrade_parts.append("data quality fails → AVOID")
    if _rr(cr) > 0 and _rr(cr) < 1.5:
        downgrade_parts.append("R:R collapses → AVOID")
    inv = _pipeline_invalidation(pr)
    if inv:
        downgrade_parts.append(f"invalidation: {inv[:80]}")
    downgrade = (
        " · ".join(downgrade_parts)
        if downgrade_parts
        else "Stop hit or regime gate closes → exit pilot"
    )
    return {
        "why_pilot": why,
        "upgrade_to_trade": upgrade,
        "downgrade_to_watch_avoid": downgrade,
    }


def _brief_monitor_cap(cr: Any, refined: str) -> str:
    """Brief/coverage-pad rows seed the monitor pool — deploy requires council validation."""
    try:
        src = str(cr.pipeline.signal.get("source") or "").lower()
    except Exception:
        return refined
    if src not in ("brief", "coverage_pad"):
        return refined
    if refined in _AVOID_ACTIONS or _score(cr) < 5.0:
        return refined
    if refined in _TRADE_ACTIONS | _PILOT_ACTIONS:
        return "WATCH"
    return refined


def refine_action(cr: Any) -> str:
    """
    Strict action taxonomy — downgrade overused PILOT to WATCH.
    """
    act = _action(cr)
    if act in _AVOID_ACTIONS:
        return _brief_monitor_cap(cr, act if act != "NO_TRADE" else "AVOID")
    if is_execution_ready(cr):
        return _brief_monitor_cap(cr, "TRADE")
    if act in _PILOT_ACTIONS or act == "PILOT":
        if is_pilot_eligible(cr):
            return _brief_monitor_cap(cr, "PILOT")
        return _brief_monitor_cap(cr, "WATCH")
    if act in _TRADE_ACTIONS:
        if is_pilot_eligible(cr):
            return _brief_monitor_cap(cr, "PILOT")
        if _score(cr) >= 5.0:
            return _brief_monitor_cap(cr, "WATCH")
        return _brief_monitor_cap(cr, "AVOID")
    if act in _WATCH_ACTIONS:
        if _score(cr) < 3.5:
            return _brief_monitor_cap(cr, "AVOID")
        return _brief_monitor_cap(cr, "WATCH")
    if _score(cr) < 3.5:
        return _brief_monitor_cap(cr, "AVOID")
    return _brief_monitor_cap(cr, "WATCH")


def build_honest_funnel(
    *,
    universe: int,
    scanned: List[Dict[str, Any]],
    council_results: List[Any],
) -> Dict[str, Any]:
    """Explicit buckets — raw scanner vs council-validated."""
    raw_triggered = len(scanned)
    raw_high_score = len([s for s in scanned if float(s.get("score") or 0) >= 6.0])
    raw_scanner_8 = len([s for s in scanned if float(s.get("score") or 0) >= 8.0])

    council_scores = [_score(cr) for cr in council_results]
    high_score_setups = len([s for s in council_scores if s >= 6.0])
    triggered_setups = len(council_results)
    execution_ready = sum(1 for cr in council_results if is_execution_ready(cr))
    pilot_ready = sum(
        1
        for cr in council_results
        if refine_action(cr) == "PILOT" and is_pilot_eligible(cr)
    )
    trade_actions = sum(
        1 for cr in council_results if refine_action(cr) in _TRADE_ACTIONS
    )
    watch_count = sum(
        1 for cr in council_results if refine_action(cr) in _WATCH_ACTIONS
    )
    avoid_count = sum(
        1 for cr in council_results if refine_action(cr) in _AVOID_ACTIONS
    )
    near_miss = sum(
        1
        for cr in council_results
        if refine_action(cr) == "WATCH" and _score(cr) >= 6.0
    )

    watch_qualified = max(near_miss, watch_count)

    return normalize_playbook_funnel(
        {
            "universe_scanned": universe,
            "raw_signal_candidates": raw_triggered,
            "raw_scanner_above_8": raw_scanner_8,
            "high_score_setups": high_score_setups,
            "triggered_setups": triggered_setups,
            "execution_ready_setups": execution_ready,
            "pilot_eligible_setups": pilot_ready,
            "trade_grade_setups": trade_actions,
            "near_miss_setups": near_miss,
            "avoid_filtered_setups": avoid_count,
            "watch_setups": watch_count,
            "watch_qualified_setups": watch_qualified,
            "deploy_qualified_setups": execution_ready,
            # Legacy keys for backward compatibility
            "universe": universe,
            "signals_triggered": raw_triggered,
            "score_above_6": raw_high_score,
            "actionable_above_7": len([s for s in council_scores if s >= 7.0]),
            "high_conviction_above_8": len([s for s in council_scores if s >= 8.0]),
            "note": playbook_funnel_layer_note(),
        }
    )


def normalize_playbook_funnel(
    funnel: Optional[Dict[str, Any]],
    *,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Canonical three-layer funnel counts for Playbook + unlock_deploy."""
    f = dict(funnel or {})
    scanned = int(f.get("universe_scanned") or f.get("universe") or 0)
    deploy = int(
        f.get("deploy_qualified_setups") or f.get("execution_ready_setups") or 0
    )
    watch = f.get("watch_qualified_setups")
    if watch is None:
        watch = f.get("near_miss_setups")
    if watch is None:
        watch = f.get("watch_setups")
    if watch is None and near_miss is not None:
        watch = len(near_miss)
    watch = int(watch or 0)
    return {
        **f,
        "universe_scanned": scanned,
        "watch_qualified_setups": watch,
        "deploy_qualified_setups": deploy,
        "execution_ready_setups": deploy,
    }


def compute_macro_regime(
    *,
    should_trade: bool,
    trend_label: str,
    tradeability: str,
    vix: float,
    breadth: float,
) -> Tuple[str, str]:
    """A. Macro Regime: Supportive / Neutral / Hostile."""
    if not should_trade or tradeability == "NO_TRADE":
        return "Hostile", "Regime gate closed — capital preservation"
    if vix > 28 or breadth < 35:
        return "Hostile", f"VIX {vix:.0f} or breadth {breadth:.0f}% — risk-off backdrop"
    trend = (trend_label or "").upper()
    if trend in ("UPTREND", "BULL", "RISK_ON") and tradeability in (
        "TRADE",
        "STRONG_TRADE",
        "SELECTIVE",
    ):
        return "Supportive", f"{trend} with deployable tradeability"
    if trend in ("DOWNTREND", "RISK_OFF", "BEAR"):
        return "Hostile", f"{trend} — avoid aggressive new risk"
    return "Neutral", "Mixed macro — selective sizing only"


def compute_opportunity_quality(
    council_results: List[Any],
    *,
    execution_ready: int,
    pilot_ready: int,
) -> Tuple[str, str]:
    """B. Opportunity Quality: Strong / Mixed / Weak."""
    if execution_ready >= 2:
        return "Strong", f"{execution_ready} execution-ready setup(s) on the board"
    if execution_ready == 1 or pilot_ready >= 1:
        return "Mixed", "Limited A-grade names — pilots or singles only"
    high_watch = sum(
        1
        for cr in council_results
        if _score(cr) >= 6.5 and refine_action(cr) == "WATCH"
    )
    if high_watch >= 2:
        return "Mixed", f"{high_watch} near-miss names forming — not deploy-grade"
    if high_watch >= 1:
        return "Mixed", "One near-miss on board — watch triggers"
    if not council_results:
        return "Weak", "No deploy-qualified setups in pipeline"
    return "Weak", "No names pass full thesis+timing+R:R gates"


def compute_execution_readiness_label(
    *,
    execution_ready: int,
    pilot_ready: int,
    macro: str,
    opportunity: str,
    ibkr_connected: bool = False,
    bracket_ready: bool = False,
) -> Tuple[str, str]:
    """C. Execution Readiness: Trade Now / Pilot Only / Watch Only / No Trade."""
    if macro == "Hostile" or opportunity == "Weak":
        if execution_ready > 0:
            return (
                "Watch Only",
                "Macro hostile or setups weak — do not size up despite isolated signals",
            )
        return "No Trade", "No deploy — regime or setup quality blocks risk"
    if execution_ready >= 1 and bracket_ready and ibkr_connected:
        return (
            "Trade Now",
            f"{execution_ready} name(s) pass full gates · IBKR handoff ready",
        )
    if execution_ready >= 1:
        return (
            "Trade Now",
            f"{execution_ready} name(s) pass gates — confirm bracket/IBKR before send",
        )
    if pilot_ready >= 1:
        return (
            "Pilot Only",
            f"{pilot_ready} pilot-eligible — half size only, stop required",
        )
    if opportunity == "Mixed":
        return "Watch Only", "Setups forming — wait for trigger confirmation"
    return "No Trade", "Nothing meets execution bar today"


def compute_honest_tradeability(
    *,
    should_trade: bool,
    execution_ready: int,
    pilot_ready: int,
    council_high_8: int,
    macro: str,
    opportunity: str,
) -> str:
    """
    Tradeability aligned with board quality — not raw scanner ≥8 count.
    """
    if not should_trade:
        return "NO_TRADE"
    if execution_ready >= 3 and opportunity == "Strong":
        return "STRONG_TRADE"
    if execution_ready >= 1:
        return "TRADE"
    if pilot_ready >= 1 or opportunity == "Mixed":
        return "SELECTIVE"
    if council_high_8 >= 2 and opportunity != "Weak":
        return "SELECTIVE"
    return "WAIT"


def build_three_layer_model(
    *,
    should_trade: bool,
    trend_label: str,
    tradeability: str,
    vix: float,
    breadth: float,
    council_results: List[Any],
    execution_ready: int,
    pilot_ready: int,
    ibkr_connected: bool = False,
    bracket_ready: bool = False,
) -> Dict[str, Any]:
    macro, macro_detail = compute_macro_regime(
        should_trade=should_trade,
        trend_label=trend_label,
        tradeability=tradeability,
        vix=vix,
        breadth=breadth,
    )
    opportunity, opp_detail = compute_opportunity_quality(
        council_results,
        execution_ready=execution_ready,
        pilot_ready=pilot_ready,
    )
    exec_label, exec_detail = compute_execution_readiness_label(
        execution_ready=execution_ready,
        pilot_ready=pilot_ready,
        macro=macro,
        opportunity=opportunity,
        ibkr_connected=ibkr_connected,
        bracket_ready=bracket_ready,
    )
    honest_tradeability = compute_honest_tradeability(
        should_trade=should_trade,
        execution_ready=execution_ready,
        pilot_ready=pilot_ready,
        council_high_8=len([cr for cr in council_results if _score(cr) >= 8.0]),
        macro=macro,
        opportunity=opportunity,
    )
    headline = f"Macro {macro} · Opportunities {opportunity} · Execution: {exec_label}"
    if macro == "Supportive" and opportunity == "Weak":
        guidance = (
            "Backdrop is supportive but today's board is weak — do not infer "
            "full-size deploy from regime alone."
        )
    elif honest_tradeability == "STRONG_TRADE" and execution_ready < 2:
        guidance = "Downgraded from STRONG — fewer than 2 execution-ready names."
    else:
        guidance = exec_detail

    return {
        "macro_regime": macro,
        "macro_detail": macro_detail,
        "opportunity_quality": opportunity,
        "opportunity_detail": opp_detail,
        "execution_readiness": exec_label,
        "execution_detail": exec_detail,
        "honest_tradeability": honest_tradeability,
        "headline": headline,
        "guidance": guidance,
    }


def classify_avoid_reason(cr: Any) -> str:
    try:
        pr = cr.pipeline
        if float(pr.confidence.data) < 0.35:
            return "low_data_quality"
        if float(pr.confidence.execution) < 0.35:
            return "execution_weak"
        rr = _rr(cr)
        if 0 < rr < 2.0:
            return "poor_rr"
        if (pr.sector.leader_status.value or "").upper() == "LAGGARD":
            return "laggard"
        if float(pr.confidence.thesis) < 0.40:
            return "weak_thesis"
        if _action(cr) in ("NO_TRADE", "AVOID"):
            return "regime_conflict"
    except Exception:
        pass
    return "other"


def build_avoid_grouped(
    council_results: List[Any],
    *,
    limit_per_group: int = 8,
) -> Dict[str, Any]:
    """Compress AVOID clutter — grouped summary for UI table."""
    groups: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _AVOID_GROUP_ORDER}
    for cr in council_results:
        act = refine_action(cr)
        if act not in _AVOID_ACTIONS:
            continue
        try:
            pr = cr.pipeline
            sig = pr.signal
            ticker = sig.get("ticker") or "—"
            bucket = classify_avoid_reason(cr)
            groups.setdefault(bucket, []).append(
                {
                    "ticker": ticker,
                    "score": round(_score(cr), 1),
                    "reason": (pr.decision.rationale or "")[:120],
                    "action": act,
                }
            )
        except Exception:
            continue

    summary_rows = []
    total = 0
    for key in _AVOID_GROUP_ORDER:
        items = groups.get(key) or []
        if not items:
            continue
        total += len(items)
        summary_rows.append(
            {
                "group": key,
                "label": key.replace("_", " ").title(),
                "count": len(items),
                "tickers": [i["ticker"] for i in items[:limit_per_group]],
                "sample_reason": items[0].get("reason", ""),
                "items": items[:limit_per_group],
            }
        )
    return {
        "total": total,
        "groups": summary_rows,
    }


def build_bucket_quality_summary(council_results: List[Any]) -> List[Dict[str, Any]]:
    """Per market-bucket thesis/timing pass counts."""
    buckets: Dict[str, Dict[str, int]] = {}
    for cr in council_results:
        try:
            bucket = cr.pipeline.sector.sector_bucket.value
        except Exception:
            bucket = "OTHER"
        if bucket not in buckets:
            buckets[bucket] = {
                "total": 0,
                "thesis_pass": 0,
                "timing_pass": 0,
                "execution_ready": 0,
            }
        buckets[bucket]["total"] += 1
        pr = cr.pipeline
        if float(pr.confidence.thesis) >= 0.65:
            buckets[bucket]["thesis_pass"] += 1
        if float(pr.confidence.timing) >= 0.50:
            buckets[bucket]["timing_pass"] += 1
        if is_execution_ready(cr):
            buckets[bucket]["execution_ready"] += 1

    rows = []
    for bucket, stats in sorted(buckets.items(), key=lambda x: -x[1]["total"]):
        rows.append(
            {
                "bucket": bucket.replace("_", " "),
                "thesis_line": f"{stats['thesis_pass']}/{stats['total']} pass thesis",
                "timing_line": f"{stats['timing_pass']}/{stats['total']} acceptable timing",
                "deploy_line": f"{stats['execution_ready']}/{stats['total']} execution-ready",
            }
        )
    return rows


def build_avoid_grouped_from_rows(
    rows: List[Dict[str, Any]],
    *,
    limit_per_group: int = 8,
) -> Dict[str, Any]:
    """Grouped AVOID summary from flat playbook rows (no council objects)."""
    groups: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _AVOID_GROUP_ORDER}
    for row in rows:
        act = (row.get("action") or "").upper()
        if act not in _AVOID_ACTIONS:
            continue
        bucket = "other"
        rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0
        if float(row.get("data_conf") or 1) < 0.35:
            bucket = "low_data_quality"
        elif float(row.get("exec_conf") or 1) < 0.35:
            bucket = "execution_weak"
        elif 0 < rr < 2.0:
            bucket = "poor_rr"
        elif (row.get("leader") or "").upper() == "LAGGARD":
            bucket = "laggard"
        elif float(row.get("thesis_conf") or 0) < 0.40:
            bucket = "weak_thesis"
        elif act in ("NO_TRADE", "AVOID"):
            bucket = "regime_conflict"
        groups.setdefault(bucket, []).append(
            {
                "ticker": row.get("ticker", "—"),
                "score": row.get("score"),
                "reason": (row.get("why_not") or row.get("invalidation") or "")[:120]
                if isinstance(row.get("why_not"), str)
                else str(row.get("why_not", ""))[:120],
                "action": act,
            }
        )
    summary_rows = []
    total = 0
    for key in _AVOID_GROUP_ORDER:
        items = groups.get(key) or []
        if not items:
            continue
        total += len(items)
        summary_rows.append(
            {
                "group": key,
                "label": key.replace("_", " ").title(),
                "count": len(items),
                "tickers": [i["ticker"] for i in items[:limit_per_group]],
                "sample_reason": items[0].get("reason", ""),
                "items": items[:limit_per_group],
            }
        )
    return {"total": total, "groups": summary_rows}


def build_bucket_quality_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, int]] = {}
    for row in rows:
        bucket = (row.get("sector_type") or "OTHER").replace(" ", "_")
        if bucket not in buckets:
            buckets[bucket] = {
                "total": 0,
                "thesis_pass": 0,
                "timing_pass": 0,
                "execution_ready": 0,
            }
        buckets[bucket]["total"] += 1
        if float(row.get("thesis_conf") or 0) >= 0.65:
            buckets[bucket]["thesis_pass"] += 1
        if float(row.get("timing_conf") or 0) >= 0.50:
            buckets[bucket]["timing_pass"] += 1
        if (row.get("action") or "").upper() == "TRADE":
            buckets[bucket]["execution_ready"] += 1
    return [
        {
            "bucket": k.replace("_", " "),
            "thesis_line": f"{v['thesis_pass']}/{v['total']} pass thesis",
            "timing_line": f"{v['timing_pass']}/{v['total']} acceptable timing",
            "deploy_line": f"{v['execution_ready']}/{v['total']} execution-ready",
        }
        for k, v in sorted(buckets.items(), key=lambda x: -x[1]["total"])
    ]


def _row_score(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_thesis(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("thesis_conf") or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_timing(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("timing_conf") or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_rr(row: Dict[str, Any]) -> float:
    return parse_ratio(row.get("risk_reward"), 0.0) or 0.0


def row_passes_trade_bar(row: Dict[str, Any]) -> bool:
    """Flat-row TRADE gate — aligned with dashboard decision rules copy."""
    score = _row_score(row)
    thesis = _row_thesis(row)
    timing = _row_timing(row)
    rr = _row_rr(row)
    if score < 8.0 or thesis < 0.65 or timing < 0.65:
        return False
    if rr > 0 and rr < TRADE_RR_THRESHOLD:
        return False
    act = (row.get("action") or "").upper()
    return act in _TRADE_ACTIONS and bool(row.get("execution_ready"))


def build_trade_bar_status(row: Dict[str, Any]) -> Dict[str, Any]:
    """Per-card gate checklist for explainability."""
    score = _row_score(row)
    thesis = _row_thesis(row)
    timing = _row_timing(row)
    rr = _row_rr(row)
    return {
        "score_ok": score >= 8.0,
        "thesis_ok": thesis >= 0.65,
        "timing_ok": timing >= 0.65,
        "rr_ok": rr <= 0 or rr >= TRADE_RR_THRESHOLD,
        "execution_ready": bool(row.get("execution_ready")),
        "passes_trade_bar": row_passes_trade_bar(row),
    }


def sector_tailwind_for_row(
    row: Dict[str, Any],
    *,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    sector_laggards: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str]:
    """
    aligned | misaligned | neutral — uses leader status + today's sector movers.
    """
    bucket = (row.get("sector_type") or row.get("sector_bucket") or "").upper()
    leader = (row.get("leader") or "").upper()
    if leader == "LAGGARD":
        return "misaligned", "Name is a sector laggard — penalized in rank"
    leaders = sector_leaders or []
    laggards = sector_laggards or []
    for sec in leaders:
        name = (sec.get("name") or sec.get("symbol") or "").upper()
        if not name:
            continue
        if name in bucket or bucket.replace("_", " ") in name or name[:3] in bucket:
            return "aligned", f"Aligned with today's leader ({sec.get('name') or name})"
    for sec in laggards:
        name = (sec.get("name") or sec.get("symbol") or "").upper()
        if name and (name in bucket or bucket.replace("_", " ") in name):
            return (
                "misaligned",
                f"Sector bucket lagging today ({sec.get('name') or name})",
            )
    return "neutral", "Sector mixed vs today's leadership"


def sector_rank_adjustment(
    row: Dict[str, Any],
    *,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    sector_laggards: Optional[List[Dict[str, Any]]] = None,
) -> float:
    align, _ = sector_tailwind_for_row(
        row, sector_leaders=sector_leaders, sector_laggards=sector_laggards
    )
    if (row.get("leader") or "").upper() == "LAGGARD":
        return -0.6
    if align == "aligned":
        return 0.35
    if align == "misaligned":
        return -0.35
    return 0.0


def build_rank_explain(
    row: Dict[str, Any],
    *,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    sector_laggards: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """Compact bullets for 'Why ranked here'."""
    lines: List[str] = []
    bar = row.get("trade_bar") or build_trade_bar_status(row)
    thesis = _row_thesis(row)
    timing = _row_timing(row)
    exec_c = float(row.get("exec_conf") or 0)
    data_c = float(row.get("data_conf") or 0)
    if bar.get("passes_trade_bar"):
        lines.append("Passes full TRADE bar (score, thesis, timing, R:R)")
    else:
        if thesis >= timing and thesis >= 0.55:
            lines.append(f"Best thesis ({thesis * 100:.0f}%)")
        elif timing >= 0.5:
            lines.append(f"Best timing ({timing * 100:.0f}%)")
        elif exec_c >= 0.5:
            lines.append(f"Execution quality ({exec_c * 100:.0f}%)")
        else:
            lines.append(f"Fit score {_row_score(row):.1f} — below TRADE bar")
    align, align_detail = sector_tailwind_for_row(
        row, sector_leaders=sector_leaders, sector_laggards=sector_laggards
    )
    if align == "aligned":
        lines.append(align_detail)
    elif align == "misaligned":
        lines.append(align_detail)
    rr = _row_rr(row)
    if rr > 0 and rr < TRADE_RR_THRESHOLD:
        lines.append(f"R:R {rr:.1f} below {TRADE_RR_THRESHOLD} full-size gate")
    if data_c < 0.35:
        lines.append("Weak data quality — rank penalty")
    if (row.get("leader") or "").upper() == "LAGGARD":
        lines.append("Laggard status — rank penalty")
    return lines[:4]


def build_runner_up_comparison(
    current: Dict[str, Any],
    runner: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Honest peer comparison — uses validated fit score, not final confidence.
    Returns None when runner is not meaningfully different.
    """
    cur_ticker = current.get("ticker")
    run_ticker = runner.get("ticker")
    if not cur_ticker or not run_ticker or cur_ticker == run_ticker:
        return None
    cur_score = _row_score(current)
    run_score = _row_score(runner)
    if abs(cur_score - run_score) < 0.05:
        return None
    parts: List[str] = []
    if cur_score > run_score:
        parts.append(f"Higher validated score ({cur_score:.1f} vs {run_score:.1f})")
    else:
        parts.append(
            f"Ranked above on action tier despite lower score "
            f"({cur_score:.1f} vs {run_score:.1f})"
        )
    cur_thesis = _row_thesis(current)
    run_thesis = _row_thesis(runner)
    if abs(cur_thesis - run_thesis) >= 0.08:
        better = "thesis" if cur_thesis > run_thesis else "runner thesis"
        parts.append(
            f"Stronger {better} ({max(cur_thesis, run_thesis) * 100:.0f}% vs "
            f"{min(cur_thesis, run_thesis) * 100:.0f}%)"
        )
    cur_rr = _row_rr(current)
    run_rr = _row_rr(runner)
    if cur_rr > 0 and run_rr > 0 and abs(cur_rr - run_rr) >= 0.3:
        parts.append(f"R:R {cur_rr:.1f} vs {run_rr:.1f}")
    cur_bucket = (current.get("sector_type") or "").upper()
    run_bucket = (runner.get("sector_type") or "").upper()
    if cur_bucket and run_bucket and cur_bucket != run_bucket:
        parts.append(
            f"Sector fit: {cur_bucket.replace('_', ' ')} vs {run_bucket.replace('_', ' ')}"
        )
    return {
        "ticker": run_ticker,
        "score": round(run_score, 1),
        "fit_score": round(run_score, 1),
        "reason": " · ".join(parts)
        if parts
        else f"{cur_ticker} ranked above {run_ticker}",
    }


# ── Decision authority (page-level gates vs card labels) ─────────────────

_AUTHORITY_TRADE_ACTIONS = frozenset(
    {"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"}
)
_AUTHORITY_PILOT_ACTIONS = frozenset({"PILOT"})
_AUTHORITY_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "WATCH ONLY"})
_AUTHORITY_AVOID_ACTIONS = frozenset(
    {"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE", "BLOCKED"}
)

_ACTION_AUTHORITY_RANK: Dict[str, int] = {
    "TRADE": 50,
    "BUY": 50,
    "BUY_ON_DIP": 50,
    "STRONG_TRADE": 50,
    "TRADE_NOW": 50,
    "PILOT": 40,
    "WATCH": 30,
    "WAIT": 30,
    "WATCH_TRIGGER": 30,
    "WATCH ONLY": 28,
    "FALLBACK WATCH": 26,
    "FALLBACK CANDIDATE": 26,
    "RESEARCH ONLY": 22,
    "REFERENCE ONLY": 21,
    "INCOMPLETE": 20,
    "NOT EXECUTION-GRADE": 18,
    "BLOCKED": 10,
    "AVOID": 10,
    "NO_TRADE": 10,
    "PASS": 10,
    "REDUCE": 10,
    "EXIT": 10,
    "NONE": 0,
}

_CEILING_RANK = {
    "DEPLOY": 50,
    "WATCH": 30,
    "RESEARCH": 22,
    "NONE": 0,
}


def _norm_action_label(action: Optional[str]) -> str:
    return (action or "WATCH").upper().strip()


def _action_authority_rank(action: Optional[str]) -> int:
    return _ACTION_AUTHORITY_RANK.get(_norm_action_label(action), 15)


def _row_rr_available(row: Dict[str, Any]) -> bool:
    raw = row.get("risk_reward")
    if raw is None or raw == "" or raw == "—":
        return False
    rr = parse_ratio(raw, 0.0) or 0.0
    return rr > 0


def assemble_confidence_breakdown(row: Dict[str, Any]) -> Dict[str, Any]:
    """4D confidence — null overall when all components missing/zero."""
    cb = (
        row.get("confidence_breakdown")
        if isinstance(row.get("confidence_breakdown"), dict)
        else {}
    )
    thesis = float(cb.get("thesis") or row.get("thesis_conf") or 0)
    timing = float(cb.get("timing") or row.get("timing_conf") or 0)
    execution = float(cb.get("execution") or row.get("exec_conf") or 0)
    data = float(cb.get("data") or row.get("data_conf") or 0)
    fallback_only = bool(
        row.get("confidence_fallback_only")
        or str(row.get("evidence_badge") or "").lower().find("fallback") >= 0
        or str(row.get("evidence_badge") or "").lower().find("brief") >= 0
    )
    parts = [thesis, timing, execution, data]
    present = [p for p in parts if p > 0]
    out: Dict[str, Any] = {
        "thesis": round(thesis, 2) if thesis else 0,
        "timing": round(timing, 2) if timing else 0,
        "execution": round(execution, 2) if execution else 0,
        "data": round(data, 2) if data else 0,
    }
    if not present:
        out["final"] = None
        out["unavailable"] = True
        out["fallback_only"] = fallback_only
        out["label"] = (
            "Fallback estimate — non-comparable"
            if fallback_only
            else "Unavailable — components missing"
        )
        return out
    final = round(sum(present) / len(present), 2)
    out["final"] = final
    out["unavailable"] = False
    out["fallback_only"] = fallback_only
    if fallback_only:
        out["label"] = "Fallback estimate — non-comparable"
    return out


def resolve_active_data_source(
    *,
    trust_source: str = "",
    ranked_source: str = "",
    fallback_brief: bool = False,
    stale: bool = False,
) -> str:
    """Single active board source: live | fallback_brief | stale_cache."""
    if fallback_brief:
        return "fallback_brief"
    src = (ranked_source or trust_source or "").lower()
    if (
        stale
        or "snapshot" in src
        or "stale" in src
        or "degraded" in src
        or "cache" in src
    ):
        return "stale_cache"
    if "brief" in src or "fallback" in src or "compressed" in src:
        return "fallback_brief"
    return "live"


def build_decision_authority(
    *,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    scanner_degraded: bool = False,
    scanner_loading: bool = False,
    data_stale: bool = False,
    fallback_brief: bool = False,
    broker_offline: bool = False,
    engine_off: bool = False,
    exec_blocked: bool = False,
    trust_source: str = "",
    ranked_source: str = "",
    ranked_stale: bool = False,
    council_count: Optional[int] = None,
    deploy_ideas_count: Optional[int] = None,
    live_council_count: Optional[int] = None,
    live_deploy_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Canonical decision authority for dashboard / ranked / fallback surfaces."""
    tb = (tradeability or "WAIT").upper()
    regime_wait = tb in ("WAIT", "NO_TRADE") or not should_trade

    gates = {
        "regime_wait": regime_wait,
        "engine_off": bool(engine_off),
        "data_stale": bool(data_stale or scanner_degraded),
        "broker_offline": bool(broker_offline),
        "exec_blocked": bool(exec_blocked),
        "scanner_loading": bool(scanner_loading or scanner_degraded),
        "fallback_brief": bool(fallback_brief),
    }
    gates_active = any(gates.values())

    source = resolve_active_data_source(
        trust_source=trust_source,
        ranked_source=ranked_source,
        fallback_brief=fallback_brief,
        stale=ranked_stale or data_stale,
    )

    if fallback_brief or (not should_trade and tb == "NO_TRADE"):
        authority_level = "suspended"
        effective_action_max = "NONE"
    elif gates_active or source != "live":
        authority_level = "research"
        effective_action_max = "WATCH" if source == "fallback_brief" else "RESEARCH"
    else:
        authority_level = "deploy"
        effective_action_max = "WATCH"

    if authority_level == "deploy" and not gates_active:
        effective_action_max = "DEPLOY"

    allows_trade_labels = (
        authority_level == "deploy"
        and not gates_active
        and effective_action_max == "DEPLOY"
    )

    mismatch = False
    mismatch_detail = ""
    if (
        council_count is not None
        and live_council_count is not None
        and council_count != live_council_count
    ):
        mismatch = True
        mismatch_detail = (
            f"Council count {council_count} vs live pipeline {live_council_count}"
        )
    if (
        deploy_ideas_count is not None
        and live_deploy_count is not None
        and deploy_ideas_count != live_deploy_count
    ):
        mismatch = True
        mismatch_detail = (mismatch_detail + "; " if mismatch_detail else "") + (
            f"Deploy ideas {deploy_ideas_count} vs live {live_deploy_count}"
        )

    stale_snapshot_lines: List[str] = []
    if source == "stale_cache":
        stale_snapshot_lines = [
            "Historical snapshot only",
            "Not suitable for execution decisions",
            "Refresh required for decision use",
        ]
    elif source == "fallback_brief":
        stale_snapshot_lines = [
            "Fallback board",
            "Reference plan only",
            "No deploy authority",
        ]

    degraded_copy = {
        "system_mode": "degraded" if gates_active or source != "live" else "normal",
        "decision_authority_line": (
            "Decision authority: suspended"
            if authority_level == "suspended"
            else (
                "Decision authority: research-only"
                if authority_level == "research"
                else "Decision authority: deploy (card-level gates still apply)"
            )
        ),
        "fallback_board_line": (
            "Fallback board: informational only · reference plan · no deploy authority"
            if source == "fallback_brief"
            else (" · ".join(stale_snapshot_lines) if stale_snapshot_lines else "")
        ),
        "stale_snapshot_lines": stale_snapshot_lines,
    }

    return {
        "source": source,
        "authority_level": authority_level,
        "gates": gates,
        "gates_active": gates_active,
        "effective_action_max": effective_action_max,
        "display_action_max": (
            effective_action_max if effective_action_max != "DEPLOY" else "WATCH"
        ),
        "allows_trade_labels": allows_trade_labels,
        "degraded": gates_active or source != "live",
        "degraded_copy": degraded_copy,
        "data_source_mismatch": mismatch,
        "data_source_mismatch_detail": mismatch_detail,
        "counter_source": source,
        "council_count": council_count,
        "deploy_ideas_count": deploy_ideas_count,
    }


def _authority_ceiling_rank(authority: Dict[str, Any]) -> int:
    if authority.get("allows_trade_labels"):
        return _CEILING_RANK["DEPLOY"]
    max_label = str(authority.get("effective_action_max") or "NONE").upper()
    if max_label == "NONE":
        return _CEILING_RANK["NONE"]
    if max_label == "RESEARCH":
        return _CEILING_RANK["RESEARCH"]
    return _CEILING_RANK["WATCH"]


def _downgrade_display_label(
    raw_action: str,
    authority: Dict[str, Any],
    row: Dict[str, Any],
) -> str:
    gates = authority.get("gates") or {}
    if gates.get("fallback_brief") or row.get("card_display_mode") == "reference_only":
        return "FALLBACK WATCH"
    if gates.get("exec_blocked"):
        return "BLOCKED"
    if gates.get("broker_offline") or gates.get("engine_off"):
        return "BLOCKED"
    if not _row_rr_available(row) and raw_action in _AUTHORITY_TRADE_ACTIONS:
        return "INCOMPLETE"
    if authority.get("source") == "stale_cache":
        return "REFERENCE ONLY"
    if (
        gates.get("regime_wait")
        or gates.get("data_stale")
        or gates.get("scanner_loading")
    ):
        return "WATCH ONLY"
    if authority.get("authority_level") == "suspended":
        return "NOT EXECUTION-GRADE"
    return "RESEARCH ONLY"


def _trade_label_allowed(row: Dict[str, Any], authority: Dict[str, Any]) -> bool:
    """TRADE badge requires live authority, R:R, and execution-ready."""
    if not authority.get("allows_trade_labels"):
        return False
    if authority.get("gates_active"):
        return False
    raw = _norm_action_label(row.get("raw_action") or row.get("action"))
    if raw not in _AUTHORITY_TRADE_ACTIONS:
        return False
    if not _row_rr_available(row):
        return False
    if not row.get("execution_ready"):
        return False
    return True


def effective_card_action(
    row: Dict[str, Any],
    authority: Dict[str, Any],
) -> str:
    """Min(card.action, authority ceiling) with honest downgrade labels."""
    raw = _norm_action_label(row.get("raw_action") or row.get("action"))
    if raw in _AUTHORITY_AVOID_ACTIONS:
        return raw if raw != "NO_TRADE" else "AVOID"

    if raw in _AUTHORITY_TRADE_ACTIONS and not _trade_label_allowed(row, authority):
        return _downgrade_display_label(raw, authority, row)

    ceiling = _authority_ceiling_rank(authority)
    raw_rank = _action_authority_rank(raw)

    if raw_rank <= ceiling:
        return raw

    return _downgrade_display_label(raw, authority, row)


def effective_card_grade(
    row: Dict[str, Any],
    authority: Dict[str, Any],
) -> str:
    """Alias for card execution grade — same rules as effective_card_action."""
    return effective_card_action(row, authority)


card_execution_grade = effective_card_grade


def apply_authority_to_row(
    row: Dict[str, Any],
    authority: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach effective action, confidence assembly, and authority metadata to a card row."""
    out = dict(row)
    if "raw_action" not in out:
        out["raw_action"] = out.get("action")
    conf = assemble_confidence_breakdown(out)
    out["confidence_breakdown"] = conf
    out["final_conf"] = conf.get("final")
    out["confidence_unavailable"] = bool(conf.get("unavailable"))
    out["confidence_fallback_only"] = bool(conf.get("fallback_only"))
    if conf.get("label"):
        out["confidence_label"] = conf["label"]
    eff = effective_card_action(out, authority)
    out["effective_action"] = eff
    out["effective_grade"] = eff
    out["action"] = eff
    if eff != out.get("raw_action"):
        out["authority_downgraded"] = True
        gates = authority.get("gates") or {}
        if gates.get("fallback_brief"):
            out["action_reason"] = (
                "Reference plan only — indicative levels · monitor zone · "
                "no deploy authority (live scanner unavailable)"
            )
        elif gates.get("broker_offline"):
            out["action_reason"] = "Broker offline — card blocked from deploy authority"
        elif gates.get("engine_off"):
            out["action_reason"] = "Engine off — no live execution authority"
        elif not _row_rr_available(out):
            out["action_reason"] = "R:R unavailable — cannot label TRADE"
    out["decision_authority"] = {
        "source": authority.get("source"),
        "effective_action_max": authority.get("effective_action_max"),
        "allows_trade_labels": authority.get("allows_trade_labels"),
    }
    eff_u = str(out.get("effective_action") or "").upper()
    raw_u = str(out.get("raw_action") or "").upper()
    gates = authority.get("gates") or {}
    blocked = bool(
        eff_u == "BLOCKED"
        or gates.get("exec_blocked")
        or gates.get("broker_offline")
        or gates.get("engine_off")
    )
    if blocked:
        out["pilot_state"] = "BLOCKED"
    elif (
        bool(out.get("execution_ready"))
        and eff_u in _AUTHORITY_TRADE_ACTIONS
        and bool(authority.get("allows_trade_labels"))
        and not bool(authority.get("gates_active"))
    ):
        out["pilot_state"] = "FULL_DEPLOY"
    elif raw_u == "PILOT" or eff_u == "PILOT":
        if (
            bool(out.get("execution_ready"))
            and str(authority.get("authority_level") or "").lower() == "deploy"
            and not bool(authority.get("gates_active"))
            and not bool(gates.get("regime_wait"))
        ):
            out["pilot_state"] = "PILOT_EXECUTABLE"
        else:
            out["pilot_state"] = "PILOT_RESEARCH_ONLY"
    else:
        out["pilot_state"] = "MONITOR_ONLY"
    return out


def apply_authority_to_rows(
    rows: List[Dict[str, Any]],
    authority: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [apply_authority_to_row(r, authority) for r in rows]


def build_ranked_decision_authority(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Derive decision authority for playbook ranked / degraded boards."""
    existing = payload.get("decision_authority")
    stale_serve = bool(
        payload.get("stale")
        or payload.get("cached")
        or payload.get("refreshing")
    )
    if (
        isinstance(existing, dict)
        and existing.get("gates") is not None
        and not stale_serve
    ):
        return existing
    ba = payload.get("best_action") or {}
    ex = ba.get("execution_readiness") or payload.get("execution_readiness") or {}
    tradeability = str(ba.get("tradeability") or "WAIT").upper()
    source = str(payload.get("source") or "").lower()
    board_mode = str(payload.get("board_mode") or "").lower()
    stale = bool(payload.get("stale") or payload.get("cached"))
    fallback_brief = (
        board_mode == "compressed_fallback"
        or "brief" in source
        or "fallback" in source
        or payload.get("compressed")
    )
    try:
        from src.services.ibkr_service import ibkr_authority_gate_snapshot

        st = ibkr_authority_gate_snapshot()
        ibkr_on = bool(st.get("connected"))
        exec_blocked = bool(st.get("circuit_breaker") or ex.get("circuit_breaker"))
    except Exception:
        ibkr_on = False
        exec_blocked = False
    opps = payload.get("opportunities") or []
    deploy_n = sum(1 for o in opps if o.get("execution_ready"))
    return build_decision_authority(
        tradeability=tradeability if not fallback_brief else "WAIT",
        should_trade=tradeability not in ("NO_TRADE", "WAIT") and not fallback_brief,
        scanner_degraded=stale or fallback_brief,
        data_stale=stale,
        fallback_brief=fallback_brief,
        broker_offline=not ibkr_on,
        engine_off=not bool(ex.get("engine_running")),
        exec_blocked=exec_blocked,
        ranked_source=source or "ranked",
        ranked_stale=stale,
        deploy_ideas_count=deploy_n,
    )


def finalize_ranked_payload_authority(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply authority to every ranked row before JSON serialization."""
    authority = build_ranked_decision_authority(payload)
    payload["decision_authority"] = authority
    for key in ("opportunities", "near_miss", "near_miss_rows"):
        rows = payload.get(key)
        if rows:
            payload[key] = apply_authority_to_rows(rows, authority)
    return payload


class _PipelineWrap:
    """Adapter so sector pipeline results work with council-oriented helpers."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline


def enrich_row_from_pipeline(pipeline: Any, row: Dict[str, Any]) -> Dict[str, Any]:
    return enrich_opportunity_row(_PipelineWrap(pipeline), row)


def enrich_opportunity_row(
    cr: Any,
    row: Dict[str, Any],
    *,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    sector_laggards: Optional[List[Dict[str, Any]]] = None,
    decision_authority: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply refined action + pilot fields to a playbook/today row."""
    act = refine_action(cr)
    row = {
        **row,
        "action": act,
        "raw_action": act,
        "execution_ready": is_execution_ready(cr),
    }
    row["trade_bar"] = build_trade_bar_status(row)
    align, align_label = sector_tailwind_for_row(
        row, sector_leaders=sector_leaders, sector_laggards=sector_laggards
    )
    row["sector_alignment"] = align
    row["sector_alignment_label"] = align_label
    row["rank_explain"] = build_rank_explain(
        row, sector_leaders=sector_leaders, sector_laggards=sector_laggards
    )
    rr_raw = row.get("risk_reward")
    if is_below_trade_rr_threshold(rr_raw):
        row["rr_below_trade_threshold"] = True
        row["rr_gate_label"] = "Below TRADE R:R threshold"
        if act == "PILOT":
            row["size_eligibility"] = "Pilot only"
        elif act in _WATCH_ACTIONS:
            row["size_eligibility"] = "Not full-size eligible"
        else:
            row["size_eligibility"] = "Pilot only"
    if act == "PILOT" and is_pilot_eligible(cr):
        row.update(build_pilot_explanations(cr))
    elif act == "PILOT":
        row["action"] = "WATCH"
        row["pilot_downgraded"] = True
    try:
        pr = cr.pipeline
        sig = pr.signal
        cal_n = sig.get("calibration_n") or 0
        cal_avail = bool(cal_n and int(cal_n) >= 30)
        row["evidence_quality"] = {
            "data_conf": round(float(pr.confidence.data), 2),
            "freshness": sig.get("data_freshness") or "unknown",
            "sample_count": cal_n,
            "calibration_available": cal_avail,
            "raw_score": sig.get("score"),
            "validated_score": round(_score(cr), 1),
        }
        row["setup_evidence"] = {
            "sample_size": cal_n,
            "win_rate": sig.get("historical_win_rate") or sig.get("win_rate"),
            "avg_r": sig.get("avg_r") or sig.get("expectancy_r"),
            "regime_follow_through": sig.get("regime_fit")
            or pr.sector.sector_bucket.value,
            "calibration_note": (
                f"Calibrated n={cal_n} — use validated score"
                if cal_avail
                else "Uncalibrated — confidence is model prior, not live hit-rate"
            ),
        }
    except Exception:
        pass
    try:
        from src.services.candlestick_context import tags_for_playbook_row
        from src.services.cost_adjusted_edge import attach_net_edge_to_row
        from src.services.crowding_narrative import attach_crowding_to_row
        from src.services.humility_labels import labels_for_playbook_row
        from src.services.score_families import attach_score_families_to_row

        sig = cr.pipeline.signal if hasattr(cr, "pipeline") else {}
        nison_tags = tags_for_playbook_row(
            signal=sig if isinstance(sig, dict) else None
        )
        row.update(
            {
                "nison_pattern_tag": nison_tags.get("pattern_tag"),
                "nison_context_label": nison_tags.get("context_label"),
                "nison_context_tag": nison_tags.get("context_tag"),
                "nison_rr_tag": nison_tags.get("rr_tag"),
                "nison_trend_tag": nison_tags.get("trend_tag"),
                "nison_execution_status": nison_tags.get("nison_execution_status"),
                "nison_humility": nison_tags.get("nison_humility") or [],
            }
        )

        row = attach_net_edge_to_row(row)
        row = attach_crowding_to_row(row)
        row = attach_score_families_to_row(row)
        row["guardrail_labels"] = labels_for_playbook_row(row)
        from src.services.buffett_judgment import tags_for_playbook_row as buffett_tags
        from src.services.crisis_regime import tags_for_playbook_row as crisis_tags
        from src.services.index_fund_judgment import (
            tags_for_playbook_row as index_fund_tags,
        )
        from src.services.opportunity_quality_naval import (
            tags_for_playbook_row as naval_quality_tags,
        )
        from src.services.signal_to_noise import (
            tags_for_playbook_row as naval_signal_tags,
        )
        from src.services.specific_knowledge import (
            tags_for_playbook_row as naval_competence_tags,
        )
        from src.services.turtle_system import tags_for_playbook_row as turtle_tags
        from src.services.value_investing import tags_for_playbook_row as value_tags

        tb = str(row.get("tradeability") or row.get("honest_tradeability") or "")
        deploy_n = int(row.get("deployable_count") or 0)
        row.update(value_tags(row, tradeability=tb))
        row.update(buffett_tags(row, tradeability=tb))
        row.update(index_fund_tags(row, tradeability=tb))
        row.update(turtle_tags(row, tradeability=tb))
        row.update(crisis_tags(row, tradeability=tb, market_vix=row.get("vix")))
        row.update(naval_signal_tags(row, tradeability=tb, deployable_count=deploy_n))
        row.update(naval_competence_tags(row, tradeability=tb))
        row.update(naval_quality_tags(row, tradeability=tb))
        from src.services.principles_engine import (
            tags_for_playbook_row as principles_tags,
        )

        row.update(principles_tags(row, tradeability=tb))
    except Exception:
        pass
    if decision_authority:
        row = apply_authority_to_row(row, decision_authority)
    else:
        conf = assemble_confidence_breakdown(row)
        row["confidence_breakdown"] = conf
        row["final_conf"] = conf.get("final")
        row["confidence_unavailable"] = bool(conf.get("unavailable"))
    try:
        from src.services.buy_signal_summary import attach_buy_signal_summary

        row = attach_buy_signal_summary(row)
    except Exception:
        pass
    return row
