"""
《原则系列（共2册）》Principles series — decision OS layer for CC.

Radical transparency, believability-weighted evidence, process quality
independent of outcome, and pain-plus-reflection learning. Sits above
honest gates (WAIT, research-only) — never overrides them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

DecisionPosture = Literal["allowed", "deferred", "blocked"]
TruthClass = Literal["fact", "stale", "estimated", "unknown"]
EvidenceTier = Literal["high", "medium", "low", "insufficient"]
DecisionGrade = Literal["A", "B", "C", "D"]
RootCauseClass = Literal[
    "data_failure",
    "process_gap",
    "regime_mismatch",
    "execution_failure",
    "judgment_error",
    "unknown",
]

PRINCIPLE_TAGS = (
    "radical_transparency",
    "believability_weighted",
    "machine_consistency",
    "pain_plus_reflection",
    "root_cause_first",
    "process_over_outcome",
)

_GOVERNING_BY_TRADEABILITY = {
    "TRADE": "machine_consistency",
    "SELECTIVE": "believability_weighted",
    "STRONG_TRADE": "machine_consistency",
    "WAIT": "process_over_outcome",
    "NO_TRADE": "radical_transparency",
}


def classify_truth_integrity(row: Dict[str, Any]) -> Dict[str, Any]:
    """Separate fact vs stale vs estimated vs unknown."""
    data_conf = float(row.get("data_conf") or 0)
    freshness = str(row.get("data_freshness") or row.get("freshness") or "").lower()
    cal_n = int(row.get("calibration_n") or row.get("sample_count") or 0)
    has_levels = bool(
        float(row.get("entry_price") or 0) > 0
        or float(row.get("stop_price") or 0) > 0
    )

    if data_conf >= 0.65 and freshness in ("fresh", "real_time", "live"):
        integrity: TruthClass = "fact"
        label = "verified facts — data fresh and confidence high"
    elif data_conf >= 0.45 or freshness in ("recent", "cached"):
        integrity = "estimated"
        label = "estimated — model prior or partial data"
    elif freshness in ("stale", "degraded", "old"):
        integrity = "stale"
        label = "stale — refresh before acting"
    elif data_conf < 0.35 and not has_levels:
        integrity = "unknown"
        label = "unknown — insufficient evidence to treat as fact"
    else:
        integrity = "estimated"
        label = "estimated — treat claims as hypothesis"

    unknowns: List[str] = []
    if integrity in ("stale", "unknown"):
        unknowns.append("data integrity gap — verify before sizing")
    if cal_n < 30:
        unknowns.append(f"uncalibrated sample (n={cal_n})")
    if not row.get("invalidation"):
        unknowns.append("invalidation not explicit")

    return {
        "integrity": integrity,
        "integrity_label": label,
        "unknowns": unknowns[:4],
        "data_conf": round(data_conf, 2),
        "freshness": freshness or "unknown",
    }


def score_evidence_weight(row: Dict[str, Any]) -> Dict[str, Any]:
    """Believability-weighted evidence — sample, calibration, confidence spread."""
    thesis = float(row.get("thesis_conf") or 0)
    timing = float(row.get("timing_conf") or 0)
    data = float(row.get("data_conf") or 0)
    cal_n = int(row.get("calibration_n") or row.get("sample_count") or 0)
    cal_avail = cal_n >= 30
    exec_ready = bool(row.get("execution_ready"))

    believability = (thesis * 0.4 + timing * 0.25 + data * 0.35)
    if cal_avail:
        believability = min(1.0, believability + 0.08)
    if exec_ready and thesis >= 0.6:
        believability = min(1.0, believability + 0.05)

    if believability >= 0.68 and cal_avail:
        tier: EvidenceTier = "high"
        label = "high believability — calibrated evidence supports action path"
    elif believability >= 0.52:
        tier = "medium"
        label = "medium believability — research or pilot only"
    elif believability >= 0.38:
        tier = "low"
        label = "low believability — defer until evidence improves"
    else:
        tier = "insufficient"
        label = "insufficient — do not treat rank as conviction"

    return {
        "tier": tier,
        "evidence_quality": tier,
        "believability_score": round(believability, 2),
        "label": label,
        "calibration_available": cal_avail,
        "sample_count": cal_n,
    }


def evaluate_decision_quality_principles(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Process quality independent of outcome — grade the decision process."""
    truth = classify_truth_integrity(row)
    evidence = score_evidence_weight(row)
    invalidation = str(row.get("invalidation") or "")
    why_not = str(row.get("why_not") or row.get("why_not_stronger") or "")
    thesis = float(row.get("thesis_conf") or 0)

    process_points = 0
    if truth["integrity"] in ("fact", "estimated"):
        process_points += 1
    if evidence["tier"] in ("high", "medium"):
        process_points += 1
    if invalidation:
        process_points += 1
    if why_not or thesis < 0.55:
        process_points += 1  # objections named or appropriately cautious
    if truth["unknowns"] and len(truth["unknowns"]) <= 2:
        process_points += 1  # unknowns explicitly listed

    if process_points >= 4:
        grade: DecisionGrade = "A"
        label = "process strong — facts, objections, and unknowns handled"
    elif process_points >= 3:
        grade = "B"
        label = "process adequate — minor gaps before full size"
    elif process_points >= 2:
        grade = "C"
        label = "process thin — research only until gaps close"
    else:
        grade = "D"
        label = "process weak — do not act on narrative alone"

    tb = (tradeability or "").upper()
    if tb in ("WAIT", "NO_TRADE") and grade in ("C", "D"):
        label += " — board gate already defers action"

    return {
        "grade": grade,
        "decision_grade": grade,
        "process_label": label,
        "process_points": process_points,
        "outcome_independent": True,
        "principle": "process_over_outcome",
    }


