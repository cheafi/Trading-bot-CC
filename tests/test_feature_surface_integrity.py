"""Section 6 feature-by-feature integrity — CC Clarity Console."""

from __future__ import annotations

from pathlib import Path

from src.services.surface_authority import (
    HIDDEN_PRIMARY_NAV,
    SURFACE_MODES,
    is_hidden_from_primary_nav,
    resolve_surface_mode,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_command_surface_is_research_not_dashboard_core():
    assert SURFACE_MODES["command"] == "command_research"
    assert resolve_surface_mode("command") == "command_research"


def test_command_hidden_from_primary_nav():
    assert "command" in HIDDEN_PRIMARY_NAV
    assert is_hidden_from_primary_nav("command") is True
    assert is_hidden_from_primary_nav("today") is False


def test_index_html_dashboard_best_action_label_no_literal_trade_on_wait():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardBestActionLabel('trade')" in raw
    idx = raw.index("dashboardBestActionLabel(kind){")
    body = raw[idx : idx + 500]
    assert "Best deploy" in body or "Top candidate" in body
    assert "'Best TRADE'" not in body


def test_index_html_dashboard_actionable_picks_use_effective_grade():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardActionablePicks()" in raw
    idx = raw.index("dashboardActionablePicks(){")
    body = raw[idx : idx + 450]
    assert "effectiveCardAction" in body
    assert "o.action==='TRADE'" not in body


def test_index_html_playbook_opps_fallback_graded():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookOppsFallbackVisible()" in raw
    assert "playbookOppsFallbackRows()" in raw
    assert "effectiveCardAction(r)" in raw
    assert "rankedOpps.rows.length===0&&opps.length>0" not in raw


def test_index_html_dossier_confirm_only_and_indicative_levels():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierLevelsIndicativeOnly()" in raw
    assert "CONFIRM ONLY" in raw
    assert "dossierResearchOnly()" in raw


def test_index_html_data_contract_strip_object():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dataContractStripVisible()" in raw
    assert "dataContractStrip().fetch" in raw
    assert "dataContractStrip().board" in raw
    assert "dataContractStrip().broker" in raw
    idx = raw.index("dataContractStrip(){")
    body = raw[idx : idx + 350]
    assert "fetch:" in body or "fetch:this.dataContractFetchBadge()" in body


def test_index_html_market_strip_stale_visible():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "marketStripStaleVisible()" in raw
    idx = raw.index("marketStripStaleVisible(){")
    body = raw[idx : idx + 350]
    assert "marketStripStaleDowngrade()" in body


def test_index_html_ibkr_connect_required_cta():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "ibkrNeedsConnectCta()" in raw
    assert "Connect required" in raw


def test_index_html_decision_hub_gated_to_board_tabs():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "_boardDecisionStrip()" in raw
    idx = raw.index("_boardDecisionStrip(){")
    body = raw[idx : idx + 280]
    assert "surfaceShowsDecisionChips" in body
    assert "tab!=='today'&&this.tab!=='signals'" in body
    ctx = raw.index("contextDecisionBar(){")
    ctx_body = raw[ctx : ctx + 550]
    assert "decisionHub.decision_bar" in ctx_body
    assert "tab==='today'" in ctx_body and "tab==='signals'" in ctx_body


def test_index_html_rs_demoted_and_command_mobile_nav():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "RS·research" in raw
    assert "Relative strength — Discovery funnel input" in raw
    assert "hidden_from_primary_nav:true" in raw
    nav = raw[raw.index("BOTTOM NAV") : raw.index("ALPINE JS")]
    assert "switchTab('guide')" in nav
    assert "switchTab('command')" not in nav
    assert "switchTab('rs')" not in nav
