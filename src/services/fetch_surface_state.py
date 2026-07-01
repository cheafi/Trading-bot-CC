"""
Shared fetch / authority degraded states for CC surfaces.

Each state maps to standard badge, title, explanation, and next_action copy
so every tab renders consistent degraded UX.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

STATE_LOADING = "loading"
STATE_FAILED_FETCH = "failed_fetch"
STATE_STALE = "stale"
STATE_FALLBACK = "fallback"
STATE_PARTIAL = "partial"
STATE_PROBE_ONLY = "probe_only"
STATE_RUNTIME_UNKNOWN = "runtime_unknown"
STATE_RESEARCH_ONLY = "research_only"
STATE_MOCK_ONLY = "mock_only"
STATE_NO_DATA = "no_data"
STATE_NOT_AUTHORITATIVE = "not_authoritative"
STATE_EXECUTION_BLOCKED = "execution_blocked"
STATE_OK = "ok"
STATE_FAILED_FETCH_FALLBACK = "failed_fetch_fallback"

ALL_STATES = (
    STATE_LOADING,
    STATE_FAILED_FETCH,
    STATE_STALE,
    STATE_FALLBACK,
    STATE_PARTIAL,
    STATE_PROBE_ONLY,
    STATE_RUNTIME_UNKNOWN,
    STATE_RESEARCH_ONLY,
    STATE_MOCK_ONLY,
    STATE_NO_DATA,
    STATE_NOT_AUTHORITATIVE,
    STATE_EXECUTION_BLOCKED,
    STATE_OK,
)

_STATE_COPY: Dict[str, Dict[str, str]] = {
    STATE_LOADING: {
        "badge": "LOADING",
        "title": "Fetching surface data",
        "explanation": "Live data is still loading — do not treat cached copy as deploy authority.",
        "next_action": "Wait for fetch to complete or refresh the tab.",
    },
    STATE_FAILED_FETCH: {
        "badge": "FETCH FAILED",
        "title": "Could not load surface",
        "explanation": "Network or server error prevented a fresh read.",
        "next_action": "Retry fetch; if persistent, use Ops diagnostics.",
    },
    STATE_STALE: {
        "badge": "STALE",
        "title": "Stale data",
        "explanation": "Last successful fetch is old — rankings and posture may not reflect current market.",
        "next_action": "Refresh this surface before acting on displayed copy.",
    },
    STATE_FALLBACK: {
        "badge": "FALLBACK",
        "title": "Fallback board",
        "explanation": "Live scanner unavailable — showing brief or snapshot fallback, not execution-grade board.",
        "next_action": "Open Dashboard when live API recovers; treat names as monitor-only.",
    },
    STATE_PARTIAL: {
        "badge": "PARTIAL",
        "title": "Partial payload",
        "explanation": "Some modules failed — surface shows incomplete evidence.",
        "next_action": "Check Ops → Data Providers before sizing.",
    },
    STATE_PROBE_ONLY: {
        "badge": "PROBE ONLY",
        "title": "Connectivity probe",
        "explanation": "Ops probe result — confirms wiring, not investable signal.",
        "next_action": "Resolve provider health before trusting downstream surfaces.",
    },
    STATE_RUNTIME_UNKNOWN: {
        "badge": "RUNTIME UNKNOWN",
        "title": "Runtime state unclear",
        "explanation": "Engine or backend status could not be confirmed.",
        "next_action": "Open Ops and confirm engine + provider health.",
    },
    STATE_RESEARCH_ONLY: {
        "badge": "RESEARCH ONLY",
        "title": "Research context",
        "explanation": "This surface informs — it does not authorize deploy by itself.",
        "next_action": "Cross-check Playbook or Dashboard before any capital action.",
    },
    STATE_MOCK_ONLY: {
        "badge": "MOCK ONLY",
        "title": "Illustrative data",
        "explanation": "Synthetic / mock rows — not validated market events.",
        "next_action": "Do not promote mock rows beyond research preview.",
    },
    STATE_EXECUTION_BLOCKED: {
        "badge": "EXEC BLOCKED",
        "title": "Execution unavailable",
        "explanation": "Broker offline, breaker tripped, or critical IBKR check failed.",
        "next_action": "Open IBKR tab and resolve connectivity before orders.",
    },
    STATE_NO_DATA: {
        "badge": "NO DATA",
        "title": "Nothing to show",
        "explanation": "Fetch succeeded but returned an empty set for this surface.",
        "next_action": "Normal on WAIT days — patience is the correct action.",
    },
    STATE_NOT_AUTHORITATIVE: {
        "badge": "NOT AUTHORITATIVE",
        "title": "Wrong surface for deploy copy",
        "explanation": "Deploy chips belong on Dashboard / Playbook only.",
        "next_action": "Switch to Dashboard for board gate and deploy posture.",
    },
    STATE_OK: {
        "badge": "",
        "title": "Live",
        "explanation": "",
        "next_action": "",
    },
    STATE_FAILED_FETCH_FALLBACK: {
        "badge": "FETCH FAILED",
        "title": "Live fetch failed — fallback visible",
        "explanation": "Fallback watchlist samples are visible (not live scanner output).",
        "next_action": "Confirm in Playbook before sizing; retry when API recovers.",
    },
}

_SURFACE_WARMUP_LOADING_LINES: Dict[str, str] = {
    "dossier_research": "Live dossier fetch still loading — retry when core panels populate.",
    "backtest_research": "Backtest API still loading — retry Run lab in a few seconds (research-only shell may appear meanwhile).",
    "funds_research": "Fund Research Lab still loading — sleeve cards refresh when the API is ready.",
    "rejections_diagnostic": "Rejection audit still loading — brief shell may show until the pipeline is ready.",
    "flow_supporting": "Flow API still loading — mock/research shell may appear until live provider connects.",
    "ops_diagnostic": "Ops API still loading — refresh Ops panels in a few seconds.",
    "": "API still loading — retry in a few seconds.",
}


def normalize_fetch_state(
    *,
    loading: bool = False,
    error: Optional[str] = None,
    stale: bool = False,
    fallback: bool = False,
    partial: bool = False,
    mock_only: bool = False,
    empty: bool = False,
    execution_blocked: bool = False,
    probe_only: bool = False,
    runtime_unknown: bool = False,
) -> str:
    """Derive canonical fetch state from boolean flags (first match wins)."""
    if loading:
        return STATE_LOADING
    if error:
        return STATE_FAILED_FETCH
    if execution_blocked:
        return STATE_EXECUTION_BLOCKED
    if runtime_unknown:
        return STATE_RUNTIME_UNKNOWN
    if probe_only:
        return STATE_PROBE_ONLY
    if mock_only:
        return STATE_MOCK_ONLY
    if fallback:
        return STATE_FALLBACK
    if stale:
        return STATE_STALE
    if partial:
        return STATE_PARTIAL
    if empty:
        return STATE_NO_DATA
    return STATE_OK


def describe_fetch_state(
    state: str,
    *,
    detail: Optional[str] = None,
    next_action: Optional[str] = None,
) -> Dict[str, str]:
    """Return badge/title/explanation/next_action for a fetch state."""
    base = dict(_STATE_COPY.get(state, _STATE_COPY[STATE_OK]))
    if detail:
        base["explanation"] = f"{base['explanation']} ({detail})".strip()
    if next_action:
        base["next_action"] = next_action
    base["state"] = state
    return base


DOSSIER_SERVICE_DEFAULT = "market_data_service"


def describe_dossier_fetch_state(
    state: str,
    *,
    detail: Optional[str] = None,
    service: Optional[str] = None,
) -> Dict[str, str]:
    """Dossier-tab degraded copy — research-specific, not generic surface fetch."""
    svc = (service or DOSSIER_SERVICE_DEFAULT).strip() or DOSSIER_SERVICE_DEFAULT
    if state == STATE_FAILED_FETCH:
        explanation = f"Live dossier fetch failed from {svc}"
        if detail:
            explanation = f"{explanation} ({detail})"
        return {
            "badge": "RESEARCH UNAVAILABLE",
            "title": "Research unavailable",
            "explanation": explanation,
            "next_action": "This page is not decision-grade until research loads",
            "state": state,
        }
    if state == STATE_LOADING:
        return {
            "badge": "LOADING",
            "title": "Loading dossier research",
            "explanation": f"Fetching live research from {svc} — do not treat empty panels as proof of verdict.",
            "next_action": "Wait for core dossier to load or retry.",
            "state": state,
        }
    if state == STATE_STALE:
        return {
            "badge": "STALE",
            "title": "Cached dossier",
            "explanation": f"Showing cached research — live fetch from {svc} did not complete.",
            "next_action": "Retry research before acting on levels or verdict.",
            "state": state,
        }
    if state == STATE_PARTIAL:
        if svc and "instant-degraded" in svc:
            explanation = (
                f"Core dossier loaded from {svc} snapshot — not live market_data_service research."
            )
            if detail:
                explanation = f"{explanation} ({detail})"
            return {
                "badge": "RESEARCH ONLY",
                "title": "Partial dossier — snapshot core",
                "explanation": explanation,
                "next_action": "Load enrichments or retry when API is full before sizing or IBKR handoff.",
                "state": state,
            }
        explanation = "Some research modules failed — evidence is incomplete."
        if detail:
            explanation = f"{explanation} ({detail})"
        return {
            "badge": "PARTIAL",
            "title": "Partial dossier",
            "explanation": explanation,
            "next_action": "Retry or load enrichments before sizing.",
            "state": state,
        }
    return describe_fetch_state(state, detail=detail)


OPS_STATE_LOADING = "loading"
OPS_STATE_FALLBACK = "fallback"
OPS_STATE_UNAVAILABLE = "unavailable"
OPS_STATE_RUNTIME_UNKNOWN = "runtime_unknown"
OPS_STATE_RETRY_RECOMMENDED = "retry_recommended"

_OPS_DEGRADED_COPY: Dict[str, Dict[str, str]] = {
    OPS_STATE_LOADING: {
        "badge": "LOADING",
        "title": "Loading",
        "explanation": "Ops panel data is still loading — do not treat empty panels as proof of health.",
        "next_action": "Wait for fetch to complete or refresh the tab.",
    },
    OPS_STATE_FALLBACK: {
        "badge": "FALLBACK",
        "title": "Fallback",
        "explanation": "Live Ops fetch failed — showing built-in fallback copy, not authoritative release notes.",
        "next_action": "Retry when the API recovers; edit data/changelog.json for canonical notes.",
    },
    OPS_STATE_UNAVAILABLE: {
        "badge": "UNAVAILABLE",
        "title": "Unavailable",
        "explanation": "Could not load this Ops panel — session state cannot be confirmed.",
        "next_action": "Retry in a few seconds; confirm the API is running and refresh Ops.",
    },
    OPS_STATE_RUNTIME_UNKNOWN: {
        "badge": "RUNTIME UNKNOWN",
        "title": "Runtime unknown",
        "explanation": "Engine or backend runtime evidence could not be confirmed from this panel.",
        "next_action": "Refresh Ops health and confirm engine + provider state.",
    },
    OPS_STATE_RETRY_RECOMMENDED: {
        "badge": "RETRY",
        "title": "Retry recommended",
        "explanation": "Network or server error prevented a fresh Ops read.",
        "next_action": "Retry in a few seconds; use Ops diagnostics if the failure persists.",
    },
}

# Pill severity for fetch badges (pr=blocked, pa=degraded, pg=live, pw=neutral)
_SEVERITY_BADGE_CLASS: Dict[str, str] = {
    STATE_FAILED_FETCH: "pr",
    STATE_FAILED_FETCH_FALLBACK: "pr",
    STATE_EXECUTION_BLOCKED: "pr",
    STATE_STALE: "pa",
    STATE_FALLBACK: "pa",
    STATE_PARTIAL: "pa",
    STATE_LOADING: "pa",
    STATE_PROBE_ONLY: "pw",
    STATE_RUNTIME_UNKNOWN: "pw",
    STATE_RESEARCH_ONLY: "pw",
    STATE_MOCK_ONLY: "pw",
    STATE_NO_DATA: "pw",
    STATE_NOT_AUTHORITATIVE: "pw",
    STATE_OK: "pg",
    OPS_STATE_LOADING: "pa",
    OPS_STATE_FALLBACK: "pa",
    OPS_STATE_UNAVAILABLE: "pr",
    OPS_STATE_RUNTIME_UNKNOWN: "pw",
    OPS_STATE_RETRY_RECOMMENDED: "pa",
}


def normalize_ops_panel_state(
    *,
    loading: bool = False,
    error: Optional[str] = None,
    fallback: bool = False,
    runtime_unknown: bool = False,
    timed_out: bool = False,
) -> str:
    """Map Ops sub-panel fetch flags to canonical degraded vocabulary."""
    if loading:
        return OPS_STATE_LOADING
    if runtime_unknown:
        return OPS_STATE_RUNTIME_UNKNOWN
    if error and (fallback or timed_out):
        return OPS_STATE_FALLBACK
    if error:
        low = str(error).lower()
        if any(
            tok in low
            for tok in (
                "failed to fetch",
                "networkerror",
                "load failed",
                "timeout",
                "http 503",
                "http 502",
                "warming up",
            )
        ):
            return OPS_STATE_RETRY_RECOMMENDED
        return OPS_STATE_UNAVAILABLE
    if fallback:
        return OPS_STATE_FALLBACK
    return STATE_OK


def ops_degraded_copy(state: str, *, detail: Optional[str] = None) -> Dict[str, str]:
    """Return badge/title/explanation/next_action for Ops degraded panels."""
    base = dict(
        _OPS_DEGRADED_COPY.get(state, _OPS_DEGRADED_COPY[OPS_STATE_UNAVAILABLE])
    )
    if detail:
        base["explanation"] = f"{base['explanation']} ({detail})".strip()
    base["state"] = state
    return base


def severity_badge_class(state: str) -> str:
    """Alpine pill class for fetch / ops degraded state (pr|pa|pg|pw)."""
    return _SEVERITY_BADGE_CLASS.get(str(state or "").lower(), "pw")


def surface_warmup_loading_line(surface_mode: Optional[str] = None) -> str:
    """Tab-aware loading line — single vocabulary for warmup banners."""
    key = str(surface_mode or "").strip()
    return _SURFACE_WARMUP_LOADING_LINES.get(key, _SURFACE_WARMUP_LOADING_LINES[""])


def surface_warmup_next_action(state: str, *, surface_mode: Optional[str] = None) -> str:
    """Unified retry CTA — prefer canonical fetch_state next_action."""
    s = str(state or "").lower()
    if s == OPS_STATE_RETRY_RECOMMENDED or s == "retry_recommended":
        return ops_degraded_copy(OPS_STATE_RETRY_RECOMMENDED)["next_action"]
    if s == OPS_STATE_LOADING or s == STATE_LOADING:
        if str(surface_mode or "") == "ops_diagnostic":
            return ops_degraded_copy(OPS_STATE_LOADING)["next_action"]
        return describe_fetch_state(STATE_LOADING)["next_action"]
    if s in (STATE_FAILED_FETCH, STATE_FAILED_FETCH_FALLBACK):
        return describe_fetch_state(s if s in _STATE_COPY else STATE_FAILED_FETCH)["next_action"]
    if s == STATE_STALE:
        return describe_fetch_state(STATE_STALE)["next_action"]
    return describe_fetch_state(STATE_FAILED_FETCH)["next_action"]


def ops_degraded_line(state: str, *, detail: Optional[str] = None) -> str:
    """Single-line Ops degraded message for trust strips and banners."""
    copy = ops_degraded_copy(state, detail=detail)
    badge = copy.get("badge") or ""
    explanation = copy.get("explanation") or ""
    return f"{badge} — {explanation}".strip(" —") if badge else explanation


def ops_updates_panel_title(state: str, *, timed_out: bool = False) -> str:
    """Updates sub-panel headline when changelog fetch is degraded."""
    if state == OPS_STATE_UNAVAILABLE:
        return "Panel unavailable"
    if state == OPS_STATE_FALLBACK:
        return "No fallback available" if timed_out else "Fallback unavailable"
    return ops_degraded_copy(state)["title"]


def fetch_state_from_http(
    status: Optional[int],
    *,
    loading: bool = False,
    body_ok: bool = True,
    stale: bool = False,
    fallback: bool = False,
    mock_only: bool = False,
    empty: bool = False,
    execution_blocked: bool = False,
    probe_only: bool = False,
    runtime_unknown: bool = False,
    error_message: Optional[str] = None,
) -> Dict[str, str]:
    """Map HTTP + flags to describe_fetch_state payload."""
    if loading:
        return describe_fetch_state(STATE_LOADING)
    if status is None and error_message:
        return describe_fetch_state(STATE_FAILED_FETCH, detail=error_message)
    if status and status >= 400:
        return describe_fetch_state(
            STATE_FAILED_FETCH,
            detail=error_message or f"HTTP {status}",
        )
    if not body_ok:
        return describe_fetch_state(STATE_PARTIAL)
    state = normalize_fetch_state(
        stale=stale,
        fallback=fallback,
        mock_only=mock_only,
        empty=empty,
        execution_blocked=execution_blocked,
        probe_only=probe_only,
        runtime_unknown=runtime_unknown,
    )
    return describe_fetch_state(state)


def warmup_status_line(
    *,
    health_mode: Optional[str] = None,
    instant_degraded: bool = False,
    fetch_failed: bool = False,
    api_reachable: bool = True,
) -> str:
    """Cold-start status for data contract / instant banner (loading vs warming vs broken vs offline)."""
    mode = str(health_mode or "").lower()
    if not api_reachable:
        return "OFFLINE — API unreachable · instant snapshot may be stale"
    if mode == "loading":
        return "WARMING — backend importing modules · brief/monitor queue only until full"
    if instant_degraded or fetch_failed:
        return "DEGRADED — instant snapshot · council/scanner may disagree until live ranked loads"
    if mode == "full":
        return "LIVE — health mode full · ranked payloads authoritative when fetch badges clear"
    return "LOADING — probing /health before treating board as live"


def warmup_upgrade_queue_preview(
    *,
    health_mode: Optional[str] = None,
    has_near_miss: bool = False,
    has_brief_fallback: bool = False,
) -> str:
    """What will populate when API is ready (monitor queue from brief / near-miss)."""
    mode = str(health_mode or "").lower()
    if mode != "loading" and not has_brief_fallback:
        return ""
    parts = [
        "live ranked playbook",
        "today council reconciliation",
        "dossier enrichment",
    ]
    if has_near_miss or has_brief_fallback:
        parts.insert(0, "monitor queue (brief near-miss + top watch)")
    return "When API ready: " + " · ".join(parts)


def trust_provenance_line(
    *,
    source: Optional[str] = None,
    freshness: Optional[str] = None,
    age_minutes: Optional[float] = None,
    snapshot_label: Optional[str] = None,
) -> str:
    """Snapshot age + source for data contract strip."""
    src = (source or "market_data_service").replace("_", " ")
    fresh = freshness or "REAL_TIME"
    age = ""
    if age_minutes is not None and age_minutes >= 0:
        if age_minutes < 60:
            age = f"{int(age_minutes)}m ago"
        else:
            age = f"{int(age_minutes // 60)}h ago"
    elif snapshot_label:
        age = snapshot_label
    bits = [src, fresh]
    if age:
        bits.append(age)
    return " · ".join(bits)


def loading_session_recovery_line(
    *,
    health_mode: Optional[str] = None,
    cc_mode: Optional[str] = None,
) -> str:
    """Operator copy for long mode=loading / port-8000 instant→:8001 proxy sessions."""
    mode = str(health_mode or "").lower()
    if mode != "loading" and str(cc_mode or "").upper() != "LOADING":
        return ""
    return (
        "Cold start: port 8000 instant shell may proxy to :8001 — "
        "wait for /health mode=full; restart once if loading exceeds ~2 min"
    )


def discovery_fallback_banner_line() -> str:
    """Primary scanners-tab banner when live fetch failed but fallback rows render."""
    return (
        "Live fetch failed — showing fallback watchlist samples. "
        "Research-only fallback results — not live scanner output. "
        "Confirm in Playbook before sizing."
    )


def route_abort_recovery_hint(surface: str = "") -> str:
    """One-time recovery copy after client route abort — no backend auto-heal."""
    key = str(surface or "").lower()
    if key in ("dossier", "dossier_research"):
        return (
            "Route failed — retry Load core only; CONFIRM ONLY until live dossier returns"
        )
    if key in ("discovery", "scanners"):
        return (
            "Scanner route failed — retry Run Scanners; fallback funnel is not deploy authority"
        )
    return "Fetch failed — retry when badges clear; monitor queue and Guide remain safe"


def stale_refresh_recovery_line() -> str:
    return "Market snapshot stale — refresh market data before using levels for sizing"


def engine_off_recovery_line() -> str:
    return (
        "Engine OFF — start engine in Ops or set CC_AUTO_START_ENGINE=1; "
        "board may be precomputed only"
    )


def ibkr_login_to_ready_hint(
    *,
    ibkr_short: str = "",
    ibkr_level: str = "",
    hint: str = "",
    gateway_reachable: bool = False,
    session_connected: bool = False,
    handoff_ready: bool = False,
) -> str:
    """State-driven IBKR recovery line — mirrors ibkr_diagnosis short codes."""
    custom = str(hint or "").strip()
    short = str(ibkr_short or "").upper()
    level = str(ibkr_level or "").lower()
    if short in ("OFFLINE", "NO IBAPI", "API OFF") or level == "offline":
        return custom or (
            "IBKR OFFLINE — start Gateway/TWS and confirm API port; "
            "Connect on IBKR tab when reachable"
        )
    if short == "BLOCKED":
        return "IBKR BLOCKED — circuit breaker active; clear risk gate before handoff"
    if short == "READY" or handoff_ready or level == "ready":
        return custom or (
            "IBKR READY — handoff path verified; confirm bracket alignment before transmit"
        )
    if short in ("LOGIN", "HANDSHAKE") or (gateway_reachable and not session_connected):
        return custom or (
            "IBKR LOGIN — connect session on IBKR tab; READY required before handoff "
            "(bracket aligned)"
        )
    if short in ("MONITOR", "PARTIAL") or level == "partial":
        return custom or (
            "IBKR partial — session up; confirm bracket and portfolio sync before handoff"
        )
    return custom or (
        "IBKR OFFLINE — start Gateway/TWS; Connect on IBKR tab when API port is reachable"
    )


def soak_confirmation_signals() -> Dict[str, str]:
    """Stable data-cc / copy anchors for staging soak sign-off (no authority change)."""
    return {
        "instant_degraded": 'data-cc="instant-degraded-banner"',
        "warmup_strip": 'data-cc="warmup-context-strip"',
        "data_contract_strip": 'data-cc="data-contract-strip"',
        "deploy_strip": 'data-cc="deploy-status-strip"',
        "mission_panel": 'data-cc="today-mission-panel"',
        "playbook_surface": 'data-cc="playbook-surface"',
        "market_stale": 'data-cc="market-strip-stale"',
        "ops_runbook": 'data-cc="ops-recovery-runbook"',
        "loading_recovery": loading_session_recovery_line(health_mode="loading"),
        "operator_loading_safe": operator_loading_safe_line(health_mode="loading"),
        "engine_off": engine_off_recovery_line(),
        "stale_refresh": stale_refresh_recovery_line(),
        "ibkr_login_ready": ibkr_login_to_ready_hint(),
        "route_abort_dossier": route_abort_recovery_hint("dossier"),
        "route_abort_scanners": route_abort_recovery_hint("discovery"),
    }


def today_mission_safe_unlock_hint(
    *,
    wait_day: bool = False,
    ibkr_ready: bool = True,
    engine_running: bool = True,
) -> str:
    if wait_day:
        return "Blocked: deploy · Safe: monitors · near-miss · Playbook ranking"
    if not ibkr_ready:
        return "Blocked: IBKR handoff · Safe: dossier core-only · monitor queue"
    if not engine_running:
        return "Blocked: new cycle sizing · Safe: Guide · monitors until engine ON"
    return ""


def today_mission_wait_subtitle(*, wait_day: bool = False) -> str:
    """Mission panel subtitle on WAIT days."""
    if wait_day:
        return "Deploy blocked — use monitors and Playbook ranking only"
    return ""


def today_mission_monitors_column_hint(
    *,
    wait_day: bool = False,
    watch_qualified: int = 0,
    monitor_count: int = 0,
) -> str:
    """Mission panel monitors column — attention routing without tradability."""
    wq = int(watch_qualified or 0)
    mc = int(monitor_count or 0)
    if wq > 0:
        return (
            f"{wq} watch-qualified on funnel — mission tickers are attention queue, "
            "not extra KPI count"
        )
    if mc > 0:
        return (
            "Fallback monitors — scan / near-miss queue; "
            "filter_funnel is authority for watch-qualified"
        )
    if wait_day:
        return "Near-miss · watch queue — priority only, not deploy on WAIT"
    return "Watch / near-miss — ranking for attention, not handoff permission"


def playbook_what_to_monitor_line(
    *,
    wait_day: bool = False,
    top_symbol: str = "",
    near_miss_count: int = 0,
) -> str:
    """Playbook WAIT-day monitor guidance — operator-facing, no deploy authority."""
    if not wait_day:
        return ""
    parts: list[str] = []
    if top_symbol:
        parts.append(f"{top_symbol.upper()} upgrade triggers")
    nm = int(near_miss_count or 0)
    if nm > 0:
        parts.append(f"{nm} near-miss row{'s' if nm != 1 else ''}")
    parts.append("deploy unlock checklist below")
    body = " · ".join(parts) if parts else "near-miss strip · gate context"
    return f"Monitor only — {body} · no deploy authority"


def operator_loading_safe_line(
    *,
    health_mode: Optional[str] = None,
    cc_mode: Optional[str] = None,
    wait_day: bool = False,
    fetch_failed: bool = False,
    instant_degraded: bool = False,
) -> str:
    """Operator-safe actions while loading or board WAIT (no deploy authority)."""
    mode = str(health_mode or "").lower()
    if mode == "loading" or str(cc_mode or "").upper() == "LOADING":
        return (
            "Safe now: monitor queue, Guide checklist, dossier core-only — "
            "wait for backend import + /health mode=full before sizing or IBKR handoff"
        )
    if fetch_failed or instant_degraded:
        return (
            "Safe now: Guide, monitors, dossier core-only — "
            "retry when fetch badges clear; no deploy from fallback"
        )
    if wait_day:
        return (
            "Safe now: near-miss monitors, Discovery context, Playbook ranking — "
            "deploy blocked on WAIT"
        )
    return ""


def today_mission_monitors_label(
    monitors: Optional[list] = None,
    *,
    near_miss_count: int = 0,
    watch_qualified: int = 0,
) -> str:
    """Dashboard mission panel monitors column heading."""
    n = len(monitors or [])
    nm = int(near_miss_count or 0)
    wq = int(watch_qualified or 0)
    if not n and not nm:
        return "Monitors"
    prefix = "Fallback monitors" if n and wq == 0 else "Monitors"
    base = f"{prefix} ({n})" if n else prefix
    return f"{base} · {nm} near-miss" if nm else base


def today_mission_card_gates(
    *,
    risk_blockers: Optional[list] = None,
    why_not: Optional[list] = None,
    limit: int = 3,
) -> list[str]:
    """Council / card-level gate flags from todays_decision — not infra blockers."""
    blockers: list[str] = []
    for rb in risk_blockers or []:
        s = str(rb).strip()
        if s and s not in blockers:
            blockers.append(s)
    for w in (why_not or [])[:2]:
        s = str(w).strip()
        if s and s not in blockers:
            blockers.append(s)
    return blockers[:limit]


def today_mission_system_blockers(
    *,
    ibkr_short: str = "",
    ibkr_ready: bool = False,
    engine_running: bool = True,
    breaker: bool = False,
    data_tier: str = "",
    brief_fallback: bool = False,
    instant_degraded: bool = False,
    fetch_badge: str = "",
    system_truth: Optional[Dict[str, Any]] = None,
) -> list[str]:
    """Infrastructure blockers — prefer system_truth.reason_codes when present."""
    if isinstance(system_truth, dict) and system_truth.get("reason_codes"):
        from src.services.system_truth import mission_blockers_from_truth

        return mission_blockers_from_truth(system_truth)
    out: list[str] = []
    if not ibkr_ready:
        label = str(ibkr_short or "OFFLINE").strip().upper()
        if not label.startswith("IBKR"):
            label = f"IBKR {label}"
        out.append(label)
    if not engine_running:
        out.append("ENGINE OFF")
    if breaker:
        out.append("EXEC BLOCKED — risk breaker")
    tier = str(data_tier or "").upper()
    if tier in ("STALE", "CRITICAL"):
        out.append(f"DATA {tier}")
    fb = str(fetch_badge or "").upper()
    if fb in ("FALLBACK", "FETCH FAILED", "STALE") and "FALLBACK" not in " ".join(out):
        if fb == "FALLBACK":
            out.append("FALLBACK / BRIEF ONLY")
        elif fb == "FETCH FAILED":
            out.append("FETCH FAILED — not decision-grade")
    if brief_fallback or instant_degraded:
        if not any("FALLBACK" in x or "BRIEF" in x for x in out):
            out.append("FALLBACK / BRIEF ONLY")
    return out


def today_mission_blockers_title(*, wait_day: bool = False, has_system: bool = False) -> str:
    if wait_day and has_system:
        return "System blockers · gate flags"
    if wait_day:
        return "Gate flags"
    return "System blockers" if has_system else "Blockers"


def today_mission_empty_blockers_copy(
    *,
    system_blockers: Optional[list] = None,
    card_gates: Optional[list] = None,
) -> str:
    if system_blockers and not card_gates:
        return "No card-level gate flags"
    return "None flagged"


def today_mission_panel(
    *,
    risk_blockers: Optional[list] = None,
    why_not: Optional[list] = None,
    near_miss: Optional[list] = None,
    top_ranked: Optional[list] = None,
    limit: int = 3,
    system_blockers: Optional[list] = None,
    system_truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Top blockers + monitors — mission strip uses system_truth.reason_codes when present."""
    card_gates = today_mission_card_gates(
        risk_blockers=risk_blockers,
        why_not=why_not,
        limit=limit,
    )
    truth = system_truth or {}
    reason_codes = truth.get("reason_codes") or []
    if reason_codes:
        from src.services.system_truth import reason_codes_to_copy

        blockers = list(truth.get("reason_copy") or reason_codes_to_copy(reason_codes))[
            : max(limit, 5)
        ]
        sys_blk = blockers[:limit]
    else:
        sys_blk = list(system_blockers or [])
        blockers: list[str] = []
        for s in sys_blk + card_gates:
            if s and s not in blockers:
                blockers.append(s)
    monitors: list[str] = []
    for nm in near_miss or []:
        t = nm.get("ticker") if isinstance(nm, dict) else None
        if t:
            tick = str(t).upper()
            if tick not in monitors:
                monitors.append(tick)
    for r in top_ranked or []:
        t = r.get("ticker") if isinstance(r, dict) else None
        if t:
            tick = str(t).upper()
            if tick not in monitors:
                monitors.append(tick)
    return {
        "system_blockers": sys_blk[:limit],
        "card_gates": card_gates,
        "blockers": blockers[: max(limit, 5)],
        "monitors": monitors[:limit],
        "near_miss_count": len(near_miss or []),
        "monitors_label": today_mission_monitors_label(
            monitors[:limit],
            near_miss_count=len(near_miss or []),
        ),
    }


