"""
Discovery research funnel — sanitize scanner dump into PM-reviewable shortlist.

Research-only surfaces must never show deploy/actionable language.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.engines.scanner_matrix import (
    DISCOVERY_HIGH_PRIORITY_CAP,
    DISCOVERY_SHORTLIST_CAP,
    ScannerMatrix,
)
from src.services.score_sanity import sanitize_score_display

_BROAD_CLUSTER_THRESHOLD = 100
_SHORTLIST_MAX = DISCOVERY_SHORTLIST_CAP
_PRIORITY_MAX = DISCOVERY_HIGH_PRIORITY_CAP

_ACTION_BANNED_RE = re.compile(
    r"\b(actionable|trade|entry|size|deploy|pilot|handoff|sizing)\b",
    re.IGNORECASE,
)
_STATUS_BANNED = frozenset({"actionable", "trade", "confirmed", "deploy"})

_RESEARCH_REPLACEMENTS = (
    (re.compile(r"\bactionable\b", re.I), "research hit"),
    (re.compile(r"\btrade\b", re.I), "research review"),
    (re.compile(r"\bentry\b", re.I), "review"),
    (re.compile(r"\bsize\b", re.I), "monitor"),
    (re.compile(r"\bdeploy\b", re.I), "Playbook review"),
    (re.compile(r"\bpilot\b", re.I), "monitor"),
)


def _discovery_scope_title(state: str, *, brief_age_days: Optional[int] = None) -> str:
    """Human title for scoped freshness — never unscoped live/stale."""
    s = str(state or "unknown").lower()
    if s == "expired" or (brief_age_days is not None and int(brief_age_days) > 2):
        age = int(brief_age_days or 0)
        return f"Expired {age}d" if age > 0 else "Expired"
    if s in ("offline", "unavailable"):
        return "Offline"
    if s == "blocked":
        return "Blocked"
    if s == "wait":
        return "WAIT"
    if s == "fresh":
        return "Fresh"
    if s == "stale":
        return "Stale"
    if s == "live":
        return "Live"
    if s == "warming":
        return "Warming"
    if s == "degraded":
        return "Degraded"
    if s == "ready":
        return "Ready"
    if s == "partial":
        return "Partial"
    return s.replace("_", " ").title() if s else "Unknown"


def _discovery_scanner_run_label(diagnostics: Optional[Dict[str, Any]]) -> str:
    diag = diagnostics or {}
    freshness = str(diag.get("data_freshness") or diag.get("scanner_run_freshness") or "unknown").lower()
    hub = str(diag.get("hub_status") or "").lower()
    if hub in ("warming", "degraded"):
        return f"Scanner run: {_discovery_scope_title(hub)}"
    return f"Scanner run: {_discovery_scope_title(freshness)}"


def build_discovery_why(truth: Optional[Dict[str, Any]]) -> str:
    """Scoped blockers — Board WAIT · broker offline · brief expired 27d."""
    t = truth or {}
    parts: List[str] = []
    board_gate = str(t.get("board_gate") or "").lower()
    regime = str(t.get("regime_state") or t.get("effective_state") or "").upper()
    if board_gate == "wait" or regime == "WAIT":
        parts.append("Board WAIT")
    elif board_gate:
        parts.append(f"Board {board_gate.upper()}")
    elif regime and regime not in ("ACTIVE", "TRADE", "SELECTIVE"):
        parts.append(f"Board {regime}")

    broker = str(t.get("broker_freshness") or "").lower()
    if broker in ("offline", "blocked"):
        parts.append("broker offline")

    brief_age = t.get("brief_age_days")
    brief = str(t.get("brief_freshness") or "").lower()
    if brief == "expired" or t.get("brief_expired") or (
        brief_age is not None and int(brief_age) > 2
    ):
        age = int(brief_age or 0)
        parts.append(f"brief expired {age}d" if age > 0 else "brief expired")

    market = str(t.get("market_data_freshness") or "").lower()
    if market == "stale" and "Board" not in " ".join(parts):
        parts.append("market data stale")

    if not t.get("deploy_authority"):
        if not any("deploy" in p.lower() for p in parts):
            parts.append("deploy authority blocked")

    return " · ".join(parts) if parts else "scan evidence only — not deploy authority"


def build_discovery_status_line(
    truth: Optional[Dict[str, Any]] = None,
    *,
    scanner_diagnostics: Optional[Dict[str, Any]] = None,
) -> str:
    """Scoped STATUS: Scanner run Live · Board Blocked · Brief Expired 27d · Broker Offline."""
    t = truth or {}
    parts: List[str] = [_discovery_scanner_run_label(scanner_diagnostics)]

    board = str(t.get("ranked_board_freshness") or "").lower()
    board_gate = str(t.get("board_gate") or "").lower()
    if board_gate == "wait":
        parts.append("Board WAIT")
    elif board in ("stale", "fallback", "unavailable") or board_gate in ("closed", "blocked"):
        parts.append(f"Board {_discovery_scope_title(board or board_gate or 'blocked')}")
    elif board == "fresh":
        parts.append("Board Fresh")

    brief_age = t.get("brief_age_days")
    brief = str(t.get("brief_freshness") or "").lower()
    if brief == "expired" or t.get("brief_expired") or (
        brief_age is not None and int(brief_age) > 2
    ):
        parts.append(f"Brief {_discovery_scope_title('expired', brief_age_days=brief_age)}")
    elif brief and brief != "fresh":
        parts.append(f"Brief {_discovery_scope_title(brief, brief_age_days=brief_age)}")

    broker = str(t.get("broker_freshness") or "").lower()
    if broker:
        parts.append(f"Broker {_discovery_scope_title(broker)}")

    if not t.get("deploy_authority"):
        parts.append("Deploy authority: None")

    return " · ".join(parts)


def build_discovery_panel(
    funnel: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
    *,
    scanner_diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Canonical Discovery operator panel — scoped freshness, zero-hit safe copy."""
    t = truth or {}
    mode = resolve_discovery_mode(t)
    counts = funnel.get("funnel_counts") or {}
    strict = int(funnel.get("strict_passed_count") or counts.get("regime") or 0)
    shortlist_n = int(counts.get("shortlist") or len(funnel.get("review_shortlist") or []))
    deploy_n = len(funnel.get("deploy_candidates") or []) if mode == "usable" else 0
    raw_n = int(counts.get("raw") or 0)
    hits_n = raw_n

    now = "Research-only · deploy blocked" if mode == "research_only" else "Research funnel active"
    why = build_discovery_why(t)
    funnel_line = (
        f"Raw {raw_n} / hits {hits_n} / strict {strict} / "
        f"shortlist {shortlist_n} / deploy {deploy_n}"
    )
    status_line = build_discovery_status_line(t, scanner_diagnostics=scanner_diagnostics)

    if strict == 0:
        headline = "No validated research candidates"
        subtitle = (
            "Research funnel only. Names go to Playbook review only after strict filters pass."
        )
        best_action = "No new research candidates. Refresh Dashboard + Playbook."
    else:
        headline = (
            f"{shortlist_n} validated research candidates · "
            f"{mode.replace('_', ' ')}"
        )
        subtitle = "Research funnel only. Names go to Playbook review only after strict filters pass."
        best_action = (
            "Send to Playbook Review"
            if mode == "research_only"
            else "Review shortlist in Playbook"
        )

    brief_age = t.get("brief_age_days")
    brief_expired = (
        t.get("brief_expired")
        or str(t.get("brief_freshness") or "").lower() == "expired"
        or (brief_age is not None and int(brief_age) > 2)
    )
    brief_note = ""
    if brief_expired:
        age = int(brief_age or 0)
        brief_note = (
            f"Brief expired {age}d — excluded from Discovery ranking context"
            if age > 0
            else "Brief expired — excluded from Discovery ranking context"
        )

    return {
        "mode": mode,
        "now": now,
        "why": why,
        "funnel_line": funnel_line,
        "status_line": status_line,
        "best_action": best_action,
        "headline": headline,
        "subtitle": subtitle,
        "brief_expired_note": brief_note,
        "deploy_authority_label": "None" if not t.get("deploy_authority") else "Open",
    }