def classify_root_cause(
    *,
    component: str = "",
    message: str = "",
    detail: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify failure modes for pain-plus-reflection loop."""
    text = f"{component} {message} {detail}".lower()
    meta = meta or {}

    if any(k in text for k in ("503", "timeout", "stale", "cache", "data", "provider")):
        cause: RootCauseClass = "data_failure"
        lesson = "Refresh data path; do not trade on stale or missing facts"
    elif any(k in text for k in ("regime", "vix", "breadth", "wait", "no_trade")):
        cause = "regime_mismatch"
        lesson = "Regime gate blocked action — respect machine constraint"
    elif any(k in text for k in ("broker", "order", "execution", "ibkr", "handoff")):
        cause = "execution_failure"
        lesson = "Fix execution path before sizing; process over outcome"
    elif any(k in text for k in ("engine", "scheduler", "cycle", "pipeline")):
        cause = "process_gap"
        lesson = "Machine not running — restore process before judgment"
    elif any(k in text for k in ("thesis", "conviction", "judgment", "override")):
        cause = "judgment_error"
        lesson = "Name the mistake; update principle or checklist"
    else:
        cause = "unknown"
        lesson = "Log pain, classify root cause, encode lesson in machine"

    return {
        "root_cause": cause,
        "root_cause_label": cause.replace("_", " "),
        "lesson": lesson,
        "principle": "pain_plus_reflection",
    }


def log_principles_lesson(
    *,
    severity: str,
    component: str,
    message: str,
    detail: str,
    suggested_action: str = "",
    dedupe_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Append platform error with root_cause + lesson fields."""
    from src.services.platform_error_log import log_platform_error

    rc = classify_root_cause(
        component=component, message=message, detail=detail, meta=meta
    )
    merged_meta = {**(meta or {}), **rc}
    return log_platform_error(
        severity=severity,  # type: ignore[arg-type]
        component=component,
        message=message,
        detail=detail,
        suggested_action=suggested_action or rc["lesson"],
        dedupe_key=dedupe_key,
        meta=merged_meta,
        root_cause=rc["root_cause"],
        lesson=rc["lesson"],
    )


def evaluate_decision_posture(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Principle-based allowed / deferred / blocked — aligns with honest gates."""
    tb = (tradeability or row.get("tradeability") or row.get("honest_tradeability") or "WAIT").upper()
    truth = classify_truth_integrity(row)
    evidence = score_evidence_weight(row)
    quality = evaluate_decision_quality_principles(row, tradeability=tb)
    act = (row.get("action") or "").upper()

    blocked_reasons: List[str] = []
    if tb in ("WAIT", "NO_TRADE"):
        blocked_reasons.append("board gate — WAIT / NO_TRADE")
    if truth["integrity"] in ("stale", "unknown"):
        blocked_reasons.append(f"truth integrity: {truth['integrity']}")
    if evidence["tier"] == "insufficient":
        blocked_reasons.append("insufficient believable evidence")
    if quality["grade"] == "D":
        blocked_reasons.append("process grade D — narrative-only")

    if blocked_reasons:
        posture: DecisionPosture = "blocked"
        headline = "Action blocked by principle — " + blocked_reasons[0]
    elif tb in ("TRADE", "SELECTIVE", "STRONG_TRADE") and act in ("TRADE", "BUY", "PILOT"):
        if quality["grade"] in ("A", "B") and evidence["tier"] in ("high", "medium"):
            posture = "allowed"
            headline = "Principle path open — process and evidence align with gate"
        else:
            posture = "deferred"
            headline = "Deferred — improve process or evidence before full size"
    elif act in ("WATCH", "WAIT", "PILOT"):
        posture = "deferred"
        headline = "Deferred — research or pilot until principle checklist passes"
    else:
        posture = "blocked" if blocked_reasons else "deferred"
        headline = blocked_reasons[0] if blocked_reasons else "Deferred — no deploy path"

    principle_tags: List[str] = []
    if truth["integrity"] != "fact":
        principle_tags.append("radical_transparency")
    if evidence["tier"] in ("high", "medium"):
        principle_tags.append("believability_weighted")
    principle_tags.append("process_over_outcome")
    if blocked_reasons:
        principle_tags.append("machine_consistency")

    return {
        "posture": posture,
        "headline": headline,
        "blocked_reasons": blocked_reasons[:3],
        "principle_tags": principle_tags[:4],
        "principle_support": "strong" if posture == "allowed" else "weak" if posture == "blocked" else "partial",
        "governing_principle": _GOVERNING_BY_TRADEABILITY.get(tb, "process_over_outcome"),
        "truth_integrity": truth["integrity"],
        "evidence_quality": evidence["tier"],
        "decision_grade": quality["grade"],
        "authority": "research_only" if posture == "blocked" else "supportive",
    }


def tags_for_playbook_row(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Playbook enrich: principle_support, evidence_quality, decision_grade."""
    posture = evaluate_decision_posture(row, tradeability=tradeability)
    return {
        "principle_support": posture["principle_support"],
        "principle_tags": posture["principle_tags"],
        "evidence_quality": posture["evidence_quality"],
        "decision_grade": posture["decision_grade"],
        "truth_integrity": posture["truth_integrity"],
        "principles_posture": posture["posture"],
        "principles_blocked": posture["posture"] == "blocked",
        "governing_principle": posture["governing_principle"],
    }


def build_principles_memo(
    *,
    ticker: str,
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dossier principles_memo — known facts, unknowns, evidence weight, decision."""
    row = {
        "ticker": ticker,
        "score": unified.get("score") or dossier.get("score"),
        "thesis_conf": (unified.get("confidence") or {}).get("thesis")
        or dossier.get("thesis_conf"),
        "timing_conf": (unified.get("confidence") or {}).get("timing"),
        "data_conf": (unified.get("confidence") or {}).get("data"),
        "action": unified.get("action") or unified.get("verdict"),
        "invalidation": dossier.get("invalidation"),
        "why_not": unified.get("why_not") or dossier.get("why_not"),
        "execution_ready": unified.get("execution_ready"),
        "data_freshness": (dossier.get("signal") or {}).get("data_freshness"),
        "calibration_n": (dossier.get("signal") or {}).get("calibration_n"),
    }
    tb = str((regime or {}).get("tradeability") or "")
    truth = classify_truth_integrity(row)
    evidence = score_evidence_weight(row)
    quality = evaluate_decision_quality_principles(row, tradeability=tb)
    posture = evaluate_decision_posture(row, tradeability=tb)

    known_facts: List[str] = []
    if truth["integrity"] == "fact":
        known_facts.append("Fresh data with high confidence")
    if row.get("invalidation"):
        known_facts.append(f"Invalidation defined: {str(row['invalidation'])[:60]}")
    if float(row.get("thesis_conf") or 0) >= 0.6:
        known_facts.append(f"Thesis confidence {float(row['thesis_conf']):.0%}")

    summary = (
        f"{posture['posture'].upper()} — {quality['process_label']}. "
        f"Evidence {evidence['tier']}; truth {truth['integrity']}."
    )

    return {
        "mode": "principles_series",
        "summary_30s": summary,
        "known_facts": known_facts[:4],
        "unknowns": truth["unknowns"],
        "truth_integrity": truth["integrity"],
        "truth_label": truth["integrity_label"],
        "evidence_quality": evidence["tier"],
        "evidence_label": evidence["label"],
        "decision_grade": quality["grade"],
        "process_label": quality["process_label"],
        "principle_decision": posture["posture"],
        "principle_headline": posture["headline"],
        "governing_principle": posture["governing_principle"],
        "principle_tags": posture["principle_tags"],
        "blocked_reasons": posture["blocked_reasons"],
        "authority": posture["authority"],
    }


def principles_posture_for_today(
    market_regime: Dict[str, Any],
    decision_model: Dict[str, Any],
    *,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Dashboard principles_posture on /api/v7/today."""
    tb = str(
        decision_model.get("honest_tradeability")
        or market_regime.get("tradeability")
        or "WAIT"
    )
    governing = _GOVERNING_BY_TRADEABILITY.get(tb, "process_over_outcome")

    opps = opportunities or []
    blocked_count = 0
    allowed_count = 0
    stale_count = 0
    for o in opps[:15]:
        p = evaluate_decision_posture(o, tradeability=tb)
        if p["posture"] == "blocked":
            blocked_count += 1
        elif p["posture"] == "allowed":
            allowed_count += 1
        if p["truth_integrity"] in ("stale", "unknown"):
            stale_count += 1

    if tb in ("WAIT", "NO_TRADE"):
        action_blocked = True
        headline = "Action blocked by principle — board says WAIT; process over outcome"
        banner = "No deploy until facts, evidence, and gates align — success is correct deferral"
    elif stale_count >= max(3, len(opps) // 2) and opps:
        action_blocked = True
        headline = f"Fact integrity weak — {stale_count} setups on stale/unknown data"
        banner = "Radical transparency: refresh facts before sizing"
    elif deployable_count > 0 and allowed_count > 0:
        action_blocked = False
        headline = f"Principle path open for {allowed_count} name(s) — believability-weighted"
        banner = "Machine consistency — act only where process grade and evidence align"
    elif deployable_count > 0:
        action_blocked = True
        headline = "Deploy candidates fail principle checklist — defer or pilot only"
        banner = "Improve process grade or evidence before full size"
    else:
        action_blocked = tb not in ("TRADE", "SELECTIVE", "STRONG_TRADE")
        headline = "Deferred — no execution-ready setups pass principle bar"
        banner = "Pain plus reflection: log gaps, do not force trades"

    integrity_summary = "mixed"
    if not opps:
        integrity_summary = "no_scan"
    elif stale_count == 0:
        integrity_summary = "acceptable"
    elif stale_count >= len(opps) // 2:
        integrity_summary = "degraded"

    return {
        "mode": "principles_series",
        "headline": headline,
        "banner": banner,
        "governing_principle": governing,
        "fact_integrity": integrity_summary,
        "action_blocked_by_principle": action_blocked,
        "blocked_setup_count": blocked_count,
        "allowed_setup_count": allowed_count,
        "stale_or_unknown_count": stale_count,
        "tradeability": tb,
        "principle_tags": [
            "radical_transparency",
            "believability_weighted",
            "process_over_outcome",
        ],
    }