def ops_recovery_guide(
    *,
    health_mode: Optional[str] = None,
    engine_running: bool = False,
    ibkr_connected: bool = False,
    breaker: bool = False,
    page_degraded: bool = False,
) -> Dict[str, Any]:
    """Ops runbook: retry vs capital block vs safe degraded mode (ops_degraded vocabulary)."""
    mode = str(health_mode or "").lower()
    retry: list[str] = []
    blocks: list[str] = []
    safe: list[str] = []

    if mode == "loading":
        port_line = loading_session_recovery_line(health_mode=mode)
        if port_line:
            retry.append(port_line)
        retry.append("Wait for /health mode=full, then refresh Dashboard and Playbook")
    else:
        retry.append("Refresh Ops health · Error log · Updates panels")

    if not engine_running:
        retry.append("Start engine (Ops health) or set CC_AUTO_START_ENGINE=1")
        blocks.append("No engine cycle — Today/Signals may be precomputed only")
    if breaker:
        blocks.append("Risk breaker ON — blocks new entries until cleared")
    if not ibkr_connected:
        blocks.append("IBKR session inactive — no handoff until LOGIN→READY on IBKR tab")

    if page_degraded or mode == "loading":
        safe_line = operator_loading_safe_line(health_mode=mode, wait_day=False)
        if safe_line:
            safe.append(safe_line)
        else:
            safe.append("Monitor-only: near-miss, Discovery context, Guide checklist")
        safe.append("Read data contract strip — FETCH FAILED / FALLBACK suspends sizing")
    else:
        safe.append("Paper review and dossier research when board is WAIT")
        safe.append("Ops diagnostics do not override Dashboard deploy gate")

    return {"retry": retry, "blocks_capital": blocks, "safe_degraded": safe}


