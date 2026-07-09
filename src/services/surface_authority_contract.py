"""
Surface authority contract — enforceable product law for all 16 operator surfaces.

SSOT for docs/SURFACE_AUTHORITY_CONTRACT.md, pytest, and verify scripts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Global banned phrases — must not appear in live runtime bindings (whitelist exceptions apply).
GLOBAL_BANNED_PHRASES: List[str] = [
    "TRADE LIST",
    "decision card",
    "PILOT = half-size",
    "pilot half-size",
    "taking a Pilot entry",
    "brief fallback",
    "Deploy gate open",
    "BOARD POSTURE TRADE",
    "Current: TRADE",
    "Active Fund Manager",
    "Max capital band",
    "Test deploy override",
    "ENGINE undefined",
    "DATA FRESH",
    "DATA STALE",
    "Freshness: live",
    "h.freshness||'live'",
    "ENGINE ON",
    "ENGINE UNKNOWN",
    "actionable in Discovery",
    "Seed Demo Book",
    "Closed-Trade Ledger",
    "CRITICAL RISK EVENT",
    "Method Not Allowed",
    "Active sleeves",
]

# Whitelist contexts where banned phrases may appear intentionally.
BANNED_PHRASE_WHITELIST: List[str] = [
    "test fixture",
    "sanitizer map key",
    "LEGACY_BANNED_DO_NOT_RENDER",
    "legacy anti-pattern",
    "Illustrative examples only",
    "Degraded — fallback watch",
    "removeTradeLanguageWhenBlocked",
    "BANNED_IN_RUNTIME",
    "GLOBAL_BANNED_PHRASES",
]

SURFACE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "guide": {
        "tab_id": "guide",
        "ui_label": "Guide",
        "surface_mode": "guide_reference",
        "authority": "suspended",
        "allowed": [
            "reference documentation",
            "workflow examples (illustrative)",
            "operator checklist",
        ],
        "blocked": [
            "live deploy authority",
            "runtime truth evaluation",
            "decision chips from board",
        ],
        "banned_phrases": ["TRADE LIST", "decision card", "pilot half-size"],
        "collapsed_sections": ["Layer 3 — Reference Manual"],
        "source_helper": "guide_mode_strip",
        "viewmodel": "guideStatusNote",
    },
    "today": {
        "tab_id": "today",
        "ui_label": "Dashboard",
        "surface_mode": "dashboard_core",
        "authority": "deploy_authority",
        "allowed": [
            "regime + board gate read",
            "deploy posture when tier allowed",
            "operator block NOW/WHY/ALLOWED/BLOCKED",
            "decision chips when fetch OK",
        ],
        "blocked": [
            "sizing when tier blocked",
            "deploy chips when IBKR critical fail",
            "raw tradeability bindings in trust strip",
        ],
        "banned_phrases": [
            "Deploy gate open",
            "Current: TRADE",
            "BOARD POSTURE TRADE",
            "x-text=\"today7.tradeability",
        ],
        "collapsed_sections": ["repair_priority details"],
        "source_helper": "build_operator_block",
        "viewmodel": "dashboardOperatorBlock",
    },
    "playbook": {
        "tab_id": "signals",
        "canonical_id": "playbook",
        "ui_label": "Playbook",
        "surface_mode": "playbook_core",
        "authority": "deploy_authority",
        "allowed": [
            "ranked board review",
            "qualification display via viewmodel",
            "pilot review when tier pilot_only",
            "deploy when board_mode full + execution-ready",
        ],
        "blocked": [
            "deploy when WAIT/NO_TRADE (research_only downgrade)",
            "raw canonicalRegimeLine in template",
            "Deploy gate open copy",
        ],
        "banned_phrases": [
            "Deploy gate open",
            "BOARD POSTURE TRADE",
            "Current: TRADE",
            "taking a Pilot entry",
            "PILOT = half-size",
        ],
        "collapsed_sections": ["legacy debate panels"],
        "source_helper": "playbookAuthorityViewModel",
        "viewmodel": "playbookOperatorView",
    },
    "discovery": {
        "tab_id": "scanners",
        "canonical_id": "discovery",
        "ui_label": "Discovery",
        "surface_mode": "discovery_research",
        "authority": "research_only",
        "allowed": [
            "scanner funnel input",
            "promote to Playbook/Dossier",
            "scoped scanner run label",
        ],
        "blocked": [
            "actionable deploy language",
            "unscoped freshness pills",
            "brief fallback in runtime",
        ],
        "banned_phrases": [
            "Freshness: live",
            "brief fallback",
            "ENGINE ON",
            "actionable in Discovery",
        ],
        "collapsed_sections": ["raw scanner JSON"],
        "source_helper": "build_research_surface_block",
        "viewmodel": "discoveryFunnelPanel",
    },
    "dossier": {
        "tab_id": "dossier",
        "ui_label": "Dossier",
        "surface_mode": "dossier_research",
        "authority": "research_only",
        "allowed": [
            "structure confirmation",
            "ticker chip header",
            "confirm-only when degraded",
            "monitor rule creation",
        ],
        "blocked": [
            "standalone deploy permission",
            "trade plan when confirm-only",
            "sizing guidance when blocked",
            "decision card framing",
        ],
        "banned_phrases": ["decision card", "TRADE LIST"],
        "collapsed_sections": [
            "trade plan panel when confirm-only",
            "lagged illustrative context",
        ],
        "source_helper": "resolve_dossier_mode",
        "viewmodel": "dossierRecoveryMode",
    },
    "portfolio": {
        "tab_id": "portfolio",
        "ui_label": "Portfolio",
        "surface_mode": "portfolio_manual",
        "authority": "deploy_authority",
        "allowed": [
            "book construction",
            "risk hierarchy review",
            "broker truth unavailable banner",
            "historical journal collapsed",
        ],
        "blocked": [
            "demo seed tools in default view",
            "critical risk event literal when inactive",
            "capital action when broker offline",
        ],
        "banned_phrases": [
            "Active sleeves",
            "Seed Demo Book",
            "Closed-Trade Ledger",
            "CRITICAL RISK EVENT",
            "Method Not Allowed",
        ],
        "collapsed_sections": [
            "Sleeve Research default",
            "Historical Journal default",
            "demo tools",
        ],
        "source_helper": "build_portfolio_risk_view_model",
        "viewmodel": "pfRiskVM",
    },
    "stratlab": {
        "tab_id": "stratlab",
        "ui_label": "Strategy Lab",
        "surface_mode": "strategy_lab_research",
        "authority": "research_only",
        "allowed": [
            "offline draft generation",
            "validation when scopes fresh",
            "committee review research path",
        ],
        "blocked": [
            "deploy authority",
            "Pine export until validation passes",
            "Playbook promotion when board stale",
        ],
        "banned_phrases": ["Deploy gate open", "Test deploy override"],
        "collapsed_sections": ["validation details when offline_draft_only"],
        "source_helper": "build_strategy_lab_page_state",
        "viewmodel": "strategyLabPageState",
    },
    "time_travel": {
        "tab_id": None,
        "ui_label": "Time Travel",
        "surface_mode": "replay_overlay",
        "authority": "suspended",
        "allowed": [
            "historical brief replay",
            "dashboard/playbook snapshot review",
            "dossier replay button",
        ],
        "blocked": [
            "live deploy authority",
            "treating replay as current truth",
            "IBKR handoff from replay",
        ],
        "banned_phrases": ["Deploy gate open", "Current: TRADE"],
        "collapsed_sections": [],
        "source_helper": "replayModeActive",
        "viewmodel": "ccReplayAsOf",
    },
    "funds": {
        "tab_id": "funds",
        "ui_label": "Funds",
        "surface_mode": "funds_research",
        "authority": "research_only",
        "allowed": ["sleeve research", "model evidence review"],
        "blocked": ["live allocation authority", "deploy chips"],
        "banned_phrases": ["Deploy gate open"],
        "collapsed_sections": ["backtest detail when stale"],
        "source_helper": "build_research_surface_block",
        "viewmodel": None,
    },
    "flow": {
        "tab_id": "flow",
        "ui_label": "Flow",
        "surface_mode": "flow_supporting",
        "authority": "confirmation_only",
        "allowed": ["options narrative overlay", "flow hit counts"],
        "blocked": ["standalone entry trigger", "deploy authority"],
        "banned_phrases": ["Deploy gate open"],
        "collapsed_sections": [],
        "source_helper": "build_research_surface_block",
        "viewmodel": None,
    },
    "rs": {
        "tab_id": "rs",
        "ui_label": "RS",
        "surface_mode": "rs_supporting",
        "authority": "research_only",
        "allowed": ["relative strength funnel input"],
        "blocked": ["deploy authority"],
        "banned_phrases": [],
        "collapsed_sections": [],
        "source_helper": "build_research_surface_block",
        "viewmodel": None,
    },
    "command": {
        "tab_id": "command",
        "ui_label": "Command",
        "surface_mode": "command_research",
        "authority": "research_only",
        "allowed": [
            "advanced aggregate diagnostic",
            "agent monitor rules (sub-surface)",
            "alerts from Playbook watchlist",
        ],
        "blocked": ["deploy gate", "decision chips", "agent sizing/handoff"],
        "banned_phrases": ["Deploy gate open", "BOARD POSTURE TRADE", "Active Fund Manager"],
        "collapsed_sections": ["agent-debate-legacy"],
        "source_helper": "build_research_surface_block",
        "viewmodel": "agent-page-default",
        "sub_surfaces": ["agent"],
    },
    "notrade": {
        "tab_id": "notrade",
        "canonical_id": "rejections",
        "ui_label": "Rejections",
        "surface_mode": "rejections_diagnostic",
        "authority": "research_only",
        "allowed": ["gate failure audit trail"],
        "blocked": ["deploy permission"],
        "banned_phrases": [],
        "collapsed_sections": [],
        "source_helper": "build_header_summary",
        "viewmodel": None,
    },
    "ops": {
        "tab_id": "ops",
        "ui_label": "Ops",
        "surface_mode": "ops_diagnostic",
        "authority": "ops_probe",
        "allowed": ["engine health", "provider probes", "shadow account research"],
        "blocked": ["capital permission from runtime alone"],
        "banned_phrases": ["ENGINE ON", "ENGINE UNKNOWN"],
        "collapsed_sections": ["error log details"],
        "source_helper": "resolve_engine_state",
        "viewmodel": "shellTruthViewModel",
    },
    "ibkr": {
        "tab_id": "ibkr",
        "ui_label": "IBKR",
        "surface_mode": "ibkr_execution",
        "authority": "ops_probe",
        "allowed": ["connectivity check", "session status", "bracket readiness"],
        "blocked": ["LOGIN-only treated as READY", "handoff when critical fail"],
        "banned_phrases": [],
        "collapsed_sections": [],
        "source_helper": "build_header_summary",
        "viewmodel": None,
    },
    "btlab": {
        "tab_id": "btlab",
        "canonical_id": "backtest",
        "ui_label": "Backtest Lab",
        "surface_mode": "backtest_research",
        "authority": "research_only",
        "allowed": ["walk-forward research", "attribution review"],
        "blocked": ["deployment authority", "live track record claims"],
        "banned_phrases": ["Deploy gate open"],
        "collapsed_sections": ["attribution when insufficient coverage"],
        "source_helper": "build_header_summary",
        "viewmodel": None,
    },
}

PRIORITY_TEST_SURFACES = frozenset(
    {
        "guide",
        "today",
        "playbook",
        "discovery",
        "dossier",
        "portfolio",
        "command",  # includes Agent sub-surface
        "stratlab",
        "time_travel",
    }
)

# Agent UI is embedded in Command — separate marker for verify scripts.
AGENT_SUB_SURFACE_MARKER = 'data-cc="agent-page-default"'


def get_surface_contract(surface_key: str) -> Dict[str, Any]:
    """Return contract for a surface key; raises KeyError if unknown."""
    if surface_key not in SURFACE_CONTRACTS:
        raise KeyError(f"unknown surface contract: {surface_key}")
    return dict(SURFACE_CONTRACTS[surface_key])


def all_surface_keys() -> List[str]:
    return sorted(SURFACE_CONTRACTS.keys())


def export_contract_json() -> Dict[str, Any]:
    """Serialize contract for Node verify scripts."""
    return {
        "global_banned_phrases": list(GLOBAL_BANNED_PHRASES),
        "whitelist": list(BANNED_PHRASE_WHITELIST),
        "surfaces": SURFACE_CONTRACTS,
        "priority_test_surfaces": sorted(PRIORITY_TEST_SURFACES),
    }


def chunk_marker_for_surface(surface_key: str) -> Optional[str]:
    """DOM/data-cc marker used by verify scripts to scope surface HTML."""
    markers = {
        "guide": "tab==='guide'",
        "today": "tab==='today'",
        "playbook": 'data-cc="playbook-surface"',
        "discovery": 'data-cc="discovery-surface"',
        "dossier": "tab==='dossier'",
        "portfolio": "tab==='portfolio'",
        "command": "tab==='command'",
        "stratlab": "tab==='stratlab'",
        "time_travel": "replayModeActive()",
        "funds": "tab==='funds'",
        "flow": "tab==='flow'",
        "rs": "tab==='rs'",
        "notrade": "tab==='notrade'",
        "ops": "tab==='ops'",
        "ibkr": "tab==='ibkr'",
        "btlab": "tab==='btlab'",
    }
    return markers.get(surface_key)
