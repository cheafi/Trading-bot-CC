"""
Portfolio / Risk authority modes — broker truth, capacity, and capital-action gating.

Modes: broker_synced_live | manual_book | demo_sample | unavailable
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from src.services.authority_engine import (
    allowed_line,
    blocked_line,
    deploy_authority_tier,
    next_action,
    primary_operator_state,
    valid_candidates_line,
    why_lines,
)

PortfolioRiskMode = Literal[
    "broker_synced_live",
    "manual_book",
    "demo_sample",
    "unavailable",
]

_DEMO_SOURCES = frozenset({"demo", "demo-seed", "demo_seed", "sample", "mock"})
_MANUAL_SOURCES = frozenset({"manual", "local", ""})

RISK_REVIEW_ONLY = "Risk review only — no deploy authority from portfolio capacity"
BROKER_TRUTH_UNAVAILABLE = "Broker truth unavailable — reconcile before capital actions"
BROKER_TRUTH_REVIEW_ONLY = (
    "Broker truth unavailable · Risk review only until sync"
)
CAPITAL_QUEUE_DISABLED = "Capital action queue disabled — risk review only"
DEMO_BOOK_LABEL = "Demo / sample book — illustrative only, not broker truth"
HISTORICAL_JOURNAL_NOTE = "Learning only · not broker truth"


def _book_source(source: str) -> str:
    return str(source or "manual").lower().strip()


def resolve_portfolio_risk_mode(
    *,
    positions: Optional[List[Dict[str, Any]]] = None,
    source: str = "manual",
    execution_readiness: Optional[Dict[str, Any]] = None,
    ibkr_linkage: Optional[Dict[str, Any]] = None,
    system_truth: Optional[Dict[str, Any]] = None,
    fetch_failed: bool = False,
) -> Dict[str, Any]:
    """Resolve portfolio book mode and deploy/capacity authority."""
    pos = list(positions or [])
    ex = execution_readiness or {}
    link = ibkr_linkage or {}
    truth = dict(system_truth or {})
    src = _book_source(source)

    if fetch_failed and not pos:
        mode: PortfolioRiskMode = "unavailable"
    elif src in _DEMO_SOURCES or any(
        _book_source(str(p.get("source") or "")) in _DEMO_SOURCES for p in pos
    ):
        mode = "demo_sample"
    elif link.get("broker_truth") or (
        bool(ex.get("broker_connected"))
        and bool(ex.get("portfolio_synced"))
        and src == "ibkr"
    ):
        mode = "broker_synced_live"
    elif pos:
        mode = "manual_book"
    else:
        mode = "unavailable"

    broker_connected = bool(ex.get("broker_connected") or link.get("broker_connected"))
    broker_truth = bool(link.get("broker_truth"))
    portfolio_synced = bool(ex.get("portfolio_synced")) or broker_truth

    blockers: List[str] = []
    if mode == "demo_sample":
        blockers.append("demo sample book")
    if mode == "unavailable":
        blockers.append("portfolio unavailable")
    if not broker_connected:
        blockers.append("broker offline")
    if not portfolio_synced and mode != "demo_sample":
        blockers.append("portfolio not synced")
    if not broker_truth and mode == "manual_book":
        blockers.append("local book only")

    tier = deploy_authority_tier(truth)
    deploy_auth = tier == "allowed" and bool(truth.get("deploy_authority"))
    if not deploy_auth:
        blockers.append("deploy authority blocked")
    if str(truth.get("brief_freshness") or "").lower() == "expired":
        blockers.append("brief expired")
    if str(truth.get("ranked_board_freshness") or "").lower() in (
        "stale",
        "fallback",
        "unavailable",
    ):
        blockers.append("board stale")
    if str(truth.get("market_data_freshness") or "").lower() in ("stale", "unavailable"):
        blockers.append("data stale")

    risk_review_only = bool(blockers) or mode in ("demo_sample", "manual_book", "unavailable")
    may_authorize_deploy = (
        mode == "broker_synced_live"
        and broker_truth
        and deploy_auth
        and not blockers
    )
    capital_action_queue_enabled = may_authorize_deploy
    risk_capacity_authority = "full" if may_authorize_deploy else "none"

    book_label = {
        "broker_synced_live": "Broker-synced live book",
        "manual_book": "Manual book — not broker truth",
        "demo_sample": DEMO_BOOK_LABEL,
        "unavailable": "Portfolio unavailable",
    }.get(mode, "Portfolio")

    return {
        "mode": mode,
        "book_label": book_label,
        "broker_truth": broker_truth,
        "broker_connected": broker_connected,
        "portfolio_synced": portfolio_synced,
        "risk_review_only": risk_review_only,
        "may_authorize_deploy": may_authorize_deploy,
        "risk_capacity_authority": risk_capacity_authority,
        "capital_action_queue_enabled": capital_action_queue_enabled,
        "blockers": blockers,
        "strip_line": (
            f"{book_label} · risk capacity {risk_capacity_authority}"
            + (" — " + RISK_REVIEW_ONLY if risk_review_only else "")
        ),
        "broker_truth_note": (
            BROKER_TRUTH_UNAVAILABLE
            if not broker_truth
            else "Broker is source of truth"
        ),
        "capital_queue_note": (
            CAPITAL_QUEUE_DISABLED if not capital_action_queue_enabled else None
        ),
        "demo_watermark": mode == "demo_sample",
    }


def build_portfolio_risk_view_model(
    portfolio_mode: Optional[Dict[str, Any]] = None,
    *,
    positions: Optional[List[Dict[str, Any]]] = None,
    ibkr_linkage: Optional[Dict[str, Any]] = None,
    critical_risk_event: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """UI contract for Portfolio tab — capacity, sleeves, demo tools, compression."""
    pm = dict(portfolio_mode or {})
    link = dict(ibkr_linkage or {})
    pos = list(positions or [])
    cre = dict(critical_risk_event or {})

    mode = pm.get("mode") or "unavailable"
    review_only = bool(pm.get("risk_review_only"))
    capital_enabled = bool(pm.get("capital_action_queue_enabled"))
    broker_truth = bool(pm.get("broker_truth") or link.get("broker_truth"))
    broker_connected = bool(pm.get("broker_connected") or link.get("broker_connected"))
    broker_offline = not broker_connected
    local_only = link.get("sync_quality") == "local_only" or mode == "manual_book"
    no_positions = len(pos) == 0

    risk_capacity_authority = (
        pm.get("risk_capacity_authority") or "none"
        if review_only or not capital_enabled
        else "full"
    )
    sleeve_authority = "research_only" if review_only else "live"
    live_eligibility = 0 if review_only else 100

    show_critical = bool(cre.get("active"))
    broker_truth_banner_active = (
        not broker_truth or broker_offline or local_only or mode in ("manual_book", "unavailable")
    ) and not show_critical

    book_scope = {
        "broker_synced_live": "Book · Broker-synced",
        "manual_book": "Book · Local-only",
        "demo_sample": "Book · Demo sample",
        "unavailable": "Book · Unavailable",
    }.get(mode, "Book · Unavailable")
    broker_scope = (
        "Broker · Synced"
        if broker_truth and broker_connected
        else "Broker · Offline"
        if broker_offline
        else "Broker · Not confirmed"
    )

    return {
        "mode": mode,
        "risk_capacity_authority": risk_capacity_authority,
        "capital_action_enabled": capital_enabled and not review_only,
        "sleeve_authority": sleeve_authority,
        "live_allocation_eligibility_pct": live_eligibility,
        "show_sleeve_research_default": not review_only and capital_enabled,
        "show_demo_tools_default": False,
        "show_historical_journal_default": False,
        "default_details_collapsed": review_only or not capital_enabled,
        "show_critical_risk_event": show_critical,
        "broker_truth_banner_active": broker_truth_banner_active,
        "broker_truth_banner": (
            BROKER_TRUTH_REVIEW_ONLY
            if broker_truth_banner_active
            else None
        ),
        "historical_journal_note": HISTORICAL_JOURNAL_NOTE,
        "book_scope_label": book_scope,
        "broker_scope_label": broker_scope,
        "scoped_truth_strip": f"{book_scope} · {broker_scope}",
        "collapse_allocation_bands": review_only or not broker_truth or no_positions,
        "collapse_operating_discipline": review_only,
        "manual_add_label": "Add manual placeholder",
        "risk_review_only": review_only,
    }


def build_portfolio_operator_block(
    truth: Optional[Dict[str, Any]] = None,
    *,
    portfolio_mode: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """NOW / WHY / ALLOWED / BLOCKED / VALIDATION / NEXT for Portfolio tab."""
    t = dict(truth or {})
    pm = dict(portfolio_mode or {})
    posture = primary_operator_state(t)
    why_parts = why_lines(t)
    pf_blockers = list(pm.get("blockers") or [])
    why = " · ".join(pf_blockers) if pf_blockers else (
        " + ".join(why_parts) if why_parts else str(t.get("primary_blocker") or "risk review only")
    )

    if pm.get("risk_review_only"):
        now = RISK_REVIEW_ONLY
        allowed = "risk review, stop coverage, concentration diagnostics"
        blocked = blocked_line(t) or "no sizing · no handoff · no deploy from portfolio capacity"
    else:
        now = posture.get("now") or posture.get("primary") or "MONITOR ONLY"
        allowed = allowed_line(t)
        blocked = blocked_line(t)

    validation = valid_candidates_line(t)
    nxt = next_action(t)
    if pm.get("mode") == "demo_sample":
        nxt = "do not treat demo book as live — connect broker for truth"
    elif not pm.get("broker_truth"):
        nxt = "repair IBKR / reconcile local book before capital actions"

    return {
        "now": now,
        "why": why,
        "allowed": allowed,
        "blocked": blocked,
        "validation": validation,
        "next": nxt,
        "details_collapsed": True,
        "portfolio_mode": pm.get("mode") or "unavailable",
        "risk_capacity_authority": pm.get("risk_capacity_authority") or "none",
        "capital_action_queue_enabled": bool(pm.get("capital_action_queue_enabled")),
    }


def sanitize_portfolio_action_copy(
    text: str,
    *,
    portfolio_mode: Optional[Dict[str, Any]] = None,
) -> str:
    """Strip deploy/sizing language when portfolio capacity cannot authorize."""
    pm = portfolio_mode or {}
    if pm.get("capital_action_queue_enabled"):
        return str(text or "")
    out = str(text or "")
    for phrase, repl in (
        ("Deploy", "Review"),
        ("deploy", "review"),
        ("ADD", "MONITOR"),
        ("TRIM URGENT", "REVIEW CONCENTRATION"),
        ("half size", "risk review"),
        ("sizing", "risk review"),
    ):
        out = out.replace(phrase, repl)
    return out
