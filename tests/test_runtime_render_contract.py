"""Rendered CC contract — banned operator copy must not appear in live template paths."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src" / "api" / "templates" / "index.html"
HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"

BANNED_IN_RUNTIME = [
    r"x-text=\"today7\.tradeability",
    r"x-text=\"canonicalTradeability\(\)\"",
    r"taking a Pilot entry",
    r"Deploy gate open",
    r"brief fallback",
    r"BOARD POSTURE TRADE",
    r"Current: TRADE",
    r"FALLBACK / BRIEF ONLY",
    r"Sizing suspended in fallback mode",
    r"freshness\.worst_tier",
    r"'DATA '\+freshness\.worst_tier",
    r"ENGINE ON",
    r"ENGINE UNKNOWN",
    r"h\.freshness\|\|'live'",
    r"Freshness:\s*live",
]

RUNTIME_REQUIRED = [
    "runtimePrimaryStateLine()",
    "runtimeSecondaryRegimeLine()",
    "data-role=\"secondary-regime\"",
    "safeRenderText(",
    "cardShowsStructureReference(",
    "Structure reference only",
    "CCHelpers.safeRenderText",
    "runtimePrimaryStateLine",
    "resolveEngineState",
    "Runtime: Conflict",
    "shellTruthVM()",
    "shellTruthViewModel",
    "dashboardShellCompressed()",
    "discoveryScannerRunLabel",
    "discoveryFunnelPanel().status_line",
    "runtimeEngineHeaderLabel",
]


def _blocked_truth_fixture() -> dict:
    return {
        "regime_state": "SELECTIVE",
        "deploy_authority": False,
        "deploy_authority_tier": "blocked",
        "broker_freshness": "offline",
        "brief_freshness": "expired",
        "brief_age_days": 26,
        "brief_expired": True,
        "board_gate": "wait",
        "market_data_freshness": "stale",
        "ranked_board_freshness": "stale",
        "reason_codes": ["ENGINE_OFF", "IBKR_OFFLINE", "BRIEF_EXPIRED"],
        "execution_readiness": {"engine_running": False, "sub_status": {"engine": "off"}},
    }


def test_index_primary_uses_runtime_state_line_not_raw_tradeability():
    html = INDEX.read_text(encoding="utf-8")
    assert "trust-strip-tier-primary" in html
    primary = html.split("trust-strip-tier-primary", 1)[1].split("</div>", 1)[0]
    assert "runtimePrimaryStateLine()" in primary
    assert 'x-text="today7.tradeability' not in primary
    assert "data-role=\"secondary-regime\"" in primary


def test_index_banned_phrases_absent_from_runtime_bindings():
    html = INDEX.read_text(encoding="utf-8")
    trust = html.split("trust-strip-tier-primary", 1)[1].split("<!--", 1)[0]
    playbook = html.split('data-cc="playbook-surface"', 1)[1].split("<!-- SURFACE:", 1)[0]
    runtime_chunk = trust + playbook
    for pattern in BANNED_IN_RUNTIME:
        assert re.search(pattern, runtime_chunk, re.I) is None, f"banned in runtime: {pattern}"


def test_index_runtime_helpers_wired():
    html = INDEX.read_text(encoding="utf-8")
    for needle in RUNTIME_REQUIRED:
        assert needle in html, f"missing runtime wiring: {needle}"


def test_cc_helpers_blocked_primary_not_selective():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "function runtimePrimaryStateLine" in helpers
    assert "function deployAuthorityTier" in helpers
    assert "function safeRenderText" in helpers
    assert 'return "conflict"' in helpers
    assert "Runtime: Conflict" in helpers
    assert "function runtimeEngineHeaderLabel" in helpers
    assert "ENGINE ON" not in helpers
    assert "function discoveryScannerRunLabel" in helpers
    assert "function shellTruthViewModel" in helpers


def test_discovery_surface_scoped_freshness_in_template():
    html = INDEX.read_text(encoding="utf-8")
    discovery = html.split('data-cc="discovery-surface"', 1)[1].split("<!-- SURFACE:", 1)[0]
    assert "discoveryScannerRunLabel()" in discovery
    assert "discoveryFunnelPanel().status_line" in discovery
    assert "Freshness: live" not in discovery
    assert "h.freshness||'live'" not in discovery
    assert "brief fallback" not in discovery.lower()


def test_safe_render_sanitizes_blocked_card_copy():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "taking a Pilot entry" in helpers
    assert "Deploy gate open" in helpers
    assert "removeTradeLanguageWhenBlocked" in helpers


def test_playbook_qualification_zero_deploy_when_blocked():
    from src.services.playbook_truth import format_playbook_qualification_line

    line = format_playbook_qualification_line(
        setup_qualified=3,
        trade_qualified=2,
        execution_qualified=2,
        deploy_qualified=2,
        deploy_authority=False,
        regime_state="SELECTIVE",
        board_gate="wait",
    )
    assert "2 deploy-qualified" not in line
    assert "0 deploy-qualified" in line
    assert "deploy gate open" not in line.lower()


def test_blocked_fixture_primary_monitor_only_not_selective():
    from src.services.authority_engine import primary_operator_state

    posture = primary_operator_state(_blocked_truth_fixture())
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["secondary"] == "SELECTIVE"


def test_guide_operator_quick_read_uses_monitor_model():
    html = INDEX.read_text(encoding="utf-8")
    guide = html.split("<!-- @cc-partial guide", 1)[1].split("<!-- @cc-partial-end guide", 1)[0]
    assert "MONITOR ONLY" in guide and "Deploy blocked" in guide
    assert "TRADE LIST" not in guide
    assert "pilot half-size" not in guide.lower()


def _playbook_surface(html: str) -> str:
    start = html.index('data-cc="playbook-surface"')
    end = html.index("x-show=\"tab==='dossier'\"", start)
    return html[start:end]


def test_playbook_wires_authority_viewmodel():
    html = INDEX.read_text(encoding="utf-8")
    helpers = HELPERS.read_text(encoding="utf-8")
    playbook = _playbook_surface(html)
    assert "playbookAuthorityViewModel" in helpers
    assert "playbookOperatorView()" in playbook
    assert "playbookQualificationDisplay()" in playbook
    assert "playbookRegimeDisplayLine()" in playbook
    assert 'x-text="canonicalRegimeLine()"' not in playbook


def test_playbook_blocked_fixture_qualification_zero_deploy():
    from src.services.playbook_truth import build_playbook_operator_view

    truth = _blocked_truth_fixture()
    truth["qualification_levels"] = {
        "setup_qualified": 3,
        "deploy_qualified": 2,
        "execution_qualified": 2,
    }
    truth["deploy_qualified_count"] = 0
    pov = build_playbook_operator_view(
        truth,
        [{"ticker": "SPY", "action": "WATCH"}],
    )
    assert pov["qualification"]["deploy"] == 0
    assert "2 deploy-qualified" not in pov["qualification_line"]


def _shell_truth_conflict_fixture() -> dict:
    """Market fresh, board stale, brief 27d, broker offline, engine conflict, authority blocked."""
    return {
        "regime_state": "SELECTIVE",
        "deploy_authority": False,
        "deploy_authority_tier": "blocked",
        "board_gate": "wait",
        "market_data_freshness": "fresh",
        "ranked_board_freshness": "stale",
        "brief_freshness": "expired",
        "brief_age_days": 27,
        "brief_expired": True,
        "broker_freshness": "offline",
        "engine_state": "on",
        "reason_codes": ["ENGINE_OFF", "BOARD_STALE", "BRIEF_EXPIRED", "IBKR_OFFLINE"],
        "execution_readiness": {"engine_running": True, "sub_status": {"engine": "on"}},
    }


def test_shell_truth_fixture_scoped_labels_no_contradiction():
    from src.services.system_truth import typed_freshness_display

    truth = _shell_truth_conflict_fixture()
    strip = typed_freshness_display(truth)
    assert "Market: Fresh" in strip
    assert "Board: Stale" in strip
    assert "Brief: Expired 27d" in strip
    assert "Broker: Offline" in strip
    assert "Authority: Blocked" in strip
    assert "DATA FRESH" not in strip
    assert "DATA STALE" not in strip
    assert "brief fallback" not in strip.lower()


def test_shell_truth_fixture_engine_not_dual_on_off():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "function shellTruthViewModel" in helpers
    assert "function resolveEngineState" in helpers
    truth = _shell_truth_conflict_fixture()
    # JS resolver contract mirrored in Python engine tests — conflict not simultaneous ON+OFF labels
    from src.services.authority_engine import resolve_engine_state

    state = resolve_engine_state(
        truth,
        {"engine_running": False, "running": True},
    )
    assert state in ("unknown", "conflict", "off")


def test_shell_truth_fixture_primary_monitor_only():
    from src.services.authority_engine import primary_operator_state

    posture = primary_operator_state(_shell_truth_conflict_fixture())
    assert posture["primary"] == "MONITOR ONLY"


def test_cc_helpers_exports_shell_truth_view_model():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "shellTruthViewModel: shellTruthViewModel" in helpers
    assert "shellTruthScopedStrip: shellTruthScopedStrip" in helpers


def _portfolio_offline_fixture() -> dict:
    return {
        "portfolio_mode": {
            "mode": "unavailable",
            "risk_review_only": True,
            "capital_action_queue_enabled": False,
            "risk_capacity_authority": "none",
            "broker_truth": False,
            "broker_connected": False,
        },
        "portfolio_risk_view_model": {
            "show_critical_risk_event": False,
            "broker_truth_banner_active": True,
            "default_details_collapsed": True,
            "show_sleeve_research_default": False,
            "show_demo_tools_default": False,
            "show_historical_journal_default": False,
        },
        "critical_risk_event": {"active": False},
        "ibkr_linkage": {"broker_truth": False, "broker_connected": False},
    }


def test_portfolio_offline_default_banned_copy_absent():
    html = INDEX.read_text(encoding="utf-8")
    helpers = HELPERS.read_text(encoding="utf-8")
    portfolio = html.split("tab==='portfolio'", 1)[1].split("<!-- SURFACE 4:", 1)[0]
    assert "pfRiskVM()" in portfolio
    assert "portfolioRiskViewModel" in helpers
    assert "Historical Journal" in portfolio
    assert "Sleeve Research" in portfolio
    banned = [
        "Active sleeves",
        "Seed Demo Book",
        "Closed-Trade Ledger",
        "CRITICAL RISK EVENT",
        "Method Not Allowed",
    ]
    for phrase in banned:
        assert phrase not in portfolio, f"banned in portfolio default: {phrase}"
    assert "Expectancy" not in portfolio.split("ledgerView.expanded")[0]
    assert "CRITICAL RISK EVENT" not in portfolio


def test_portfolio_risk_view_model_offline_contract():
    from src.services.portfolio_risk_mode import (
        BROKER_TRUTH_REVIEW_ONLY,
        build_portfolio_risk_view_model,
        resolve_portfolio_risk_mode,
    )

    pm = resolve_portfolio_risk_mode(
        positions=[],
        source="manual",
        execution_readiness={"broker_connected": False},
        ibkr_linkage={"broker_truth": False, "broker_connected": False},
        system_truth={"deploy_authority": False},
    )
    vm = build_portfolio_risk_view_model(pm, positions=[], ibkr_linkage=pm)
    assert vm["capital_action_enabled"] is False
    assert vm["show_critical_risk_event"] is False
    assert vm["broker_truth_banner"] == BROKER_TRUTH_REVIEW_ONLY
