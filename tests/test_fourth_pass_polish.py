"""Fourth-pass CC polish — operator safe lines, partial markers, mission WAIT."""

from __future__ import annotations

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.fetch_surface_state import (
    operator_loading_safe_line,
    today_mission_wait_subtitle,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
PARTIAL = ROOT / "src/api/templates/cc/partials/degraded_banners.html"
BUILD_SCRIPT = ROOT / "scripts/build-cc-template.mjs"


def test_operator_loading_safe_line_loading_and_wait():
    assert "core-only" in operator_loading_safe_line(health_mode="loading")
    assert operator_loading_safe_line(health_mode="full", wait_day=False) == ""
    assert "WAIT" in operator_loading_safe_line(wait_day=True)


def test_today_mission_wait_subtitle():
    assert "Deploy blocked" in today_mission_wait_subtitle(wait_day=True)
    assert today_mission_wait_subtitle(wait_day=False) == ""


def test_index_html_fourth_pass_wiring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "<!-- @cc-partial degraded_banners -->" in raw
    assert "<!-- @cc-partial-end degraded_banners -->" in raw
    assert "operatorLoadingSafeLine()" in raw
    assert "todayMissionWaitSubtitle()" in raw
    assert 'data-cc="portfolio-stop-blockers"' in raw


def test_cc_helpers_fourth_pass_exports():
    run_dashboard_js("""
        assert.match(H.operatorLoadingSafeLine({healthMode: 'loading'}),
            /core-only/);
        assert.equal(H.operatorLoadingSafeLine({healthMode: 'full',
            waitDay: false}), '');
        assert.match(app.operatorLoadingSafeLine(), /core-only/);
        app.healthMode = 'full';
        app.live = true;
        app.ccHeader.page_authority_mode = 'active';
        assert.match(app.operatorLoadingSafeLine(), /WAIT/);
        // Display is Traditional Chinese, not an English default.
        assert.equal(app.todayMissionWaitSubtitle(),
            H.localizeUiText('Deploy blocked — use monitors and ' +
                'Playbook ranking only'));
        assert.match(app.todayMissionWaitSubtitle(), /部署已阻/);
        assert.equal(app.deployOpen(), false);
        assert.equal(app.playbookCanSendToIbkr({execution_ready: true,
            action: 'TRADE', entry_price: 100, stop_price: 95}), false);
        app.today7.tradeability = 'SELECTIVE';
        app.today7.system_state = {deploy_open: true};
        app.live = true;
        app.ccHeader.page_authority_mode = 'active';
        assert.equal(app.operatorLoadingSafeLine(), '');
        assert.equal(app.todayMissionWaitSubtitle(), '');
        assert.equal(H.todayMissionWaitSubtitle({waitDay: false}), '');
    """)


def test_degraded_banners_partial_exists():
    body = PARTIAL.read_text(encoding="utf-8")
    assert 'data-cc="instant-degraded-banner"' in body
    assert 'data-cc="warmup-context-strip"' in body
    assert "operatorLoadingSafeLine()" in body


def test_build_cc_template_script_present():
    assert BUILD_SCRIPT.is_file()