# Opportunity intelligence monitor types — labels for Today / mission panel only.
OPPORTUNITY_MONITOR_TRIGGER_TYPES: Dict[str, str] = {
    "structure": "Structure repair — monitor for playbook gate",
    "volume": "Volume confirmation — attention only",
    "event_clear": "Event risk cleared — narrative context, not trigger",
    "insider_cluster": "Insider cluster (lagged Form 4) — research context",
    "13f_sponsorship": "13F sponsorship change (lagged) — research context",
    "strategy_health": "Strategy curve health — sizing template research only",
    "cluster_deploy": "Deploy cluster — board gate still required",
    "cluster_pilot": "Pilot cluster — half-size research template",
    "cluster_watch": "Watch cluster — WAIT day monitors",
    "cluster_near_miss": "Near-miss cluster — upgrade layer, not deploy",
    "cluster_blocked_cost": "Blocked by cost — net edge after drag too weak",
    "cluster_blocked_dd": "Blocked by DD — drawdown budget constrains sizing",
}

# Alias for quant / algo daily hooks (same labels as opportunity monitor types).
QUANT_CLUSTER_MONITOR_LABELS: Dict[str, str] = {
    "deploy": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_deploy"],
    "pilot": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_pilot"],
    "watch": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_watch"],
    "near-miss": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_near_miss"],
    "blocked-by-cost": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_blocked_cost"],
    "blocked-by-dd": OPPORTUNITY_MONITOR_TRIGGER_TYPES["cluster_blocked_dd"],
}


