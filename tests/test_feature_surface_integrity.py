"""Section 6 feature-by-feature integrity — CC Clarity Console."""

from __future__ import annotations

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.surface_authority import (
    HIDDEN_PRIMARY_NAV,
    SURFACE_MODES,
    is_hidden_from_primary_nav,
    resolve_surface_mode,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"

# Synthetic state only: exercise real selectors, never replace authority methods.
ACTIVE_BOARD = """
app.live = true;
app.healthMode = 'full';
app.ccHeader.page_authority_mode = 'active';
app.ops.running = true;
app.today7.regime = {trend: 'UPTREND'};
app.today7.tradeability = 'SELECTIVE';
app.today7.trust = {source: 'live', stale: false, freshness: 'FRESH'};
app.today7.filter_funnel = {
    universe_scanned: 20, watch_qualified_setups: 2, deploy_qualified_setups: 1
};
app.today7.todays_decision = {deploy_posture: 'DEPLOY', execution_ready_count: 1};
app.today7.execution_readiness = {
    broker_connected: true, gateway_reachable: true,
    trade_handoff_ready: true, bracket_order_ready: true, engine_running: true
};
app.today7.cc_state = {
    tradeability_state: {tradeability: 'SELECTIVE'},
    board_decision_state: {
        state: 'DEPLOY', source: 'live', authority_level: 'deploy',
        allows_trade_labels: true, gates: {}, gates_active: false, degraded: false
    },
    execution_state: {state: 'READY'},
    freshness_state: {worst_tier: 'FRESH', board_source: 'live'}
};
app.today7.system_state = {deploy_open: true, tradeability: 'SELECTIVE'};
assert.equal(app.pageAuthorityMode(), 'active');
assert.equal(app.deployOpen(), true);
"""


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
    run_dashboard_js(ACTIVE_BOARD + """
        assert.equal(app.dashboardBestActionLabel('trade'), app._uiText('Best deploy'));
        app.today7.cc_state.tradeability_state.tradeability = 'WAIT';
        assert.equal(app.dashboardBestActionLabel('trade'), app._uiText('Top candidate'));
        assert.equal(app.dashboardBestActionLabel('action'), app._uiText('Top monitor'));
        app.today7.cc_state.tradeability_state.tradeability = 'SELECTIVE';
        app.today7.system_state.deploy_open = false;
        assert.equal(app.dashboardBestActionLabel('trade'), app._uiText('Top candidate'));
    """)


def test_index_html_dashboard_actionable_picks_use_effective_grade():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardActionablePicks()" in raw
    run_dashboard_js(ACTIVE_BOARD + """
        const good = {ticker: 'SYN', action: 'TRADE', execution_ready: true, risk_reward: 3};
        const downgraded = {...good, ticker: 'DOWN', effective_grade: 'WATCH'};
        app.today7.top_ranked = [good, downgraded, {...good, execution_ready: false}];
        assert.equal(app.effectiveCardAction(downgraded), 'WATCH');
        assert.deepEqual(app.dashboardActionablePicks(), [good]);
        app.today7.system_state.deploy_open = false;
        assert.equal(app.dashboardActionablePicks().length, 0);
        app.today7.system_state.deploy_open = true;
        app.cc_status.breaker = true;
        assert.equal(app.dashboardActionablePicks().length, 0);
    """)


def test_index_html_playbook_opps_fallback_graded():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookOppsFallbackVisible()" in raw
    assert "playbookOppsFallbackRows()" in raw
    assert "rankedOpps.rows.length===0&&opps.length>0" not in raw
    run_dashboard_js(ACTIVE_BOARD + """
        const trade = {ticker: 'SYN', action: 'TRADE', execution_ready: true, risk_reward: 3};
        const watch = {...trade, ticker: 'DOWN', effective_grade: 'WATCH'};
        app.opps = [trade, watch, {ticker: 'NO', action: 'AVOID'}];
        assert.deepEqual(app.playbookOppsFallbackRows(), [watch]);
        assert.equal(app.playbookOppsFallbackVisible(), true);
        app.rankedOpps.rows = [trade];
        assert.equal(app.playbookOppsFallbackVisible(), false);
        assert.equal(app.playbookOppsFallbackRows().length, 0);
    """)


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
    run_dashboard_js(ACTIVE_BOARD + """
        const strip = app.dataContractStrip();
        assert.equal(strip.fetch, app.dataContractFetchBadge());
        assert.equal(strip.board, 'UPTREND · SELECTIVE');
        assert.equal(strip.broker, 'READY');
        assert.equal(strip.dismissible, true);
        assert.equal(app.dataContractStripVisible(), true);
        app.dismissDataContract();
        assert.equal(app.dataContractStripVisible(), false);
    """)


def test_index_html_market_strip_stale_visible():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "marketStripStaleVisible()" in raw
    run_dashboard_js(ACTIVE_BOARD + """
        assert.equal(app.marketStripStaleVisible(), false);
        app.today7.trust = {source: 'disk-snapshot', stale: true};
        assert.equal(app.marketStripStaleDowngrade(), true);
        assert.equal(app.marketStripStaleVisible(), true);
        app.today7.trust = {source: 'live', stale: false};
        app.freshness = {worst_tier: 'CRITICAL'};
        assert.equal(app.marketStripStaleVisible(), true);
    """)


def test_index_html_ibkr_connect_required_cta():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "ibkrNeedsConnectCta()" in raw
    assert "Connect required" in raw


def test_index_html_decision_hub_gated_to_board_tabs():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "normalizedContextDecisionBar()" in raw
    run_dashboard_js("""
        const strip = {deploy_reduce_wait: 'WAIT'};
        const bar = {verdict: 'WAIT'};
        app.decisionHub = {decision_strip: strip, decision_bar: bar};
        for (const tab of ['today', 'signals']) {
            app.tab = tab;
            assert.equal(app._boardDecisionStrip(), strip);
            assert.equal(app.contextDecisionBar(), bar);
        }
        for (const tab of ['guide', 'flow', 'rs', 'command', 'scanners', 'ops']) {
            app.tab = tab;
            assert.equal(app._boardDecisionStrip(), null);
            assert.equal(app.contextDecisionBar(), null);
        }
        app.tab = 'funds';
        app.fundMonitor.console = {decision_bar: {verdict: 'RESEARCH ONLY'}};
        assert.equal(app.contextDecisionBar(), app.fundMonitor.console.decision_bar);
    """)


def test_index_html_rs_demoted_and_command_mobile_nav():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Open RS research layer" in raw
    assert "Relative strength — Discovery funnel input" in raw
    run_dashboard_js("""
        assert.equal(app.moreTabs.find(t => t.id === 'command').hidden_from_primary_nav, true);
        app.tab = 'command';
        assert.equal(app.pageSurface(), 'command_research');
    """)
    nav = raw[raw.index("BOTTOM NAV") :]
    assert "switchTab('guide')" in nav
    assert "switchTab('command')" not in nav
    assert "switchTab('rs')" not in nav
