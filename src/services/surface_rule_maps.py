"""
Unified surface rule maps — tab → authority mode, IDOS posture, research contract overlays.

Canonical tab/surface definitions live in surface_authority.py; this module adds
IDOS + research-contract overlays consumed by research_safety and tests.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List

from src.services.surface_authority import (
    AUTHORITY_OPS,
    AUTHORITY_RESEARCH,
    SURFACE_MODES,
    TAB_ID_ALIASES,
    TAB_SURFACE_MAP,
    _HEADER_BASE,
    resolve_surface_mode,
)

UI_TAB_ALIASES: Dict[str, str] = dict(TAB_ID_ALIASES)

UI_SURFACE_MODES: Dict[str, str] = dict(SURFACE_MODES)

SURFACE_MODE_BY_TAB: Dict[str, str] = {
    k: SURFACE_MODES[k]
    for k in TAB_SURFACE_MAP
    if k in SURFACE_MODES
}

RESEARCH_ONLY_SURFACE_KEYS: FrozenSet[str] = frozenset(
    {
        "discovery",
        "dossier",
        "funds",
        "rs",
        "notrade",
        "btlab",
        "command",
        "strategy_lab",
        "agent",
        "shadow",
        "reports",
    }
)

IDOS_BY_SURFACE_MODE: Dict[str, Dict[str, str]] = {
    "dashboard_core": {
        "know": "Today's tradeability and regime gate",
        "believe": "Board + data freshness when green",
        "doubt": "Single-name scores before gate",
        "act": "Size only when gate + execution align",
    },
    "playbook_core": {
        "know": "Ranked actions and execution_ready flags",
        "believe": "Entry/stop/target when complete",
        "doubt": "Fallback / compressed board modes",
        "act": "Dashboard cross-check then IBKR",
    },
    "strategy_lab_research": {
        "know": "Research-only; today's Dashboard gate still rules",
        "believe": "Backtest + benchmark vs SPY",
        "doubt": "Non-PIT data unless as_of set",
        "act": "Send to Playbook — never auto-deploy",
    },
    "agent_monitoring": {
        "know": "Alerts are monitoring, not orders",
        "believe": "Linked ticker context",
        "doubt": "After-hours / stale quotes",
        "act": "Playbook → Dossier before size",
    },
    "shadow_diagnostic": {
        "know": "Paper path vs rule path",
        "believe": "Closed trades journal",
        "doubt": "Local book ≠ broker truth",
        "act": "Improve watch rules; no deploy",
    },
    "reports_library": {
        "know": "Historical research artifacts",
        "believe": "Validation metrics in export",
        "doubt": "Snapshot age",
        "act": "Playbook review if acting",
    },
    "guide_reference": {
        "know": "Reference manual only",
        "believe": "Workflow order",
        "doubt": "N/A — no live evaluation",
        "act": "Open Dashboard for live gate",
    },
}

RESEARCH_CONTRACT_BY_SURFACE: Dict[str, Dict[str, Any]] = {
    "strategy-lab": {
        "pipeline_stops_at": "playbook_review",
        "idos": IDOS_BY_SURFACE_MODE["strategy_lab_research"],
    },
    "strategy_lab": {
        "pipeline_stops_at": "playbook_review",
        "idos": IDOS_BY_SURFACE_MODE["strategy_lab_research"],
    },
    "agent": {
        "pipeline_stops_at": "playbook_review",
        "idos": IDOS_BY_SURFACE_MODE["agent_monitoring"],
    },
    "shadow": {
        "pipeline_stops_at": "journal_only",
        "idos": IDOS_BY_SURFACE_MODE["shadow_diagnostic"],
    },
    "reports": {
        "pipeline_stops_at": "export_only",
        "idos": IDOS_BY_SURFACE_MODE["reports_library"],
    },
    "research": {
        "pipeline_stops_at": "watch_rule_or_playbook_review",
        "idos": IDOS_BY_SURFACE_MODE["strategy_lab_research"],
    },
}


def canonical_tab(ui_tab: str) -> str:
    return UI_TAB_ALIASES.get(ui_tab, ui_tab)


def surface_mode_for_ui_tab(ui_tab: str) -> str:
    return resolve_surface_mode(ui_tab)


def all_required_surface_modes() -> List[str]:
    return sorted(set(_HEADER_BASE.keys()))


def research_overlay_for_surface(surface: str) -> Dict[str, Any]:
    key = str(surface or "research").strip()
    return (
        RESEARCH_CONTRACT_BY_SURFACE.get(key)
        or RESEARCH_CONTRACT_BY_SURFACE.get(canonical_tab(key))
        or RESEARCH_CONTRACT_BY_SURFACE["research"]
    )