def describe_opportunity_monitor_trigger(trigger_type: str) -> str:
    """Human label for opportunity monitor rows (monitoring_only in today_insights)."""
    key = str(trigger_type or "").strip().lower()
    return OPPORTUNITY_MONITOR_TRIGGER_TYPES.get(
        key,
        "Opportunity context — monitoring only, not deploy authority",
    )


def index_regime_strip_line(
    summary: Optional[Dict[str, Any]] = None,
    *,
    strip: Optional[Dict[str, Any]] = None,
) -> str:
    """Monitor-only index regime copy for Today strip — never deploy authority."""
    s = summary or {}
    st = strip or {}
    line = str(st.get("line") or s.get("strip_line") or s.get("summary") or "").strip()
    if not line:
        return "Index regime unavailable — MOCK/DEGRADED"
    degraded = bool(s.get("degraded") or st.get("degraded"))
    if degraded and "MOCK" not in line.upper():
        line = f"MOCK/DEGRADED · {line}"
    return f"{line} — monitor only, not deploy"


def regime_fit_pill_class(regime_fit: str = "") -> str:
    fit = str(regime_fit or "").lower()
    if fit == "aligned":
        return "pg"
    if fit in ("stressed_filter", "lag_vs_index"):
        return "pr"
    if fit == "wait_filter":
        return "pa"
    return "pw"


