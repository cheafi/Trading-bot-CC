"""CC consistency cleanup pass — mission panel, funnel parity, dossier authority."""

from __future__ import annotations

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.decision_truth_model import normalize_playbook_funnel
from src.services.fetch_surface_state import (
    playbook_what_to_monitor_line,
    today_mission_empty_blockers_copy,
    today_mission_system_blockers,
    today_mission_panel,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_today_mission_system_blockers_wires_infra():
    blk = today_mission_system_blockers(
        ibkr_ready=False,
        ibkr_short="OFFLINE",
        engine_running=False,
        data_tier="STALE",
        brief_fallback=True,
    )
    assert any("IBKR" in x for x in blk)
    assert "ENGINE OFF" in blk
    assert any("DATA STALE" in x for x in blk)
    assert any("FALLBACK" in x for x in blk)


def test_today_mission_panel_splits_system_and_card_gates():
    m = today_mission_panel(
        risk_blockers=[],
        system_blockers=["ENGINE OFF", "IBKR OFFLINE"],
        near_miss=[{"ticker": "X"}],
    )
    assert m["system_blockers"]
    assert m["card_gates"] == []
    assert "ENGINE OFF" in m["blockers"]
    assert (
        today_mission_empty_blockers_copy(
            system_blockers=m["system_blockers"],
            card_gates=m["card_gates"],
        )
        == "No card-level gate flags"
    )


def test_playbook_funnel_label_uses_funnel_not_row_actions():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert (
        "playbookFunnelLabel(rankedOpps.filter_funnel||today7.filter_funnel, "
        "rankedOpps.rows)"
    ) in raw
    run_dashboard_js("""
        const rows = [
            {action: 'WATCH'}, {action: 'TRADE', execution_ready: true}];
        const funnel = {universe_scanned: 40, watch_qualified_setups: 0,
            deploy_qualified_setups: 0, near_miss_setups: 8,
            execution_ready_setups: 3};
        assert.deepEqual(app.playbookFunnelCounts(funnel, rows),
            {scanned: 40, watch: 0, deploy: 0});
        assert.match(app.playbookFunnelLabel(funnel, rows),
            /0 funnel watch-qualified · 0 deploy-qualified/);
        assert.deepEqual(app.playbookFunnelCounts(null, rows),
            {scanned: 0, watch: 0, deploy: 0});
        assert.deepEqual(app.playbookFunnelCounts({
            universe: '12', watch_setups: '2', execution_ready_setups: '1'
        }, rows), {scanned: 12, watch: 2, deploy: 1});
    """)


def test_index_mission_panel_system_blockers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "todayMissionPanel().system_blockers" in raw
    assert "todayMissionPanel().card_gates" in raw
    assert "todayMissionBlockersTitle()" in raw
    assert 'x-text="todayMissionEmptyBlockersCopy()"' in raw
    run_dashboard_js("""
        const blockers = H.todayMissionSystemBlockers({ibkrReady: false,
            ibkrShort: 'OFFLINE', engineRunning: false, breaker: true,
            dataTier: 'STALE', briefFallback: true});
        assert.deepEqual(blockers, ['IBKR OFFLINE', 'ENGINE OFF',
            'EXEC BLOCKED', 'DATA STALE', 'BRIEF ONLY']);
        assert.deepEqual(H.todayMissionSystemBlockers({
            ibkrReady: true, engineRunning: true,
            dataTier: 'FRESH'}), []);
        app.freshness = {worst_tier: 'STALE'};
        const panel = app.todayMissionPanel();
        assert.ok(panel.system_blockers.includes('ENGINE OFF'));
        assert.ok(panel.system_blockers.includes('DATA STALE'));
        assert.deepEqual(panel.card_gates, []);
        assert.equal(app.todayMissionEmptyBlockersCopy(), '無卡片級閘門標記');
        app.today7.todays_decision = {
            risk_blockers: ['R:R incomplete', 'R:R incomplete']};
        assert.deepEqual(app.todayMissionPanel().card_gates,
            ['R:R incomplete']);
    """)


def test_index_dossier_confirm_only_actions_blocked():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierActionsBlocked()" in raw
    assert ':disabled="dossierActionsBlocked()"' in raw
    run_dashboard_js("""
        app.dos.status = 'loaded';
        app.dos.intel = {unified_decision: {label: 'TRADE', rr_ratio: 3,
            confidence_pct: 75, confidence: 0.75}};
        assert.equal(app.dossierActionsBlocked(), false);
        app.dos.intel.confidence_metrics = {
            decision_confidence_available: false,
            decision_confidence_label: 'Pending calibration'};
        assert.equal(app.dossierActionsBlocked(), true);
        assert.equal(app.dossierSizingBlockedReason(), 'confirm_only');
        assert.equal(app.dosSizeShares(), 0);
        assert.equal(app.dosSizeDisplay(), '—');
    """)


def test_index_header_chip_groups():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "headerChipGroups()" in raw
    helpers = CC_HELPERS.read_text(encoding="utf-8")
    assert "partitionHeaderChips" in helpers
    assert "todayMissionSystemBlockers" in helpers


def test_playbook_wait_day_compression_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookWaitDayIntro()" in raw
    assert 'x-text="playbookOperatorNextActionLine()"' in raw
    assert 'x-text="playbookRankingsDisclaimer()"' in raw
    assert "playbookRowsCompactLabel()" in raw
    run_dashboard_js("""
        app.today7.tradeability = 'WAIT';
        app.rankedOpps.near_miss = [{ticker: 'COST'}, {ticker: 'QCOM'}];
        assert.equal(app.playbookRowsCompactMode(), true);
        const line = app.playbookWhatToMonitorLine();
        assert.match(line, /deploy unlock checklist below/);
        assert.match(line, /無 deploy 權威/);
        assert.equal(app.playbookOperatorNextActionLine(), line);
        assert.equal(H.playbookWhatToMonitorLine({waitDay: false}), '');
        app.rankedOpps.compact_rows = false;
        assert.equal(app.playbookRowsCompactMode(), false);
    """)


def test_playbook_what_to_monitor_line_parity():
    line = playbook_what_to_monitor_line(
        wait_day=True,
        top_symbol="cost",
        near_miss_count=2,
    )
    assert "COST upgrade triggers" in line
    assert "2 near-miss rows" in line
    assert "deploy unlock checklist below" in line
    assert "no deploy authority" in line
    assert playbook_what_to_monitor_line(wait_day=False) == ""


def test_normalize_watch_not_inflated_from_board_rows():
    out = normalize_playbook_funnel(
        {"watch_qualified_setups": 0, "universe_scanned": 40},
        opportunities=[{"action": "WATCH"}] * 5,
    )
    assert out["watch_qualified_setups"] == 0
