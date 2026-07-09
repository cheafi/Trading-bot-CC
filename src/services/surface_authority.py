"""
Surface authority labels — research ≠ permission, connected ≠ synced.

Use across tabs so operators know what each page may and may not authorize.

Root cause (2026-06): PM strip reused decisionHub / today7 playbook chips on
every tab, so Idea QCOM · REDUCE · Avoid 1 appeared on Guide, Funds, Flow, etc.
Fix: SURFACE_MODES + build_header_summary — exactly one surface owns header copy.
See docs/SURFACE_AUTHORITY_REFACTOR.md
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.fetch_surface_state import (
    STATE_EXECUTION_BLOCKED,
    STATE_FAILED_FETCH,
    STATE_FALLBACK,
    STATE_LOADING,
    STATE_MOCK_ONLY,
    STATE_NOT_AUTHORITATIVE,
    STATE_OK,
    STATE_PARTIAL,
    STATE_RESEARCH_ONLY,
    STATE_STALE,
    describe_dossier_fetch_state,
    describe_fetch_state,
    normalize_fetch_state,
)

AUTHORITY_DEPLOY = "deploy_authority"
AUTHORITY_PILOT = "pilot_only"
AUTHORITY_RESEARCH = "research_only"
AUTHORITY_CONFIRMATION = "confirmation_only"
AUTHORITY_OPS = "ops_probe"
AUTHORITY_BLOCKED = "blocked"
AUTHORITY_SUSPENDED = "suspended"

# Single source for Guide tab header copy (trust strip + Alpine bindings).
GUIDE_AUTHORITY_STRIP = "GUIDE MODE · Reference only · Decision surfaces suspended"
GUIDE_STATUS_NOTE = "Runtime not evaluated here"

AUTHORITY_LABELS: Dict[str, str] = {
    AUTHORITY_DEPLOY: "Deploy authority — gated board may permit sizing",
    AUTHORITY_PILOT: "Pilot only — half size, stop required",
    AUTHORITY_RESEARCH: "Research only — informs, does not authorize trades",
    AUTHORITY_CONFIRMATION: "Confirmation only — must align with board + regime",
    AUTHORITY_OPS: "Ops / connectivity — not investable signal",
    AUTHORITY_BLOCKED: "Blocked — page gate or broker prevents deploy",
    AUTHORITY_SUSPENDED: "Guide mode — decision surfaces suspended; reference only",
}

TAB_SURFACE_MAP: Dict[str, Dict[str, str]] = {
    "today": {
        "surface": "Dashboard",
        "default_authority": AUTHORITY_DEPLOY,
        "short": "Board gate + today's decision",
    },
    "playbook": {
        "surface": "Playbook",
        "default_authority": AUTHORITY_DEPLOY,
        "short": "Ranked opportunities — deploy when board_mode full",
    },
    "dossier": {
        "surface": "Dossier",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Single-name research — not standalone permission",
    },
    "portfolio": {
        "surface": "Portfolio",
        "default_authority": AUTHORITY_DEPLOY,
        "short": "Book construction + risk hierarchy",
    },
    "discovery": {
        "surface": "Discovery",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Universe scan — funnel input only",
    },
    "flow": {
        "surface": "Flow",
        "default_authority": AUTHORITY_CONFIRMATION,
        "short": "Options flow — narrative support, not trigger",
    },
    "funds": {
        "surface": "Funds",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Model evidence — backtest ≠ live track record",
    },
    "ibkr": {
        "surface": "IBKR",
        "default_authority": AUTHORITY_OPS,
        "short": "Broker health — critical checks block execution",
    },
    "ops": {
        "surface": "Ops",
        "default_authority": AUTHORITY_OPS,
        "short": "Runtime vs probe — workflow ≠ capital permission",
    },
    "rs": {
        "surface": "RS",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Relative strength — funnel input only",
    },
    "command": {
        "surface": "Command",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Advanced aggregate — not deploy gate",
        "hide_from_primary_nav": True,
    },
    "notrade": {
        "surface": "Rejections",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Audit trail — why names failed gates",
    },
    "btlab": {
        "surface": "Backtest Lab",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Walk-forward research — not live track record",
    },
    "stratlab": {
        "surface": "Strategy Lab",
        "default_authority": AUTHORITY_RESEARCH,
        "short": "Strategy calibration — research only, not deploy authority",
    },
    "guide": {
        "surface": "Guide",
        "default_authority": AUTHORITY_SUSPENDED,
        "short": "Reference only · Decision surfaces suspended",
    },
}

# UI tab ids in index.html → canonical surface_authority keys
TAB_ID_ALIASES: Dict[str, str] = {
    "signals": "playbook",
    "scanners": "discovery",
    "today": "today",
    "stock-intel": "dossier",
    "rejections": "notrade",
    "backtest": "btlab",
}


def resolve_authority(
    tab: str,
    *,
    tradeability: Optional[str] = None,
    board_mode: Optional[str] = None,
    ibkr_blocked: bool = False,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Resolve effective authority for a tab given live context."""
    meta = TAB_SURFACE_MAP.get(tab, TAB_SURFACE_MAP["dossier"])
    if tab == "guide":
        return {
            "tab": tab,
            "surface": meta["surface"],
            "authority": AUTHORITY_SUSPENDED,
            "authority_label": AUTHORITY_LABELS[AUTHORITY_SUSPENDED],
            "short": meta["short"],
            "reasons": ["Guide mode suspends active decision language"],
            "badge": "GUIDE MODE",
        }

    authority = meta["default_authority"]
    reasons: list[str] = []

    tb = (tradeability or "").upper()
    if tab in ("today", "playbook", "portfolio"):
        if ibkr_blocked:
            authority = AUTHORITY_BLOCKED
            reasons.append("Critical IBKR check failed")
        elif tb in ("NO_TRADE", "WAIT"):
            authority = AUTHORITY_RESEARCH if tab == "playbook" else AUTHORITY_BLOCKED
            reasons.append(f"Board tradeability {tb}")
        elif deployable_count < 1:
            authority = AUTHORITY_PILOT if tb == "SELECTIVE" else AUTHORITY_RESEARCH
            reasons.append("No execution-ready names")
        elif deployable_count >= 1 and tb in ("TRADE", "STRONG_TRADE"):
            authority = AUTHORITY_DEPLOY

    if tab == "playbook" and board_mode in ("compressed", "emergency", "fallback"):
        authority = AUTHORITY_RESEARCH
        reasons.append(f"Board mode {board_mode} — reduced deploy authority")

    if tab == "discovery":
        authority = AUTHORITY_RESEARCH
        if tb in ("NO_TRADE", "WAIT"):
            reasons.append(f"Board tradeability {tb} — discovery is research-only")
        if deployable_count < 1:
            reasons.append("No execution-ready names — monitor candidates only")
        if ibkr_blocked:
            reasons.append("Broker blocked — discovery cannot authorize deploy")

    if tab == "flow":
        authority = AUTHORITY_CONFIRMATION
        reasons.append("Flow never authorizes deploy alone")

    return {
        "tab": tab,
        "surface": meta["surface"],
        "authority": authority,
        "authority_label": AUTHORITY_LABELS.get(authority, authority),
        "short": meta["short"],
        "reasons": reasons,
        "badge": _authority_badge(authority),
    }