def regime_fit_tag(regime_fit: str = "") -> str:
    fit = str(regime_fit or "").lower()
    labels = {
        "aligned": "Regime aligned",
        "stressed_filter": "Stressed filter",
        "wait_filter": "WAIT filter",
        "lag_vs_index": "Lags index",
        "selective_filter": "Selective filter",
    }
    return labels.get(fit, "Selective filter")


def index_leadership_dossier_line(block: Optional[Dict[str, Any]] = None) -> str:
    b = block or {}
    summary = str(b.get("summary") or "").strip()
    if b.get("degraded") and "MOCK" not in summary.upper():
        summary = f"{summary or 'Relative leadership unavailable'} — MOCK/DEGRADED"
    return f"{summary or 'Relative leadership — confirm-only'} — not deploy authority"


def today_mission_quant_cluster_lines(
    hints: Optional[list] = None,
    *,
    limit: int = 3,
) -> list[str]:
    """Short monitor-only lines from /api/v7/today quant_cluster_hints — no deploy authority."""
    lines: list[str] = []
    for hint in list(hints or [])[:limit]:
        if not isinstance(hint, dict):
            continue
        label = str(hint.get("label") or "").strip()
        if not label:
            cluster = str(hint.get("cluster") or "").strip()
            label = QUANT_CLUSTER_MONITOR_LABELS.get(cluster, cluster)
        detail = str(hint.get("detail") or "").strip()
        if detail and len(detail) <= 72:
            line = f"{label} — {detail}"
        else:
            line = f"{label} — monitor only, not deploy"
        if line and line not in lines:
            lines.append(line)
    return lines