def resolve_discovery_mode(truth: Optional[Dict[str, Any]]) -> str:
    """research_only when deploy blocked or authority suspended."""
    t = truth or {}
    if not t.get("deploy_authority", False):
        return "research_only"
    if t.get("allows_trade_labels") is False:
        return "research_only"
    if t.get("exec_blocked"):
        return "research_only"
    regime = str(t.get("regime_state") or t.get("effective_state") or "").upper()
    if regime in ("WAIT", "NO_TRADE"):
        return "research_only"
    authority = str(t.get("authority_level") or "").lower()
    if authority in ("research", "suspended"):
        return "research_only"
    return "usable"


def calibrate_discovery_score(score: Any) -> Dict[str, Any]:
    """Human label — hide negative or out-of-range raw scores."""
    sane = sanitize_score_display(score)
    if not sane.get("valid"):
        return {
            "label": "Signal quality: Low · Excluded",
            "display": "Signal quality: Low · Excluded",
            "raw_hidden": True,
            "excluded": True,
        }
    val = float(sane["score_raw"])
    if val >= 7.5:
        label = "Signal quality: High"
    elif val >= 6.0:
        label = "Signal quality: Medium"
    else:
        label = "Signal quality: Low"
    return {
        "label": label,
        "display": label,
        "raw_hidden": False,
        "excluded": False,
    }


