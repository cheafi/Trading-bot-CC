"""
Research-quality classification for opportunity rows — rank ≠ quality ≠ authority.

Quality tiers inform monitor prioritization only; they never set deploy_eligible
or bypass Decision Engine gates (WAIT / NO_TRADE / STALE / BROKER_DOWN).
"""

from __future__ import annotations

import glob
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.decision_truth_model import TRADE_RR_THRESHOLD
from src.services.operator_state_contract import structural_valid_for_monitor
from src.utils.numeric_parse import parse_ratio

BRIEF_STALE_DAYS = 7

_REJECT_ACTIONS = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE"})


def _conf(row: Dict[str, Any], key: str) -> float:
    cb = row.get("confidence_breakdown") or {}
    alias = {
        "thesis_conf": "thesis",
        "timing_conf": "timing",
        "exec_conf": "execution",
        "data_conf": "data",
    }
    cb_key = alias.get(key, key.replace("_conf", ""))
    raw = cb.get(cb_key)
    if raw is None:
        raw = row.get(key)
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _rr(row: Dict[str, Any]) -> float:
    return parse_ratio(row.get("risk_reward"), 0.0) or 0.0


def _is_laggard(row: Dict[str, Any]) -> bool:
    if str(row.get("leader") or "").upper() == "LAGGARD":
        return True
    rs = row.get("rs") or {}
    if str(rs.get("rs_status") or "").upper() == "LAGGARD":
        return True
    why_not = row.get("why_not") or row.get("why_not_trade") or ""
    if isinstance(why_not, list):
        why_not = " ".join(str(x) for x in why_not)
    rank_explain = row.get("rank_explain") or []
    if isinstance(rank_explain, list):
        why_not = f"{why_not} {' '.join(rank_explain)}"
    return "laggard" in str(why_not).lower()


def _has_major_conflict(row: Dict[str, Any]) -> bool:
    return str(row.get("conflict_level") or "").upper() == "HIGH"


def _is_extended(row: Dict[str, Any]) -> bool:
    struct = row.get("structure") or {}
    return bool(struct.get("is_extended"))


def _is_monitor_qualified(row: Dict[str, Any]) -> bool:
    if not structural_valid_for_monitor(row):
        return False
    act = str(row.get("action") or row.get("raw_action") or "").upper()
    if act in _REJECT_ACTIONS and not row.get("execution_ready"):
        return float(row.get("score") or 0) < 5.0
    return True


def _gate_checks(
    row: Dict[str, Any],
    *,
    data_stale: bool,
    brief_stale: bool,
) -> Dict[str, bool]:
    thesis = _conf(row, "thesis_conf")
    timing = _conf(row, "timing_conf")
    execution = _conf(row, "exec_conf")
    data = _conf(row, "data_conf")
    rr = _rr(row)
    fresh = not data_stale and not brief_stale
    evidence = row.get("evidence_quality") or {}
    freshness = str(evidence.get("freshness") or "").lower()
    if freshness in ("stale", "degraded", "critical"):
        fresh = False
    return {
        "fresh_data": fresh,
        "rr_ok": rr >= TRADE_RR_THRESHOLD,
        "thesis_ok": thesis >= 0.60,
        "timing_ok": timing >= 0.60,
        "execution_ok": execution >= 0.60,
        "data_ok": data >= 0.70,
        "no_major_conflict": not _has_major_conflict(row),
        "not_laggard": not _is_laggard(row),
        "not_extended": not _is_extended(row),
    }


def _quality_score(gates: Dict[str, bool], row: Dict[str, Any]) -> int:
    weights = {
        "fresh_data": 12,
        "rr_ok": 18,
        "thesis_ok": 18,
        "timing_ok": 16,
        "execution_ok": 14,
        "data_ok": 12,
        "no_major_conflict": 5,
        "not_laggard": 3,
        "not_extended": 2,
    }
    base = sum(weights[k] for k, ok in gates.items() if ok)
    thesis = _conf(row, "thesis_conf")
    timing = _conf(row, "timing_conf")
    rr = _rr(row)
    partial = 0
    if 0.50 <= thesis < 0.60:
        partial += 4
    if 0.50 <= timing < 0.60:
        partial += 3
    if TRADE_RR_THRESHOLD > rr >= 2.0:
        partial += 3
    return min(100, base + partial)