def today_board_hero_synthesis_line(
    *,
    wait_day: bool = False,
    quant_cluster_hints: Optional[list] = None,
    no_setup_diagnosis: Optional[Dict[str, Any]] = None,
) -> str:
    """Board hero one-liner for WAIT/monitor context — synthesis only, not deploy permission."""
    if not wait_day:
        return ""
    parts: list[str] = []
    hints = list(quant_cluster_hints or [])
    if hints and isinstance(hints[0], dict):
        h0 = hints[0]
        label = str(h0.get("label") or "").strip()
        if not label:
            cluster = str(h0.get("cluster") or "").strip()
            label = QUANT_CLUSTER_MONITOR_LABELS.get(cluster, cluster)
        detail = str(h0.get("detail") or "").strip()
        if label:
            quant_part = label
            if detail and len(detail) <= 48:
                quant_part += f" ({detail})"
            elif detail:
                quant_part += " — monitor context"
            parts.append(quant_part)
    diag = no_setup_diagnosis if isinstance(no_setup_diagnosis, dict) else {}
    blocker = str(diag.get("primary_blocker") or diag.get("headline") or "").strip()
    if blocker:
        parts.append(blocker)
    if not parts:
        return ""
    return (
        "Synthesis hint (monitor only): "
        + " · ".join(parts)
        + " — not deploy permission"
    )