def hide_uncalibrated_confidence(
    conf: Any,
    sample_size: Optional[int] = None,
) -> str:
    """No % confidence without calibration sample."""
    has_cal = sample_size is not None and int(sample_size) >= 30
    if not has_cal:
        return "Confidence: heuristic · Calibration: insufficient"
    try:
        val = float(conf)
    except (TypeError, ValueError):
        return "Confidence: heuristic · Calibration: insufficient"
    pct = round(val * 100) if val <= 1 else round(val)
    if pct <= 0:
        return "Confidence: heuristic · Calibration: insufficient"
    return f"Confidence: {pct}% · Calibration: sufficient"


def sanitize_discovery_action_labels(text: Any, mode: str) -> str:
    """Research mode — research hit, not actionable/trade/entry/size."""
    raw = str(text or "").strip()
    if not raw:
        return "research hit" if mode == "research_only" else "review"
    if mode != "research_only":
        return raw
    out = raw
    for pattern, repl in _RESEARCH_REPLACEMENTS:
        out = pattern.sub(repl, out)
    if _ACTION_BANNED_RE.search(out):
        out = "research hit — Playbook review path"
    return out


def _pattern_hit_count(hit: Dict[str, Any]) -> int:
    meta = hit.get("metadata") or {}
    if isinstance(meta, dict):
        cluster = meta.get("cluster_size") or meta.get("pattern_hit_count")
        if cluster is not None:
            try:
                return int(cluster)
            except (TypeError, ValueError):
                pass
    scanner = str(hit.get("scanner") or hit.get("signal_source") or "").lower()
    if scanner == "similar_pattern":
        dbg = hit.get("debug_total_hits")
        if dbg is not None:
            try:
                return int(dbg)
            except (TypeError, ValueError):
                pass
    return int(hit.get("pattern_hit_count") or hit.get("hit_count") or 0)


def classify_raw_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    """Broad cluster / exclusion / signal quality for one scanner hit."""
    scanner = str(hit.get("scanner") or hit.get("signal_source") or "").lower()
    pattern_count = _pattern_hit_count(hit)
    broad = pattern_count > _BROAD_CLUSTER_THRESHOLD or bool(hit.get("broad_cluster"))
    if scanner == "similar_pattern" and pattern_count > _BROAD_CLUSTER_THRESHOLD:
        broad = True

    score_meta = hit.get("metadata") or {}
    sample_size = (
        hit.get("calibration_n")
        or score_meta.get("calibration_n")
        if isinstance(score_meta, dict)
        else None
    )
    score_val = hit.get("strength") if hit.get("strength") is not None else hit.get("score")
    calibrated = calibrate_discovery_score(score_val)
    excluded = bool(calibrated.get("excluded")) or bool(hit.get("is_warning")) or broad

    reason_parts: List[str] = []
    if broad:
        reason_parts.append(f"broad cluster ({pattern_count or '>'+str(_BROAD_CLUSTER_THRESHOLD)} hits)")
    if calibrated.get("excluded"):
        reason_parts.append("invalid score")
    if hit.get("is_warning"):
        reason_parts.append("risk flag")
    if not reason_parts:
        reason_parts.append("scanner match")

    return {
        "broad_cluster": broad,
        "excluded": excluded,
        "signal_quality": calibrated.get("label", "Signal quality: Low"),
        "reason": " · ".join(reason_parts),
        "confidence_display": hide_uncalibrated_confidence(hit.get("confidence"), sample_size),
        "score_display": calibrated.get("display"),
        "raw_hidden": calibrated.get("raw_hidden", False),
    }