def _authority_badge(authority: str) -> str:
    badges = {
        AUTHORITY_DEPLOY: "DEPLOY OK",
        AUTHORITY_PILOT: "PILOT ONLY",
        AUTHORITY_RESEARCH: "RESEARCH ONLY",
        AUTHORITY_CONFIRMATION: "CONFIRMATION",
        AUTHORITY_OPS: "OPS / CONNECTIVITY",
        AUTHORITY_BLOCKED: "NO DEPLOY AUTHORITY",
        AUTHORITY_SUSPENDED: "GUIDE MODE",
    }
    return badges.get(authority, authority.upper())


def _canonical_tab(tab: str) -> str:
    return TAB_ID_ALIASES.get(tab, tab)


def authority_strip_for_today(
    *,
    tradeability: str,
    board_mode: Optional[str] = None,
    ibkr_connected: bool = False,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Dashboard + playbook header authority chips."""
    tabs = ("today", "playbook", "dossier", "portfolio", "discovery", "flow", "funds", "ibkr", "ops")
    return {
        "surfaces": [
            resolve_authority(
                t,
                tradeability=tradeability,
                board_mode=board_mode if t == "playbook" else None,
                ibkr_blocked=not ibkr_connected and t in ("today", "playbook", "portfolio"),
                deployable_count=deployable_count,
            )
            for t in tabs
        ],
        "principle": "Research relevance ≠ deploy permission",
    }


def is_decision_surface_suspended(ui_tab: str) -> bool:
    """True when UI tab is Guide — decision language must not render."""
    return _canonical_tab(ui_tab) == "guide"


def guide_mode_strip(*, engine_running: bool = False, display_mode: str = "PAPER") -> Dict[str, Any]:
    """Passive header payload when Guide tab is active — reference surface, not runtime proof."""
    mode = (display_mode or "PAPER").upper()
    return {
        "guide_mode": True,
        "badge": "GUIDE MODE",
        "strip": GUIDE_AUTHORITY_STRIP,
        "short": "Reference only · Decision surfaces suspended",
        "authority": AUTHORITY_SUSPENDED,
        "authority_label": AUTHORITY_LABELS[AUTHORITY_SUSPENDED],
        "engine_on": engine_running,
        "display_mode": mode,
        "mode_label": f"Mode · {mode}",
        "status_note": GUIDE_STATUS_NOTE,
        "principle": "Fresh output beats pretty output",
    }


# UI tab id → canonical surface mode (only one mode controls header summary)
SURFACE_MODES: Dict[str, str] = {
    "today": "dashboard_core",
    "signals": "playbook_core",
    "scanners": "discovery_research",
    "dossier": "dossier_research",
    "stock-intel": "dossier_research",
    "portfolio": "portfolio_manual",
    "funds": "funds_research",
    "flow": "flow_supporting",
    "rs": "rs_supporting",
    "notrade": "rejections_diagnostic",
    "rejections": "rejections_diagnostic",
    "guide": "guide_reference",
    "ops": "ops_diagnostic",
    "ibkr": "ibkr_execution",
    "btlab": "backtest_research",
    "backtest": "backtest_research",
    "stratlab": "strategy_lab_research",
    "command": "command_research",
}

# Tabs reachable via More menu / deep link — excluded from mobile primary nav
HIDDEN_PRIMARY_NAV = frozenset({"command"})

# Surfaces that may show deploy / idea chips from board state
_DECISION_CHIP_SURFACES = frozenset({"dashboard_core", "playbook_core"})

_HEADER_BASE: Dict[str, Dict[str, str]] = {
    "dashboard_core": {
        "badge": "BOARD GATE",
        "title": "Dashboard — today's deploy posture",
        "explanation": "Regime + board gate + deploy posture. This surface may permit sizing when tradeability and execution align.",
        "next_action": "Read tradeability first, then top ranked — patience beats participation on WAIT days.",
    },
    "playbook_core": {
        "badge": "DEPLOY BOARD",
        "title": "Playbook — ranked opportunities",
        "explanation": "Ranked board — deploy when board_mode is full and names are execution-ready.",
        "next_action": "Filter to execution-ready rows; cross-check Dashboard gate before sizing.",
    },
    "discovery_research": {
        "badge": "RESEARCH ONLY",
        "title": "Discovery — universe scan",
        "explanation": "Scanner funnel input only — hits here do not authorize trades alone.",
        "next_action": "Promote interesting names to Playbook or Dossier for validation.",
    },
    "dossier_research": {
        "badge": "RESEARCH ONLY",
        "title": "Dossier — single-name research",
        "explanation": "Per-ticker evidence and verdict — not standalone deploy permission.",
        "next_action": "Confirm board posture on Dashboard before acting on dossier verdict.",
    },
    "portfolio_manual": {
        "badge": "BOOK CONSTRUCTION",
        "title": "Portfolio — book & risk hierarchy",
        "explanation": "Manual book construction, heat, correlation, and risk — overrides come from you, not the scanner.",
        "next_action": "Reconcile manual book vs IBKR before rebalancing.",
    },
    "funds_research": {
        "badge": "MODEL EVIDENCE",
        "title": "Funds — sleeve research",
        "explanation": "Model sleeves and backtest evidence — backtest ≠ live track record.",
        "next_action": "Treat sleeve gates as research; live validation required before capital.",
    },
    "flow_supporting": {
        "badge": "CONFIRMATION ONLY",
        "title": "Flow — options narrative overlay",
        "explanation": "Options flow supports names already validated elsewhere — never a standalone entry trigger.",
        "next_action": "Use flow to prioritize watchlist; Playbook + Dossier must agree first.",
    },
    "rs_supporting": {
        "badge": "RESEARCH ONLY",
        "title": "Relative strength — Discovery funnel input",
        "explanation": "Relative strength ranks funnel candidates — not deploy authority.",
        "next_action": "Cross-check sector regime and Playbook; promote via Discovery scanners.",
    },
    "command_research": {
        "badge": "RESEARCH ONLY",
        "title": "Command — advanced aggregate",
        "explanation": "Terminal aggregate view — deep decision dump, not a deploy gate.",
        "next_action": "Use Dashboard + Playbook for deploy authority; Command is diagnostic only.",
    },
    "guide_reference": {
        "badge": "GUIDE MODE",
        "title": "Guide — reference surface",
        "explanation": "Documentation and workflow reference — runtime not evaluated here.",
        "next_action": "Open Dashboard when ready to evaluate live board posture.",
    },
    "ops_diagnostic": {
        "badge": "OPS / CONNECTIVITY",
        "title": "Ops — runtime diagnostics",
        "explanation": "Engine health, providers, and probes — workflow status ≠ capital permission.",
        "next_action": "Fix stale providers or breaker before returning to Dashboard.",
    },
    "ibkr_execution": {
        "badge": "EXECUTION GATE",
        "title": "IBKR — broker handoff",
        "explanation": "Connectivity, session, brackets, and order readiness — critical failures block execution.",
        "next_action": "Connect gateway and confirm session_usable before live orders.",
    },
    "rejections_diagnostic": {
        "badge": "AUDIT TRAIL",
        "title": "Rejections — gate failure log",
        "explanation": "Why names failed gates — diagnostic audit, not deploy permission.",
        "next_action": "Use rejections to refine watchlist; return to Playbook for actionable board.",
    },
    "backtest_research": {
        "badge": "BACKTEST ONLY",
        "title": "Backtest Lab — walk-forward research",
        "explanation": "Walk-forward and attribution research — backtest ≠ live track record.",
        "next_action": "Treat unstable walk-forward as lower trust, not higher conviction.",
    },
    "strategy_lab_research": {
        "badge": "RESEARCH ONLY",
        "title": "Strategy Lab — calibration sandbox",
        "explanation": "Offline draft and validation research — not deployment authority.",
        "next_action": "Repair live data before validation; board gate still required for promotion.",
    },
}


def resolve_surface_mode(ui_tab: str) -> str:
    """Map Alpine tab id to canonical surface mode."""
    canonical = _canonical_tab(ui_tab)
    return SURFACE_MODES.get(canonical, SURFACE_MODES.get(ui_tab, "discovery_research"))


def is_hidden_from_primary_nav(ui_tab: str) -> bool:
    """True when tab must not appear in mobile bottom nav."""
    return _canonical_tab(ui_tab) in HIDDEN_PRIMARY_NAV


def surface_shows_decision_chips(surface_mode: str) -> bool:
    return surface_mode in _DECISION_CHIP_SURFACES


def build_header_summary(
    surface_mode: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build page-authority-aware header copy for the active surface.

    context keys (all optional):
      fetch_state, tradeability, regime_trend, deploy_posture, best_idea_ticker,
      deploy_label, avoid_count, ticker (dossier), loading, error, stale,
      fallback, mock_only, execution_blocked, chips (list of {label, class})
    """
    ctx = dict(context or {})
    base = dict(_HEADER_BASE.get(surface_mode, _HEADER_BASE["discovery_research"]))
    fetch_state = ctx.get("fetch_state") or normalize_fetch_state(
        loading=bool(ctx.get("loading")),
        error=ctx.get("error"),
        stale=bool(ctx.get("stale")),
        fallback=bool(ctx.get("fallback")),
        mock_only=bool(ctx.get("mock_only")),
        execution_blocked=bool(ctx.get("execution_blocked")),
        empty=bool(ctx.get("empty")),
    )
    if (
        surface_mode not in _DECISION_CHIP_SURFACES
        and fetch_state == STATE_OK
        and surface_mode != "guide_reference"
    ):
        fetch_state = STATE_NOT_AUTHORITATIVE
    fetch_copy = describe_fetch_state(
        fetch_state,
        detail=ctx.get("fetch_detail"),
        next_action=ctx.get("fetch_next_action"),
    )
    if surface_mode == "dossier_research" and fetch_state in (
        STATE_FAILED_FETCH,
        STATE_LOADING,
        STATE_STALE,
        STATE_PARTIAL,
    ):
        fetch_copy = describe_dossier_fetch_state(
            fetch_state,
            detail=ctx.get("fetch_detail") or ctx.get("error"),
            service=ctx.get("dossier_service") or ctx.get("service"),
        )

    chips: List[Dict[str, str]] = []
    if surface_shows_decision_chips(surface_mode) and fetch_state in (
        STATE_OK,
        STATE_STALE,
        STATE_FALLBACK,
    ):
        if ctx.get("deploy_label"):
            chips.append({"label": str(ctx["deploy_label"]), "class": "deploy"})
        if ctx.get("best_idea_ticker"):
            chips.append(
                {
                    "label": f"Idea {ctx['best_idea_ticker']}",
                    "class": "idea",
                }
            )
        avoid_n = int(ctx.get("avoid_count") or 0)
        if avoid_n > 0:
            chips.append({"label": f"Avoid {avoid_n}", "class": "avoid"})
    elif surface_mode == "dossier_research" and ctx.get("ticker"):
        chips.append({"label": str(ctx["ticker"]).upper(), "class": "ticker"})
    elif surface_mode == "portfolio_manual" and ctx.get("position_count") is not None:
        chips.append(
            {
                "label": f"{ctx['position_count']} positions",
                "class": "book",
            }
        )
    elif surface_mode == "flow_supporting" and ctx.get("flow_count") is not None:
        chips.append({"label": f"Flow hits {ctx['flow_count']}", "class": "flow"})
    elif surface_mode == "ibkr_execution":
        label = ctx.get("ibkr_label") or "IBKR"
        chips.append({"label": str(label), "class": "ibkr"})

    extra = ctx.get("chips") or []
    if isinstance(extra, list):
        chips.extend(extra)

    regime = ctx.get("regime_trend")
    tradeability = ctx.get("tradeability")
    subtitle_parts = []
    if regime and tradeability:
        subtitle_parts.append(f"{regime} · {tradeability}")
    elif regime:
        subtitle_parts.append(str(regime))
    elif tradeability and surface_shows_decision_chips(surface_mode):
        subtitle_parts.append(str(tradeability))
    subtitle = " · ".join(subtitle_parts) if subtitle_parts else base["title"]

    return {
        "surface_mode": surface_mode,
        "badge": base["badge"]
        if surface_mode == "guide_reference"
        else (fetch_copy["badge"] if fetch_copy["badge"] else base["badge"]),
        "title": base["title"],
        "subtitle": subtitle,
        "explanation": fetch_copy["explanation"] or base["explanation"],
        "next_action": fetch_copy["next_action"] or base["next_action"],
        "fetch_state": fetch_state,
        "show_decision_chips": surface_shows_decision_chips(surface_mode)
        and fetch_state in (STATE_OK, STATE_STALE, STATE_FALLBACK),
        "show_regime_strip": surface_mode != "guide_reference",
        "chips": chips,
        "authority_badge": base["badge"],
    }


def header_summary_for_tab(
    ui_tab: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience: resolve surface mode from tab id then build summary."""
    mode = resolve_surface_mode(ui_tab)
    return build_header_summary(mode, context)


def build_header_summary_for_tab(
    active_tab: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Alias for header_summary_for_tab — activeTab + context API."""
    return header_summary_for_tab(active_tab, context)


def resolve_authority_for_ui_tab(
    ui_tab: str,
    *,
    tradeability: str,
    board_mode: Optional[str] = None,
    ibkr_connected: bool = False,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Resolve authority for an Alpine tab id (signals → playbook, etc.)."""
    canonical = _canonical_tab(ui_tab)
    return resolve_authority(
        canonical,
        tradeability=tradeability,
        board_mode=board_mode if canonical == "playbook" else None,
        ibkr_blocked=not ibkr_connected and canonical in ("today", "playbook", "portfolio"),
        deployable_count=deployable_count,
    )