def today_execution_readiness_diagnostic(
    execution_readiness: Optional[Dict[str, Any]] = None,
) -> str:
    """One-line exec path gap summary for Today strip — diagnostic only."""
    er = execution_readiness if isinstance(execution_readiness, dict) else {}
    sub = er.get("sub_status") if isinstance(er.get("sub_status"), dict) else {}
    gaps: list[str] = []
    if sub.get("broker_transport") != "up":
        gaps.append("transport down")
    if sub.get("session_auth") != "active":
        gaps.append("session inactive")
    if sub.get("engine") != "on":
        gaps.append("engine off")
    if sub.get("handoff_readiness") != "ready":
        gaps.append("handoff blocked")
    if sub.get("bracket_readiness") != "ready":
        gaps.append("bracket draft")
    if er.get("circuit_breaker"):
        gaps.append("breaker on")
    if not gaps and er.get("trade_handoff_ready"):
        return ""
    reasons = [str(r).strip() for r in (er.get("degraded_reasons") or [])[:2] if r]
    base = "Exec diagnostic: " + (" · ".join(gaps) if gaps else (er.get("readiness_label") or "path incomplete"))
    if reasons:
        base += " — " + "; ".join(reasons)
    return base + " (not deploy authority)"


DOSSIER_CONFIRM_ONLY_SIZING = "No sizing guidance in confirm-only mode"


def dossier_quote_available(data: Optional[Dict[str, Any]] = None) -> bool:
    """True when dossier header may show a live price (not $0 placeholder)."""
    d = data or {}
    if d.get("quote_pending") or d.get("quote_unavailable"):
        return False
    try:
        price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return False
    return price > 0


def dossier_price_display(data: Optional[Dict[str, Any]] = None) -> str:
    if not dossier_quote_available(data):
        return "Quote unavailable"
    return f"${float(data['price']):.2f}"


def dossier_change_pct_display(data: Optional[Dict[str, Any]] = None) -> str:
    if not dossier_quote_available(data):
        return "—"
    try:
        change = float((data or {}).get("change_pct"))
    except (TypeError, ValueError):
        return "—"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.2f}%"


def dossier_confirm_only_sizing_line() -> str:
    return DOSSIER_CONFIRM_ONLY_SIZING


def dossier_sizing_display(*, blocked: bool, reason: str = "") -> str:
    if not blocked:
        return ""
    r = str(reason or "")
    if r == "confirm_only":
        return "—"
    if r in ("failed", "partial"):
        return "Blocked"
    return "—"


def dossier_sizing_explanation(*, blocked: bool, reason: str = "") -> str:
    if not blocked:
        return ""
    r = str(reason or "")
    if r == "confirm_only":
        return DOSSIER_CONFIRM_ONLY_SIZING
    if r in ("failed", "partial"):
        return "Sizing blocked until live dossier loads"
    if r == "rr_unavailable":
        return "Size unavailable — R:R not confirmed"
    return "Size unavailable"


def _opportunity_intel_degraded(payload: Optional[Dict[str, Any]] = None) -> bool:
    p = payload or {}
    tier = str(p.get("data_tier") or "").lower()
    return bool(p.get("degraded") or p.get("instant_degraded") or tier == "mock")