def collapse_broad_clusters(
    hits: List[Dict[str, Any]],
    *,
    threshold: int = _BROAD_CLUSTER_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Mark similar_pattern clusters above threshold as broad/excluded."""
    out: List[Dict[str, Any]] = []
    scanner_counts: Dict[str, int] = {}
    for hit in hits or []:
        scanner = str(hit.get("scanner") or hit.get("signal_source") or "unknown").lower()
        scanner_counts[scanner] = scanner_counts.get(scanner, 0) + 1

    for hit in hits or []:
        row = dict(hit)
        scanner = str(row.get("scanner") or row.get("signal_source") or "").lower()
        pattern_count = _pattern_hit_count(row) or scanner_counts.get(scanner, 0)
        if pattern_count > threshold or (
            scanner == "similar_pattern" and scanner_counts.get(scanner, 0) > threshold
        ):
            row["broad_cluster"] = True
            row["excluded"] = True
            row["collapsed"] = True
            row["collapse_reason"] = f"broad cluster — {pattern_count} hits"
        classification = classify_raw_hit(row)
        row.update(classification)
        out.append(row)
    return out


def _sort_key(hit: Dict[str, Any]) -> tuple:
    score_val = hit.get("strength") if hit.get("strength") is not None else hit.get("score")
    try:
        score = float(score_val or 0)
    except (TypeError, ValueError):
        score = -999.0
    overlap = int(hit.get("overlap") or 0)
    warning = 1 if hit.get("is_warning") else 0
    excluded = 1 if hit.get("excluded") else 0
    broad = 1 if hit.get("broad_cluster") else 0
    return (-overlap, -score, warning, excluded, broad)


def _sanitize_hit_row(hit: Dict[str, Any], mode: str) -> Dict[str, Any]:
    row = dict(hit)
    classification = classify_raw_hit(row)
    row.update(classification)
    row["status"] = sanitize_discovery_action_labels(
        row.get("status") or "monitor",
        mode,
    )
    row["next_action"] = sanitize_discovery_action_labels(
        row.get("next_action") or "Review in Playbook",
        mode,
    )
    row["action"] = sanitize_discovery_action_labels(
        row.get("action") or "WATCH",
        mode,
    )
    if mode == "research_only":
        status_lower = str(row.get("status") or "").lower()
        if status_lower in _STATUS_BANNED:
            row["status"] = "research hit"
        action_upper = str(row.get("action") or "").upper()
        if action_upper in ("TRADE", "BUY", "DEPLOY", "PILOT"):
            row["action"] = "RESEARCH"
    row["monitor_rule_enabled"] = bool(
        not row.get("excluded")
        and not row.get("broad_cluster")
        and mode == "research_only"
        and not row.get("is_warning")
    )
    return row


def build_research_shortlist(
    hits: List[Dict[str, Any]],
    *,
    max_items: int = _SHORTLIST_MAX,
) -> List[Dict[str, Any]]:
    """Top validated names only — excludes broad clusters and invalid scores."""
    eligible = [
        h
        for h in hits or []
        if not h.get("excluded") and not h.get("broad_cluster") and not h.get("is_warning")
    ]
    eligible.sort(key=_sort_key)
    return eligible[: max(0, int(max_items))]


def build_discovery_verdict(
    funnel: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shortlist count, best family, next action, default sentence."""
    t = truth or {}
    mode = resolve_discovery_mode(t)
    shortlist = funnel.get("review_shortlist") or []
    strict_passed = int(funnel.get("strict_passed_count") or 0)
    groups = funnel.get("signal_groups") or {}
    best_family: Optional[str] = None
    best_count = 0
    for name, meta in groups.items():
        count = int((meta or {}).get("validated_count") or (meta or {}).get("count") or 0)
        if count > best_count:
            best_count = count
            best_family = name
    panel = build_discovery_panel(
        {
            "funnel_counts": funnel.get("funnel_counts") or {},
            "strict_passed_count": strict_passed,
            "review_shortlist": shortlist,
            "deploy_candidates": funnel.get("deploy_candidates") or [],
        },
        t,
    )
    if strict_passed == 0:
        default_sentence = panel["headline"]
        next_action = panel["best_action"]
    else:
        default_sentence = (
            f"{len(shortlist)} validated research candidates · "
            f"best family {best_family or '—'} · {mode.replace('_', ' ')}"
        )
        next_action = panel["best_action"]
    return {
        "shortlist_count": len(shortlist),
        "strict_passed_count": strict_passed,
        "best_family": best_family,
        "best_family_count": best_count,
        "next_action": next_action,
        "default_sentence": default_sentence,
        "subtitle": panel["subtitle"],
        "status_line": panel["status_line"],
        "why": panel["why"],
        "now": panel["now"],
        "funnel_line": panel["funnel_line"],
        "best_action": panel["best_action"],
        "brief_expired_note": panel["brief_expired_note"],
        "mode": mode,
        "hide_raw_hits": strict_passed == 0,
    }


def build_discovery_funnel(
    raw_hits: List[Dict[str, Any]],
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Research funnel stages from raw scanner hits.

    strictPassedCount === 0 → hide_raw_hits default.
    """
    mode = resolve_discovery_mode(truth)
    collapsed = collapse_broad_clusters(list(raw_hits or []))
    sanitized = [_sanitize_hit_row(h, mode) for h in collapsed]

    passed_liquidity = [
        h for h in sanitized if str(h.get("scanner") or "").lower() != "low_liquidity"
    ]
    passed_data_quality = [
        h for h in passed_liquidity if not h.get("excluded") and not h.get("raw_hidden")
    ]
    passed_structure = [h for h in passed_data_quality if not h.get("broad_cluster")]
    passed_regime = [h for h in passed_structure if not h.get("is_warning")]

    strict_passed_count = len(passed_regime)
    review_shortlist = build_research_shortlist(passed_regime, max_items=_SHORTLIST_MAX)
    deploy_candidates: List[Dict[str, Any]] = []
    if mode == "usable":
        deploy_candidates = review_shortlist[:_PRIORITY_MAX]

    signal_groups: Dict[str, Dict[str, Any]] = {}
    for hit in sanitized:
        scanner = str(hit.get("scanner") or hit.get("signal_source") or "unknown")
        bucket = signal_groups.setdefault(
            scanner,
            {"count": 0, "validated_count": 0, "broad_cluster": False, "collapsed": False},
        )
        bucket["count"] += 1
        if hit.get("broad_cluster"):
            bucket["broad_cluster"] = True
            bucket["collapsed"] = True
        if not hit.get("excluded") and not hit.get("broad_cluster"):
            bucket["validated_count"] += 1

    verdict = build_discovery_verdict(
        {
            "review_shortlist": review_shortlist,
            "strict_passed_count": strict_passed_count,
            "signal_groups": signal_groups,
        },
        truth,
    )

    return {
        "mode": mode,
        "raw_hits": sanitized,
        "signal_groups": signal_groups,
        "passed_liquidity": passed_liquidity,
        "passed_data_quality": passed_data_quality,
        "passed_structure": passed_structure,
        "passed_regime": passed_regime,
        "review_shortlist": review_shortlist,
        "deploy_candidates": deploy_candidates,
        "strict_passed_count": strict_passed_count,
        "hide_raw_hits": strict_passed_count == 0,
        "empty_message": "No validated research candidates",
        "verdict": verdict,
        "funnel_counts": {
            "raw": len(sanitized),
            "liquidity": len(passed_liquidity),
            "data_quality": len(passed_data_quality),
            "structure": len(passed_structure),
            "regime": len(passed_regime),
            "shortlist": len(review_shortlist),
        },
        "top_priority": review_shortlist[:_PRIORITY_MAX],
    }


def attach_discovery_operator_view(
    payload: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Collect hits from scanner hub payload and attach discovery_operator_view."""
    raw_hits: List[Dict[str, Any]] = []
    grouped = payload.get("scanners") or {}
    for _cat, scanners in grouped.items():
        if not isinstance(scanners, dict):
            continue
        for scan_name, bucket in scanners.items():
            for hit in ScannerMatrix.hits_from_bucket(bucket):
                row = dict(hit)
                row.setdefault("scanner", scan_name)
                row.setdefault("signal_source", scan_name)
                if bucket.get("debug_total_hits"):
                    row["debug_total_hits"] = bucket["debug_total_hits"]
                raw_hits.append(row)

    for row in payload.get("merged_top_names") or []:
        raw_hits.append(
            {
                **row,
                "scanner": "merged_rank",
                "signal_source": "merged_rank",
                "overlap": row.get("overlap"),
            }
        )

    funnel = build_discovery_funnel(raw_hits, truth)
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    panel = build_discovery_panel(funnel, truth, scanner_diagnostics=diagnostics)
    out = dict(payload)
    out["discovery_operator_view"] = {**funnel, "panel": panel}
    out["discovery_verdict"] = {
        **(payload.get("discovery_verdict") or {}),
        **(funnel.get("verdict") or {}),
        **panel,
    }
    return out