def _upgrade_path(gates: Dict[str, bool], row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if not gates["rr_ok"]:
        rr = _rr(row)
        out.append(f"Raise R:R to ≥{TRADE_RR_THRESHOLD:.1f} (now {rr:.1f})")
    if not gates["thesis_ok"]:
        out.append(f"Thesis ≥60% (now {_conf(row, 'thesis_conf') * 100:.0f}%)")
    if not gates["timing_ok"]:
        out.append(f"Timing ≥60% (now {_conf(row, 'timing_conf') * 100:.0f}%)")
    if not gates["execution_ok"]:
        out.append(f"Execution ≥60% (now {_conf(row, 'exec_conf') * 100:.0f}%)")
    if not gates["data_ok"]:
        out.append(f"Data ≥70% (now {_conf(row, 'data_conf') * 100:.0f}%)")
    if not gates["fresh_data"]:
        out.append("Refresh live data — stale context caps quality")
    if not gates["not_laggard"]:
        out.append("Improve sector leadership — laggard penalty")
    if not gates["no_major_conflict"]:
        out.append("Resolve structural / regime conflict")
    if not gates["not_extended"]:
        out.append("Wait for pullback — extended structure")
    return out[:5]


def _reasons_for_tier(
    tier: str,
    gates: Dict[str, bool],
    row: Dict[str, Any],
    *,
    data_stale: bool,
    brief_stale: bool,
) -> List[str]:
    reasons: List[str] = []
    if brief_stale:
        reasons.append("Brief context stale — research only")
    if data_stale:
        reasons.append("Live data degraded — quality capped")
    if tier == "REJECT":
        if _is_extended(row):
            reasons.append("Extended structure — do not chase")
        if _conf(row, "data_conf") < 0.40:
            reasons.append("Low data confidence")
        act = str(row.get("action") or "").upper()
        if act in _REJECT_ACTIONS:
            reasons.append(f"Action {act} — rejected for monitor quality")
        if not reasons:
            reasons.append("Fails minimum research-quality bar")
        return reasons[:4]
    failed = [k for k, ok in gates.items() if not ok]
    label_map = {
        "fresh_data": "Data not fresh",
        "rr_ok": f"R:R below {TRADE_RR_THRESHOLD:.1f}",
        "thesis_ok": "Thesis below 60%",
        "timing_ok": "Timing below 60%",
        "execution_ok": "Execution below 60%",
        "data_ok": "Data below 70%",
        "no_major_conflict": "Major structural conflict",
        "not_laggard": "Sector laggard",
        "not_extended": "Extended price structure",
    }
    for key in failed:
        lbl = label_map.get(key)
        if lbl:
            reasons.append(lbl)
    if tier == "WEAK" and not reasons:
        reasons.append("Monitor-qualified but below research-quality bar")
    return reasons[:5]


def classify_opportunity_quality(
    row: Dict[str, Any],
    *,
    data_stale: bool = False,
    brief_stale: bool = False,
) -> Dict[str, Any]:
    """Per-row research quality — never grants deploy authority."""
    gates = _gate_checks(row, data_stale=data_stale, brief_stale=brief_stale)
    score = _quality_score(gates, row)
    act = str(row.get("action") or row.get("raw_action") or "").upper()

    research_context_only = brief_stale
    if research_context_only:
        row = dict(row)
        row["research_context_only"] = True

    if (
        brief_stale
        or data_stale
        or _is_extended(row)
        or _conf(row, "data_conf") < 0.35
        or (act in _REJECT_ACTIONS and float(row.get("score") or 0) < 4.5)
    ):
        tier = "REJECT"
    elif all(gates.values()):
        tier = "STRONG" if not _is_laggard(row) else "PROMISING"
    elif sum(1 for ok in gates.values() if ok) >= 5 and score >= 55:
        tier = "PROMISING"
    elif _is_monitor_qualified(row):
        tier = "WEAK"
    else:
        tier = "REJECT"

    if brief_stale and tier == "STRONG":
        tier = "PROMISING"
        score = min(score, 74)

    if data_stale and tier == "STRONG":
        tier = "PROMISING"
        score = min(score, 79)

    reasons = _reasons_for_tier(tier, gates, row, data_stale=data_stale, brief_stale=brief_stale)
    upgrade = _upgrade_path(gates, row) if tier in ("WEAK", "PROMISING") else []

    return {
        "tier": tier,
        "score": score,
        "reasons": reasons,
        "upgrade_path": upgrade,
        "gates": gates,
        "research_context_only": research_context_only or bool(row.get("research_context_only")),
        "label_zh": {
            "STRONG": "強 · STRONG",
            "PROMISING": "可期 · PROMISING",
            "WEAK": "偏弱 · WEAK",
            "REJECT": "拒絕 · REJECT",
        }.get(tier, tier),
        "note": (
            "Research quality only — Decision Engine controls deploy authority"
            if tier == "STRONG"
            else "Rank ≠ quality ≠ deploy permission"
        ),
    }


def build_quality_decomposition(row: Dict[str, Any]) -> Dict[str, Any]:
    """Six-axis quality breakdown for card display."""
    struct = row.get("structure") or {}
    thesis = _conf(row, "thesis_conf")
    timing = _conf(row, "timing_conf")
    rr = _rr(row)
    data = _conf(row, "data_conf")
    leader = str(row.get("leader") or "").upper()
    pf = row.get("portfolio_gate") or {}

    structure_score = 70
    if struct.get("is_extended"):
        structure_score = 25
    elif struct.get("trend") == "uptrend":
        structure_score = 85
    elif struct.get("trend") == "downtrend":
        structure_score = 35

    rr_score = min(100, int(rr / TRADE_RR_THRESHOLD * 100)) if rr > 0 else 20
    leadership_score = {"LEADER": 90, "STRONG": 75, "NEUTRAL": 55, "LAGGARD": 25}.get(
        leader, 50
    )
    timing_score = int(timing * 100)
    evidence_score = int(data * 100)
    pf_allowed = pf.get("allowed")
    portfolio_score = 80 if pf_allowed is not False else 40

    return {
        "structure": {"score": structure_score, "extended": bool(struct.get("is_extended"))},
        "reward_risk": {"score": rr_score, "rr": round(rr, 2)},
        "leadership": {"score": leadership_score, "leader": leader or "—"},
        "timing": {"score": timing_score, "thesis": round(thesis, 2)},
        "evidence": {"score": evidence_score, "data_conf": round(data, 2)},
        "portfolio_fit": {"score": portfolio_score, "allowed": pf_allowed},
    }


def brief_age_days() -> Optional[int]:
    """Age of latest brief-*.json in days, if discoverable."""
    try:
        brief_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        files = sorted(glob.glob(os.path.join(brief_dir, "brief-*.json")))
        if not files:
            return None
        path = files[-1]
        m = re.search(r"brief-(\d{4}-\d{2}-\d{2})\.json", os.path.basename(path))
        if m:
            brief_dt = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - brief_dt).days)
        mtime = os.path.getmtime(path)
        return max(0, int((datetime.now(timezone.utc).timestamp() - mtime) / 86400))
    except Exception:
        return None