def insider_context_label(
    quality: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Dossier opp-intel insider line — softer when mock/degraded."""
    degraded = _opportunity_intel_degraded(payload)
    q = str(quality or "").lower()
    labels = {
        "supportive_only": (
            "Supportive context (mock/lagged)"
            if degraded
            else "Supportive context"
        ),
        "notable_accumulation": (
            "Possible accumulation (mock/lagged)"
            if degraded
            else "Notable accumulation (lagged)"
        ),
        "notable_distribution": (
            "Possible distribution (mock/lagged)"
            if degraded
            else "Distribution risk (lagged)"
        ),
        "noise": "Routine Form 4 (mock)" if degraded else "Routine Form 4",
        "insufficient_data": (
            "Insufficient history (mock)" if degraded else "Insufficient history"
        ),
    }
    return labels.get(
        q,
        "Insider context (mock/lagged)" if degraded else "Insider context (lagged)",
    )


def institutional_sponsorship_label(
    verdict: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    v = str(verdict or "").strip()
    if not v:
        return "—"
    if not _opportunity_intel_degraded(payload):
        return v
    low = v.lower()
    if "added sponsorship" in low:
        return "Illustrative added sponsorship (mock/lagged)"
    if "mixed" in low or "unchanged" in low:
        return "Illustrative mixed / unchanged (mock/lagged)"
    return f"{v} (mock/lagged)"


def dossier_trade_plan_note(
    *,
    note: str = "",
    setup_type: str = "",
    research_only: bool = False,
    levels_blank: bool = False,
) -> str:
    """Structure snapshot footnote when levels are missing in confirm-only mode."""
    text = str(note or setup_type or "").strip()
    if research_only and levels_blank:
        return "Live structure unavailable — structure review only"
    if levels_blank:
        return "Live structure unavailable"
    if text:
        return text
    return "Structure-based reference"


def resolve_dossier_mode_for_surface(
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
) -> str:
    from src.services.dossier_mode import resolve_dossier_mode

    return resolve_dossier_mode(
        unified_label=unified_label,
        load_phase=load_phase,
        partial=partial,
        failed_fetch=failed_fetch,
        instant_degraded=instant_degraded,
        brief_backed=brief_backed,
        research_only=research_only,
        has_quote=has_quote,
        pending_calibration=pending_calibration,
        rr_unavailable=rr_unavailable,
    )


def dossier_confirm_only_strip() -> str:
    from src.services.dossier_mode import DOSSIER_CONFIRM_ONLY_STRIP

    return DOSSIER_CONFIRM_ONLY_STRIP


def dossier_structure_snapshot_title() -> str:
    from src.services.dossier_mode import STRUCTURE_SNAPSHOT_TITLE

    return STRUCTURE_SNAPSHOT_TITLE


def dossier_structure_level_label(field: str, *, mode: str = "structure_review_only") -> str:
    from src.services.dossier_mode import structure_level_label

    return structure_level_label(field, mode=mode)


def dossier_paper_draft_disabled_copy() -> str:
    from src.services.dossier_mode import PAPER_DRAFT_DISABLED_COPY

    return PAPER_DRAFT_DISABLED_COPY


def dossier_monitor_rule_button() -> str:
    from src.services.dossier_mode import MONITOR_RULE_BUTTON

    return MONITOR_RULE_BUTTON


def dossier_monitor_rule_hint() -> str:
    from src.services.dossier_mode import MONITOR_RULE_HINT

    return MONITOR_RULE_HINT


def dossier_lagged_context_note() -> str:
    from src.services.dossier_mode import LAGGED_CONTEXT_COLLAPSED_NOTE

    return LAGGED_CONTEXT_COLLAPSED_NOTE


def ai_reason_code_line(code: Optional[Dict[str, Any]] = None) -> str:
    """Single AI reason code — monitor-only explainer."""
    c = code or {}
    msg = str(c.get("message") or "").strip()
    if not msg:
        return "AI context — explanatory only, not deploy authority"
    return f"{msg} — monitor only"


def regime_stack_strip_line(summary: Optional[Dict[str, Any]] = None) -> str:
    """Compact regime stack copy for Today strip."""
    s = summary or {}
    line = str(s.get("strip_line") or "").strip()
    if not line:
        return "Regime stack unavailable — MOCK/DEGRADED"
    if s.get("degraded") and "MOCK" not in line.upper():
        line = f"MOCK/DEGRADED · {line}"
    return f"{line} — monitor only, not deploy"


def allocator_stance_hint(stance: Optional[Dict[str, Any]] = None) -> str:
    a = stance or {}
    sug = str(a.get("suggestion") or "").strip()
    if sug:
        return sug
    route = a.get("routing") or {}
    strongest = (route.get("strongest") or {}).get("name") or "—"
    weakest = (route.get("weakest") or {}).get("name") or "—"
    return f"Quant hint: strongest sleeve {strongest} · weakest {weakest} (not a trade route)"


def ai_contradiction_dossier_line(hint: str = "", *, degraded: bool = False) -> str:
    text = str(hint or "").strip()
    if not text:
        return ""
    if degraded and "MOCK" not in text.upper():
        text = f"{text} — MOCK/DEGRADED"
    return f"{text} — confirm-only, not deploy authority"


def typed_freshness_strip_line(truth: Optional[Dict[str, Any]] = None) -> str:
    """Scoped freshness strip — one line per subsystem, no FRESH+STALE mix."""
    from src.services.system_truth import typed_freshness_display

    return typed_freshness_display(truth or {})


def system_truth_line(truth: Optional[Dict[str, Any]] = None) -> str:
    """Header / mission parity line — typed freshness display."""
    from src.services.system_truth import system_truth_line as _line

    return _line(truth)


def global_truth_strip(truth: Optional[Dict[str, Any]] = None) -> str:
    """Canonical scoped freshness strip — no unscoped DATA FRESH/STALE."""
    from src.services.system_truth import format_global_truth_strip

    t = truth or {}
    if t.get("truth_strip"):
        return str(t["truth_strip"])
    return format_global_truth_strip(t)


def operator_block_for_page(
    truth: Optional[Dict[str, Any]] = None,
    *,
    page: str = "dashboard",
    operator_blocks: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shared operator block for surface helpers."""
    from src.services.operator_surface import build_operator_block

    blocks = operator_blocks or {}
    if page in blocks and isinstance(blocks[page], dict):
        return blocks[page]
    if truth and isinstance(truth.get("operator_block"), dict) and page == "dashboard":
        return truth["operator_block"]
    return build_operator_block(truth, page)


def playbook_qualification_funnel_line(funnel: Optional[Dict[str, Any]] = None) -> str:
    """Playbook funnel strip — setup-qualified vs deploy-qualified."""
    f = funnel or {}
    line = str(f.get("qualification_line") or "").strip()
    if line:
        return line
    from src.services.decision_truth_model import format_qualification_funnel_line

    return format_qualification_funnel_line(
        setup_qualified=int(f.get("setup_qualified_setups") or f.get("watch_qualified_setups") or 0),
        trade_qualified=int(f.get("trade_qualified_setups") or 0),
        execution_qualified=int(f.get("execution_qualified_setups") or 0),
        deploy_qualified=int(f.get("deploy_qualified_setups") or 0),
    )
