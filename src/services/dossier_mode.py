"""Dossier authority modes — gates UI between structure review and live trade plan."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

DossierMode = Literal["usable", "structure_review_only", "loading", "unavailable"]

CONFIRM_ONLY_LABELS = frozenset(
    {"CONFIRM ONLY", "RESEARCH ONLY", "REFERENCE ONLY", "WATCH ONLY", "PASS"}
)

DOSSIER_CONFIRM_ONLY_STRIP = (
    "Confirm-only · 僅結構確認：無入場價、無止損、無倉位 · no sizing · no handoff"
)

PAPER_DRAFT_DISABLED_COPY = (
    "Paper draft disabled · 紙上模擬已關閉 — 需 live Dossier + Playbook 確認後才可模擬"
)

MONITOR_RULE_BUTTON = "Create monitor rule · 建立監察規則"
MONITOR_RULE_HINT = "Alert only · 僅提醒 — 不定倉、不交接券商 · no sizing · no handoff"

LAGGED_CONTEXT_COLLAPSED_NOTE = (
    "Lagged / illustrative context · 滯後參考，不用於結構確認 · not used for confirmation"
)

STRUCTURE_SNAPSHOT_TITLE = "Structure snapshot · 結構快照"

_STRUCTURE_LABELS = {
    "entry": ("Reference level · 參考價位", "Entry zone"),
    "stop": ("Risk reference · 風險參考", "Stop"),
    "target": ("Upside references · 上行參考", "T1 / T2"),
    "rr": ("R:R", "R:R"),
    "size": ("Sizing", "Size @1%"),
    "invalidation": ("Invalidation", "Invalidation"),
    "note": ("Note", "Note"),
    "source": ("Source", "Source"),
    "freshness": ("Freshness", "Freshness"),
    "use": ("Use", "Use: structure review only"),
}

_RECOVERY_ALLOWED = [
    "retry",
    "load core",
    "open Playbook",
]

_RECOVERY_BLOCKED = [
    "no trade plan",
    "no paper draft",
    "no sizing",
    "no handoff",
]


def resolve_dossier_mode(
    *,
    unified_label: str = "",
    load_phase: str = "full",
    partial: bool = False,
    failed_fetch: bool = False,
    instant_degraded: bool = False,
    brief_backed: bool = False,
    research_only: bool = False,
    has_quote: bool = False,
    pending_calibration: bool = False,
    rr_unavailable: bool = False,
    module_errors: Optional[Dict[str, str]] = None,
) -> DossierMode:
    """Resolve dossier UI authority mode from fetch state and decision label."""
    label = str(unified_label or "").upper()
    module_errors = module_errors or {}

    if failed_fetch and not has_quote:
        return "unavailable"

    if load_phase == "core":
        return "loading"

    confirm_only = (
        label in CONFIRM_ONLY_LABELS
        or research_only
        or instant_degraded
        or brief_backed
        or pending_calibration
        or rr_unavailable
        or not has_quote
    )

    if not has_quote and (instant_degraded or not brief_backed or partial):
        return "unavailable"

    if confirm_only:
        return "structure_review_only"

    if partial or bool(module_errors):
        return "loading"

    return "usable"


def is_structure_review_only(mode: str) -> bool:
    return str(mode or "") == "structure_review_only"


def is_recovery_mode(mode: str) -> bool:
    return str(mode or "") in ("structure_review_only", "loading", "unavailable")


def is_usable_mode(mode: str) -> bool:
    return str(mode or "") == "usable"


def structure_level_label(field: str, *, mode: str = "usable") -> str:
    """Bilingual column label for structure snapshot vs live trade plan."""
    review = is_structure_review_only(mode) or not is_usable_mode(mode)
    pair = _STRUCTURE_LABELS.get(field, (field, field))
    return pair[0] if review else pair[1]


def structure_snapshot_use_line(*, mode: str = "structure_review_only") -> str:
    if is_structure_review_only(mode):
        return "Use: structure review only"
    return ""


def dossier_missing_data_items(
    *,
    has_quote: bool = False,
    has_technicals: bool = False,
    has_peers: bool = False,
    has_options: bool = False,
    has_catalysts: bool = False,
    has_risk: bool = False,
    playbook_deploy_allowed: bool = False,
    mode: str = "structure_review_only",
) -> List[str]:
    """Missing-data checklist for confirm-only dossier."""
    if not is_recovery_mode(mode):
        return []
    missing: List[str] = []
    if not has_quote:
        missing.append("quote")
    if not has_technicals:
        missing.append("technicals")
    if not has_peers:
        missing.append("peers")
    if not has_options:
        missing.append("options")
    if not has_catalysts:
        missing.append("catalysts")
    if not has_risk:
        missing.append("risk")
    if not playbook_deploy_allowed and mode == "structure_review_only":
        missing.append("Playbook deploy permission")
    return missing


def dossier_evidence_confidence(
    *,
    mode: str = "structure_review_only",
    evidence_quality: str = "",
    calibration: str = "",
    reason: str = "",
) -> Dict[str, str]:
    """Evidence confidence block for confirm-only dossier."""
    review = is_recovery_mode(mode)
    eq = str(evidence_quality or "").strip() or ("Low" if review else "—")
    cal = str(calibration or "").strip() or ("Pending" if review else "—")
    use_allowed = "structure review only" if review else "live confirmation"
    default_reason = (
        "Live dossier incomplete — structure references only, no deploy authority."
        if review
        else ""
    )
    return {
        "evidence_quality": eq,
        "calibration": cal,
        "use_allowed": use_allowed,
        "reason": str(reason or default_reason).strip(),
    }


def dossier_evidence_status_panel(
    *,
    mode: str,
    has_quote: bool = False,
    has_narrative: bool = False,
    evidence_quality: str = "",
    calibration: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    """Evidence status panel — replaces Bull/Bear when modules missing."""
    show = is_recovery_mode(mode) or not has_quote or not has_narrative
    ec = dossier_evidence_confidence(
        mode=mode,
        evidence_quality=evidence_quality,
        calibration=calibration,
        reason=reason,
    )
    headline = "Structure unavailable" if not has_quote else "Evidence incomplete"
    if mode == "loading":
        headline = "Structure loading"
    return {
        "show": show,
        "headline": headline,
        "evidence_quality": ec["evidence_quality"],
        "calibration": ec["calibration"],
        "use_allowed": ec["use_allowed"],
        "reason": ec["reason"] or "Live modules missing — no deploy authority",
        "modules_missing": not has_narrative or is_recovery_mode(mode),
    }


def dossier_allowed_actions(mode: str) -> List[str]:
    if is_recovery_mode(mode):
        return list(_RECOVERY_ALLOWED)
    if mode == "usable":
        return ["Trade plan", "Monitor rule", "Paper draft (when gated)", "Open Playbook"]
    return ["Retry fetch"]


def dossier_blocked_actions(mode: str) -> List[str]:
    if is_recovery_mode(mode):
        return list(_RECOVERY_BLOCKED)
    return []


def _operator_why_line(
    *,
    mode: str,
    has_quote: bool,
    brief_backed: bool,
    instant_degraded: bool,
    reason: str = "",
) -> str:
    if reason:
        return reason
    parts: List[str] = []
    if not has_quote:
        parts.append("live quote unavailable")
    if not brief_backed:
        parts.append("no brief row")
    if mode == "loading":
        parts.append("backend loading")
    if instant_degraded:
        parts.append("instant-degraded")
    return " · ".join(parts) if parts else "Live dossier incomplete"


def build_dossier_operator_block(
    *,
    mode: str,
    ticker: str = "",
    unified_label: str = "",
    has_quote: bool = False,
    brief_backed: bool = False,
    instant_degraded: bool = False,
    missing_data: Optional[List[str]] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """Recovery-first operator block for degraded dossier surfaces."""
    sym = str(ticker or "").upper()
    label = str(unified_label or "").strip()

    if mode == "unavailable":
        now = f"{sym} · Structure unavailable" if sym else "Structure unavailable"
    elif mode == "loading":
        now = f"{sym} · Loading" if sym else "Loading dossier"
    elif mode == "structure_review_only":
        now = f"{sym} · {label or 'CONFIRM ONLY'}" if sym else (label or "CONFIRM ONLY")
    else:
        now = f"{sym} · {label}" if sym and label else (sym or label or "Dossier")

    missing = missing_data or []
    return {
        "now": now,
        "why": _operator_why_line(
            mode=mode,
            has_quote=has_quote,
            brief_backed=brief_backed,
            instant_degraded=instant_degraded,
            reason=reason,
        ),
        "allowed": dossier_allowed_actions(mode),
        "blocked": dossier_blocked_actions(mode),
        "missing_data": missing,
        "next": "retry live fetch" if is_recovery_mode(mode) else "review structure and open Playbook when deploy-qualified",
    }


def dossier_ui_authority_flags(
    *,
    mode: str,
    playbook_deploy_allowed: bool = False,
    broker_online: bool = False,
) -> Dict[str, bool]:
    """UI hide flags for trade-plan authority leakage prevention."""
    usable = is_usable_mode(mode)
    return {
        "hide_trade_plan": not usable,
        "hide_paper_draft": not usable or not playbook_deploy_allowed or not broker_online,
        "hide_sizing": not usable,
        "show_evidence_status": is_recovery_mode(mode),
    }


def paper_draft_visible(
    *,
    mode: str,
    playbook_watch_plus: bool = False,
    deploy_blocked: bool = True,
    broker_online: bool = False,
) -> bool:
    """Paper Order Draft only when fully usable and execution gates pass."""
    return (
        is_usable_mode(mode)
        and playbook_watch_plus
        and not deploy_blocked
        and broker_online
    )


def trade_plan_visible(
    *,
    mode: str,
    deploy_blocked: bool = True,
    broker_online: bool = False,
    playbook_watch_plus: bool = False,
) -> bool:
    """Trade plan section only when usable and deploy authority allows."""
    return is_usable_mode(mode) and playbook_watch_plus and not deploy_blocked and broker_online


def build_structure_snapshot_rows(
    *,
    mode: str,
    entry_zone: Optional[Any] = None,
    stop: Optional[Any] = None,
    target_1r: Optional[Any] = None,
    target_2r: Optional[Any] = None,
    rr_display: Optional[Any] = None,
    invalidation: str = "",
    note: str = "",
    source: str = "",
    freshness: str = "",
    live_validated: bool = False,
) -> List[Dict[str, str]]:
    """Structure snapshot rows — hides R:R unless live validated."""
    if mode in ("unavailable", "loading"):
        return []

    def _fmt_price(v: Any) -> str:
        if v is None or v == "":
            return "—"
        return f"${v}"

    def _fmt_entry(ez: Any) -> str:
        if ez and len(ez) >= 2:
            return f"${ez[0]}–${ez[1]}"
        return "—"

    rows: List[Dict[str, str]] = [
        {
            "label": structure_level_label("entry", mode=mode),
            "value": _fmt_entry(entry_zone),
        },
        {
            "label": structure_level_label("stop", mode=mode),
            "value": _fmt_price(stop),
        },
        {
            "label": structure_level_label("target", mode=mode),
            "value": (
                f"${target_1r} / ${target_2r}"
                if target_1r and target_2r
                else "—"
            ),
        },
    ]

    if is_usable_mode(mode) or live_validated:
        rows.append(
            {
                "label": structure_level_label("rr", mode=mode),
                "value": str(rr_display or "—"),
            }
        )

    if invalidation:
        rows.append(
            {
                "label": structure_level_label("invalidation", mode=mode),
                "value": str(invalidation),
            }
        )
    if note:
        rows.append({"label": structure_level_label("note", mode=mode), "value": note})

    if is_structure_review_only(mode):
        if source:
            rows.append({"label": structure_level_label("source", mode=mode), "value": source})
        if freshness:
            rows.append(
                {"label": structure_level_label("freshness", mode=mode), "value": freshness}
            )
        rows.append(
            {
                "label": structure_level_label("use", mode=mode),
                "value": structure_snapshot_use_line(mode=mode),
            }
        )

    return rows


def build_dossier_mode_block(
    *,
    mode: str,
    unified_label: str = "",
    instant_degraded: bool = False,
    brief_backed: bool = False,
    has_quote: bool = False,
    has_technicals: bool = False,
    has_peers: bool = False,
    has_options: bool = False,
    has_catalysts: bool = False,
    has_risk: bool = False,
    playbook_deploy_allowed: bool = False,
    evidence_quality: str = "",
    calibration: str = "",
    reason: str = "",
    source: str = "",
    freshness: str = "",
    ticker: str = "",
    has_narrative: bool = False,
    broker_online: bool = False,
) -> Dict[str, Any]:
    """Payload block attached to stock-intel for dossier UI parity."""
    missing = dossier_missing_data_items(
        has_quote=has_quote,
        has_technicals=has_technicals,
        has_peers=has_peers,
        has_options=has_options,
        has_catalysts=has_catalysts,
        has_risk=has_risk,
        playbook_deploy_allowed=playbook_deploy_allowed,
        mode=mode,
    )
    ui_flags = dossier_ui_authority_flags(
        mode=mode,
        playbook_deploy_allowed=playbook_deploy_allowed,
        broker_online=broker_online,
    )
    operator_block = build_dossier_operator_block(
        mode=mode,
        ticker=ticker,
        unified_label=unified_label,
        has_quote=has_quote,
        brief_backed=brief_backed,
        instant_degraded=instant_degraded,
        missing_data=missing,
        reason=reason,
    )
    evidence_status = dossier_evidence_status_panel(
        mode=mode,
        has_quote=has_quote,
        has_narrative=has_narrative,
        evidence_quality=evidence_quality,
        calibration=calibration,
        reason=reason,
    )
    return {
        "mode": mode,
        "confirm_only_strip": DOSSIER_CONFIRM_ONLY_STRIP if is_structure_review_only(mode) else "",
        "structure_snapshot_title": STRUCTURE_SNAPSHOT_TITLE,
        "allowed": dossier_allowed_actions(mode),
        "blocked": dossier_blocked_actions(mode),
        "missing_data": missing,
        "evidence_confidence": dossier_evidence_confidence(
            mode=mode,
            evidence_quality=evidence_quality,
            calibration=calibration,
            reason=reason,
        ),
        "evidence_status": evidence_status,
        "dossier_operator_block": operator_block,
        "hide_trade_plan": ui_flags["hide_trade_plan"],
        "hide_paper_draft": ui_flags["hide_paper_draft"],
        "hide_sizing": ui_flags["hide_sizing"],
        "paper_draft_disabled_copy": PAPER_DRAFT_DISABLED_COPY,
        "monitor_rule_button": MONITOR_RULE_BUTTON,
        "monitor_rule_hint": MONITOR_RULE_HINT,
        "lagged_context_note": LAGGED_CONTEXT_COLLAPSED_NOTE,
        "source": source,
        "freshness": freshness,
        "unified_label": unified_label,
        "instant_degraded": instant_degraded,
        "brief_backed": brief_backed,
    }