def resolve_brief_stale_context(
    *,
    used_brief_fallback: bool = False,
    trust: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    age = brief_age_days()
    stale = bool(used_brief_fallback)
    if age is not None and age > BRIEF_STALE_DAYS:
        stale = True
    if trust and str(trust.get("source") or "").startswith("brief"):
        stale = True
    return {
        "brief_stale": stale,
        "brief_age_days": age,
        "brief_stale_threshold_days": BRIEF_STALE_DAYS,
        "research_context_only": stale,
    }


def attach_quality_to_row(
    row: Dict[str, Any],
    *,
    data_stale: bool = False,
    brief_stale: bool = False,
    rank_total: Optional[int] = None,
) -> Dict[str, Any]:
    out = dict(row)
    q = classify_opportunity_quality(out, data_stale=data_stale, brief_stale=brief_stale)
    out["quality"] = q
    out["quality_tier"] = q["tier"]
    out["quality_decomposition"] = build_quality_decomposition(out)
    try:
        from src.services.operator_state_contract import classify_rank_bucket

        out["rank_bucket"] = classify_rank_bucket(out)
    except Exception:
        pass
    if rank_total is not None and out.get("rank"):
        out["rank_label"] = f"#{out['rank']} / {rank_total}"
    return out


def attach_quality_to_rows(
    rows: Optional[List[Dict[str, Any]]],
    *,
    data_stale: bool = False,
    brief_stale: bool = False,
) -> List[Dict[str, Any]]:
    if not rows:
        return []
    total = len(rows)
    return [
        attach_quality_to_row(r, data_stale=data_stale, brief_stale=brief_stale, rank_total=total)
        for r in rows
    ]


def build_opportunity_verdict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Board-level opportunity conclusion for dashboard strip."""
    rows = list(payload.get("top_ranked") or payload.get("top_5") or [])
    near = list(payload.get("near_miss") or [])
    funnel = payload.get("filter_funnel") or {}
    brief_ctx = payload.get("brief_context") or {}
    data_stale = bool(payload.get("data_stale") or payload.get("scanner_degraded"))
    brief_stale = bool(brief_ctx.get("brief_stale") or payload.get("brief_stale"))

    all_rows = rows + near
    if not all(r.get("quality") for r in rows):
        rows = attach_quality_to_rows(rows, data_stale=data_stale, brief_stale=brief_stale)
    if near and not all(r.get("quality") for r in near):
        near = attach_quality_to_rows(near, data_stale=data_stale, brief_stale=brief_stale)

    monitor_qualified = sum(1 for r in all_rows if _is_monitor_qualified(r))
    quality_qualified = sum(
        1 for r in all_rows if (r.get("quality") or {}).get("tier") == "STRONG"
    )
    deploy_qualified = sum(1 for r in all_rows if r.get("execution_ready"))
    if not deploy_qualified:
        deploy_qualified = int(
            funnel.get("deploy_qualified_setups")
            or funnel.get("execution_ready_setups")
            or 0
        )

    promising_rows = [r for r in all_rows if (r.get("quality") or {}).get("tier") == "PROMISING"]
    weak_rows = [r for r in rows if (r.get("quality") or {}).get("tier") == "WEAK"]

    if quality_qualified >= 1:
        state = "QUALITY_AVAILABLE"
        headline = "QUALITY SETUPS AVAILABLE"
        headline_zh = "有達標研究質素候選"
    elif promising_rows:
        state = "PROMISING_ONLY"
        headline = "PROMISING — NOT STRONG"
        headline_zh = "有可期候選 · 未達強質素"
    elif monitor_qualified >= 1:
        state = "NO_HIGH_QUALITY_SETUP"
        headline = "NO HIGH-QUALITY SETUP"
        headline_zh = "無高質素設定"
    else:
        state = "EMPTY_BOARD"
        headline = "NO MONITOR CANDIDATES"
        headline_zh = "無有效監察候選"

    best_monitor: Optional[Dict[str, Any]] = None
    if rows:
        best_monitor = rows[0]
    elif near:
        best_monitor = near[0]

    closest_upgrade: Optional[Dict[str, Any]] = None
    candidates = sorted(
        [r for r in all_rows if (r.get("quality") or {}).get("tier") in ("WEAK", "PROMISING")],
        key=lambda r: int((r.get("quality") or {}).get("score") or 0),
        reverse=True,
    )
    if candidates:
        closest_upgrade = candidates[0]

    main_blocker = ""
    next_action = ""
    if state == "NO_HIGH_QUALITY_SETUP" and best_monitor:
        q = best_monitor.get("quality") or {}
        reasons = q.get("reasons") or []
        main_blocker = reasons[0] if reasons else "Best monitor fails quality gates"
        main_blocker = f"{main_blocker} · 最佳監察仍偏弱"
        next_action = (
            "Watch closest upgrade path — do not treat rank #1 as deploy signal · "
            "監察最接近升級路徑 · 勿將排名當部署訊號"
        )
    elif state == "QUALITY_AVAILABLE":
        main_blocker = "Decision Engine still controls deploy_open"
        next_action = (
            "Review STRONG names — authority gate must still pass · "
            "複核強質素名單 · 仍需通過部署權限閘門"
        )
    elif state == "PROMISING_ONLY":
        main_blocker = "No STRONG tier — partial gates only"
        next_action = (
            "Monitor PROMISING rows for gate upgrades · "
            "監察可期候選直至閘門補齊"
        )
    else:
        main_blocker = "Board empty or all rejected"
        next_action = "Wait for fresh scan · 等待新掃描"

    near_quality = [
        {
            "ticker": r.get("ticker"),
            "tier": (r.get("quality") or {}).get("tier"),
            "score": (r.get("quality") or {}).get("score"),
            "needs": (r.get("quality") or {}).get("upgrade_path") or [],
        }
        for r in promising_rows[:5]
    ]
    do_not_chase = [
        {
            "ticker": r.get("ticker"),
            "reason": ((r.get("quality") or {}).get("reasons") or ["REJECT"])[0],
        }
        for r in all_rows
        if (r.get("quality") or {}).get("tier") == "REJECT"
    ][:5]

    return {
        "state": state,
        "headline": headline,
        "headline_bilingual": f"{headline_zh} · {headline}",
        "monitor_qualified_count": monitor_qualified,
        "quality_qualified_count": quality_qualified,
        "deploy_qualified_count": deploy_qualified,
        "best_monitor": {
            "ticker": best_monitor.get("ticker") if best_monitor else None,
            "why_weak": (
                ((best_monitor.get("quality") or {}).get("reasons") or ["—"])[0]
                if best_monitor
                else None
            ),
            "tier": (best_monitor.get("quality") or {}).get("tier") if best_monitor else None,
            "score": (best_monitor.get("quality") or {}).get("score") if best_monitor else None,
        },
        "closest_upgrade": {
            "ticker": closest_upgrade.get("ticker") if closest_upgrade else None,
            "needs": (closest_upgrade.get("quality") or {}).get("upgrade_path") or []
            if closest_upgrade
            else [],
            "tier": (closest_upgrade.get("quality") or {}).get("tier") if closest_upgrade else None,
        },
        "main_blocker": main_blocker,
        "main_blocker_bilingual": main_blocker,
        "next_action": next_action,
        "next_action_bilingual": next_action,
        "research_context_only": brief_stale or data_stale,
        "brief_context": brief_ctx,
        "opportunity_states": {
            "quality": quality_qualified,
            "promising": len(promising_rows),
            "weak": len(weak_rows),
            "none_strong": quality_qualified == 0,
            "best_monitor": best_monitor.get("ticker") if best_monitor else None,
            "near_quality": near_quality,
            "do_not_chase": do_not_chase,
        },
        "authority_note": (
            "Quality ≠ deploy authority · Decision Engine sets deploy_open only"
        ),
    }


def tags_for_playbook_row(
    row: Dict[str, Any],
    *,
    data_stale: bool = False,
    brief_stale: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    """Hook-compatible with enrich_opportunity_row tag pattern."""
    q = classify_opportunity_quality(row, data_stale=data_stale, brief_stale=brief_stale)
    return {
        "quality": q,
        "quality_decomposition": build_quality_decomposition(row),
    }


def _tier_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        tier = str((row.get("quality") or {}).get("tier") or "—").upper()
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def _authority_label(row: Dict[str, Any]) -> str:
    ps = str(row.get("pilot_state") or "").upper()
    if row.get("execution_ready"):
        return "DEPLOY ELIGIBLE · Decision Engine"
    if ps == "MONITOR_ONLY" or ps == "PILOT_RESEARCH_ONLY":
        return "MONITOR ONLY"
    if ps == "BLOCKED":
        return "BLOCKED"
    return "MONITOR ONLY"


def attach_opportunity_verdict_to_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich board payload with verdict, tier counts, and per-row quality/authority labels."""
    out = dict(payload)
    verdict = out.get("opportunity_verdict") or build_opportunity_verdict(out)
    rows = list(
        out.get("top_ranked")
        or out.get("top_5")
        or out.get("opportunities")
        or []
    )
    near = list(out.get("near_miss") or out.get("near_miss_rows") or [])
    all_rows = rows + near
    verdict = dict(verdict)
    verdict["tier_counts"] = _tier_counts(all_rows)
    out["opportunity_verdict"] = verdict

    for key in ("top_ranked", "top_5", "opportunities", "near_miss", "near_miss_rows"):
        bucket = out.get(key)
        if not isinstance(bucket, list):
            continue
        enriched: List[Dict[str, Any]] = []
        for row in bucket:
            item = dict(row)
            q = item.get("quality") or {}
            item["quality_tier"] = q.get("tier")
            item["authority_label"] = _authority_label(item)
            enriched.append(item)
        out[key] = enriched
    return out
