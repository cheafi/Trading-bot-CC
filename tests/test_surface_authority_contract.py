"""Surface authority contract — enforceable product law for 16 operator surfaces."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.surface_authority import (
    AUTHORITY_RESEARCH,
    AUTHORITY_SUSPENDED,
    SURFACE_MODES,
    TAB_SURFACE_MAP,
    resolve_authority,
)
from src.services.surface_authority_contract import (
    AGENT_SUB_SURFACE_MARKER,
    BANNED_PHRASE_WHITELIST,
    GLOBAL_BANNED_PHRASES,
    PRIORITY_TEST_SURFACES,
    SURFACE_CONTRACTS,
    all_surface_keys,
    chunk_marker_for_surface,
    get_surface_contract,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src" / "api" / "templates" / "index.html"
GUIDE = ROOT / "src" / "api" / "templates" / "cc" / "partials" / "guide.html"
HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
CONTRACT_DOC = ROOT / "docs" / "SURFACE_AUTHORITY_CONTRACT.md"
OS_DOC = ROOT / "docs" / "OPERATOR_DECISION_OS.md"
FLOW_DOC = ROOT / "docs" / "DAILY_OPERATOR_FLOW.md"


def _surface_chunk(html: str, marker: str) -> str:
    start = html.find(marker)
    if start < 0:
        return ""
    # Scope ~12k chars or until next SURFACE comment
    end_markers = ["<!-- SURFACE:", "<!-- @cc-partial", "x-show=\"tab==="]
    end = len(html)
    for em in end_markers:
        pos = html.find(em, start + len(marker))
        if pos > start and pos < end:
            end = pos
    return html[start : min(start + 12000, end)]


def _is_whitelisted(text: str, phrase: str) -> bool:
    lower = text.lower()
    if phrase.lower() not in lower:
        return False
    for ctx in BANNED_PHRASE_WHITELIST:
        if ctx.lower() in lower:
            return True
    if "illustrative examples only" in lower:
        return True
    return False


def test_contract_map_has_exactly_16_surfaces():
    assert len(SURFACE_CONTRACTS) == 16
    assert len(all_surface_keys()) == 16


def test_priority_surfaces_are_subset_of_contract():
    for key in PRIORITY_TEST_SURFACES:
        assert key in SURFACE_CONTRACTS, f"missing priority surface: {key}"


def test_contract_docs_exist():
    for path in (CONTRACT_DOC, OS_DOC, FLOW_DOC):
        assert path.is_file(), f"missing doc: {path}"
    contract_text = CONTRACT_DOC.read_text(encoding="utf-8")
    assert "16 operator surfaces" in contract_text
    assert "Global Banned Phrases" in contract_text


def test_per_surface_required_fields():
    required = {
        "tab_id",
        "ui_label",
        "surface_mode",
        "authority",
        "allowed",
        "blocked",
        "banned_phrases",
        "collapsed_sections",
        "source_helper",
    }
    for key, contract in SURFACE_CONTRACTS.items():
        for field in required:
            assert field in contract, f"{key} missing {field}"
        assert isinstance(contract["allowed"], list) and contract["allowed"]
        assert isinstance(contract["blocked"], list)


def test_guide_contract_suspended_authority():
    c = get_surface_contract("guide")
    auth = resolve_authority("guide", tradeability="TRADE", deployable_count=5)
    assert c["authority"] == AUTHORITY_SUSPENDED
    assert auth["authority"] == AUTHORITY_SUSPENDED
    assert c["surface_mode"] == SURFACE_MODES["guide"]
    html = INDEX.read_text(encoding="utf-8")
    assert c["viewmodel"] == "guideStatusNote"
    assert "guideStatusNote()" in html


def test_dashboard_operator_block_viewmodel():
    c = get_surface_contract("today")
    html = INDEX.read_text(encoding="utf-8")
    assert c["viewmodel"] == "dashboardOperatorBlock"
    assert "dashboardOperatorBlock()" in html


def test_dashboard_playbook_deploy_surfaces():
    for key, tab in (("today", "today"), ("playbook", "playbook")):
        c = get_surface_contract(key)
        assert c["authority"] == "deploy_authority"
        assert TAB_SURFACE_MAP[tab]["default_authority"] == "deploy_authority"


def test_discovery_dossier_research_only():
    for key in ("discovery", "dossier"):
        c = get_surface_contract(key)
        assert c["authority"] == AUTHORITY_RESEARCH
    dossier_auth = resolve_authority("dossier", tradeability="TRADE", deployable_count=3)
    assert dossier_auth["authority"] == AUTHORITY_RESEARCH


def test_portfolio_viewmodel_present():
    c = get_surface_contract("portfolio")
    html = INDEX.read_text(encoding="utf-8")
    helpers = HELPERS.read_text(encoding="utf-8")
    chunk = _surface_chunk(html, chunk_marker_for_surface("portfolio") or "")
    assert c["viewmodel"] == "pfRiskVM"
    assert "pfRiskVM()" in chunk
    assert "portfolioRiskViewModel" in helpers


def test_playbook_viewmodel_and_banned_phrases():
    c = get_surface_contract("playbook")
    html = INDEX.read_text(encoding="utf-8")
    helpers = HELPERS.read_text(encoding="utf-8")
    chunk = _surface_chunk(html, chunk_marker_for_surface("playbook") or "")
    assert c["viewmodel"] == "playbookOperatorView"
    assert "playbookOperatorView()" in chunk
    assert "playbookAuthorityViewModel" in helpers
    for phrase in c["banned_phrases"]:
        assert phrase.lower() not in chunk.lower(), f"banned in playbook chunk: {phrase}"


def test_discovery_scoped_freshness_no_banned():
    c = get_surface_contract("discovery")
    html = INDEX.read_text(encoding="utf-8")
    chunk = _surface_chunk(html, chunk_marker_for_surface("discovery") or "")
    assert "discoveryScannerRunLabel()" in chunk
    assert "discoveryFunnelPanel().status_line" in chunk
    for phrase in c["banned_phrases"]:
        assert phrase.lower() not in chunk.lower(), f"banned in discovery: {phrase}"


def test_dossier_confirm_only_not_decision_card():
    c = get_surface_contract("dossier")
    guide = GUIDE.read_text(encoding="utf-8")
    assert "decision card" in c["banned_phrases"]
    assert "decision card" not in guide.lower()
    assert "structure review surface" in guide.lower() or "structure confirmation" in guide.lower()
    assert "Confirm-only · 僅結構確認" in guide


def test_command_agent_sub_surface_marker():
    c = get_surface_contract("command")
    html = INDEX.read_text(encoding="utf-8")
    assert AGENT_SUB_SURFACE_MARKER.strip('"') in html
    assert "agent" in (c.get("sub_surfaces") or [])
    assert c["viewmodel"] == "agent-page-default"
    agent_chunk = _surface_chunk(html, "data-cc=\"agent-page-default\"")
    assert agent_chunk
    for phrase in c["banned_phrases"]:
        if phrase == "Active Fund Manager":
            assert phrase not in agent_chunk


def test_stratlab_viewmodel_present():
    c = get_surface_contract("stratlab")
    html = INDEX.read_text(encoding="utf-8")
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "tab==='stratlab'" in html
    assert c["viewmodel"] == "strategyLabPageState"
    assert "strategyLabPageState" in helpers


def test_time_travel_replay_overlay():
    c = get_surface_contract("time_travel")
    html = INDEX.read_text(encoding="utf-8")
    assert c["authority"] == AUTHORITY_SUSPENDED
    assert "replayModeActive()" in html
    assert c["viewmodel"] == "ccReplayAsOf"


def test_global_banned_phrases_absent_from_runtime_trust_and_playbook():
    html = INDEX.read_text(encoding="utf-8")
    trust = html.split("trust-strip-tier-primary", 1)[1].split("<!--", 1)[0]
    playbook = _surface_chunk(html, 'data-cc="playbook-surface"')
    runtime = trust + playbook
    for phrase in GLOBAL_BANNED_PHRASES:
        if phrase in ("DATA FRESH", "DATA STALE"):
            assert phrase not in runtime
            continue
        if _is_whitelisted(runtime, phrase):
            continue
        assert phrase.lower() not in runtime.lower(), f"global banned in runtime: {phrase}"


def test_guide_banned_phrases_and_pilot_wording():
    guide = GUIDE.read_text(encoding="utf-8")
    assert "TRADE LIST" not in guide
    assert "decision card" not in guide.lower()
    assert "pilot half-size" not in guide.lower()
    assert "PILOT/TRADE labels on blocked days are review-only" in guide
    assert "review-only — not permission" in guide.lower() or "review-only" in guide.lower()


def test_surface_modes_align_with_contract():
    """Canonical surface modes in surface_authority.py match contract keys."""
    mode_by_tab = {
        "today": "dashboard_core",
        "playbook": "playbook_core",
        "discovery": "discovery_research",
        "dossier": "dossier_research",
        "portfolio": "portfolio_manual",
        "guide": "guide_reference",
        "funds": "funds_research",
        "flow": "flow_supporting",
        "rs": "rs_supporting",
        "command": "command_research",
        "notrade": "rejections_diagnostic",
        "ops": "ops_diagnostic",
        "ibkr": "ibkr_execution",
        "btlab": "backtest_research",
    }
    for tab, expected_mode in mode_by_tab.items():
        contract_key = "playbook" if tab == "playbook" else tab
        if tab == "discovery":
            contract_key = "discovery"
        if tab == "notrade":
            contract_key = "notrade"
        c = SURFACE_CONTRACTS[contract_key]
        assert c["surface_mode"] == expected_mode


def test_chunk_markers_present_for_priority_surfaces():
    html = INDEX.read_text(encoding="utf-8")
    for key in PRIORITY_TEST_SURFACES:
        marker = chunk_marker_for_surface(key)
        assert marker, f"no chunk marker for {key}"
        assert marker in html, f"marker missing in index.html: {key} -> {marker}"


def test_helpers_export_contract_viewmodels():
    helpers = HELPERS.read_text(encoding="utf-8")
    exports = [
        "playbookAuthorityViewModel",
        "shellTruthViewModel",
        "portfolioRiskViewModel",
        "strategyLabPageState",
        "discoveryFunnelPanel",
    ]
    for name in exports:
        assert name in helpers, f"missing helper export: {name}"
