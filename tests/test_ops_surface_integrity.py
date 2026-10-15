"""Ops tab degraded copy, error-log UX, and render safety."""

from __future__ import annotations

import json
from pathlib import Path

from _dashboard_html_contract import bindings
from _dashboard_js_runtime import run_dashboard_js

from src.services.ops_operator_console import build_degraded_ops_operator_console

from src.services.fetch_surface_state import (
    OPS_STATE_FALLBACK,
    OPS_STATE_LOADING,
    OPS_STATE_RETRY_RECOMMENDED,
    OPS_STATE_RUNTIME_UNKNOWN,
    OPS_STATE_UNAVAILABLE,
    normalize_ops_panel_state,
    ops_degraded_copy,
    ops_degraded_line,
    ops_updates_panel_title,
)
from src.services.ui_render_safety import find_js_leaks_in_file

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_ops_degraded_vocabulary_table():
    loading = ops_degraded_copy(OPS_STATE_LOADING)
    fallback = ops_degraded_copy(OPS_STATE_FALLBACK)
    unavailable = ops_degraded_copy(OPS_STATE_UNAVAILABLE)
    runtime_unknown = ops_degraded_copy(OPS_STATE_RUNTIME_UNKNOWN)
    retry = ops_degraded_copy(OPS_STATE_RETRY_RECOMMENDED)

    assert loading["title"] == "Loading"
    assert fallback["title"] == "Fallback"
    assert unavailable["title"] == "Unavailable"
    assert runtime_unknown["title"] == "Runtime unknown"
    assert retry["title"] == "Retry recommended"

    assert "LOADING" in ops_degraded_line(OPS_STATE_LOADING)
    assert "FALLBACK" in ops_degraded_line(OPS_STATE_FALLBACK)
    assert "UNAVAILABLE" in ops_degraded_line(OPS_STATE_UNAVAILABLE)
    assert "RUNTIME UNKNOWN" in ops_degraded_line(OPS_STATE_RUNTIME_UNKNOWN)
    assert "RETRY" in ops_degraded_line(OPS_STATE_RETRY_RECOMMENDED)


def test_normalize_ops_panel_state_maps_fetch_failures():
    assert normalize_ops_panel_state(loading=True) == OPS_STATE_LOADING
    assert (
        normalize_ops_panel_state(error="Failed to fetch")
        == OPS_STATE_RETRY_RECOMMENDED
    )
    assert (
        normalize_ops_panel_state(error="HTTP 500", fallback=True) == OPS_STATE_FALLBACK
    )
    assert normalize_ops_panel_state(runtime_unknown=True) == OPS_STATE_RUNTIME_UNKNOWN


def test_index_html_error_log_does_not_show_empty_when_fetch_failed():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Error log fetch failed:" not in raw
    assert "opsErrorLogUnavailableDetail()" in bindings(INDEX_HTML, "x-text")
    conditions = bindings(INDEX_HTML, "x-if")
    empty = next(
        c
        for c in conditions
        if "!errorLog.entries.length" in c and "!errorLog.error" in c
    )
    assert "errorLog.error" in conditions
    run_dashboard_js("""
        const emptyExpression = EMPTY_EXPRESSION;
        const isEmpty = () => {
            with (app) { return eval(emptyExpression); }
        };
        app.errorLog = {loading: false, entries: [], error: ''};
        assert.equal(isEmpty(), true);
        app.errorLog.loading = true;
        assert.equal(isEmpty(), false);
        app.errorLog.loading = false;
        app.errorLog.error = 'HTTP 503';
        assert.equal(isEmpty(), false);
        assert.equal(app.opsErrorLogUnavailableDetail(), H.localizeUiText(
            'Unable to confirm whether errors were logged this session.'));
        app.errorLog.error = '';
        app.errorLog.entries = [{message: 'engine stopped'}];
        assert.equal(isEmpty(), false);
    """.replace("EMPTY_EXPRESSION", json.dumps(empty)))


def test_ops_updates_panel_title_vocabulary():
    assert ops_updates_panel_title(OPS_STATE_UNAVAILABLE) == "Panel unavailable"
    assert (
        ops_updates_panel_title(OPS_STATE_FALLBACK, timed_out=True)
        == "No fallback available"
    )
    assert (
        ops_updates_panel_title(OPS_STATE_FALLBACK, timed_out=False)
        == "Fallback unavailable"
    )
    assert ops_updates_panel_title(OPS_STATE_RETRY_RECOMMENDED) == "Retry recommended"


def _ops_surface_html(raw: str) -> str:
    start = raw.find("<!-- SURFACE 7: OPERATOR CONSOLE")
    if start < 0:
        return ""
    end = raw.find("</main>", start)
    return raw[start : end + len("</main>")] if end >= 0 else raw[start:]


def test_degraded_ops_console_includes_component_evidence():
    out = build_degraded_ops_operator_console(
        reason="backend importing", brief_ok=False
    )
    assert len(out["component_evidence"]) >= 3
    assert out["providers_honest"]["regime_router"]["probe"] == "Warming"
    assert "probe_table_note" in out["diagnostics"]
    assert "Recovery runbook" in out["diagnostics"]["page_intro"]


def test_degraded_ops_console_surfaces_backend_fatal_hint():
    hint = "No module named 'uvicorn' — pip install uvicorn"
    out = build_degraded_ops_operator_console(
        reason="backend importing",
        brief_ok=True,
        backend_fatal_hint=hint,
    )
    assert any("Backend crash" in b for b in out["blockers"])
    assert "uvicorn" in out["diagnostics"]["page_intro"]
    assert "Backend crash detected" in out["diagnostics"]["probe_table_note"]


def test_index_html_ops_uses_shared_degraded_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    ops = _ops_surface_html(raw)
    assert "opsDegradedCopy(" in ops
    assert "opsDegradedLine(" in ops
    assert "opsGlobalLoadingLine(" in raw
    assert "opsUpdatesPanelTitle(" in ops
    assert "opsPanelLoadingShort(" in ops
    assert "opsProviderRuntimeFallbackLabel(" in ops
    assert "Changelog timed out — showing fallback." not in ops
    assert "Probe only — refresh ops console" not in ops
    assert "opsProbeRuntimeFallbackRows()" in raw
    assert "opsFormatEvidence(" in ops
    assert "opsComponentLabel(" in ops
    assert "opsProbeLabel(" in ops
    assert "Probe vs runtime evidence" in ops
    assert "探測 vs 執行時證據" in ops
    assert "probe_table_note" in raw
    assert "opsDegradedLine('loading')" not in ops
    assert 'x-text="opsGlobalLoadingLine()"' in ops
    assert "API still loading — retry in a few seconds." not in ops
    run_dashboard_js("""
        app.tab = 'ops';
        for (const [ctx, expected] of [
            [{loading: true}, 'loading'],
            [{runtime_unknown: true}, 'runtime_unknown'],
            [{error: 'HTTP 500', fallback: true}, 'fallback'],
            [{error: 'Failed to fetch'}, 'retry_recommended'],
            [{error: 'HTTP 500'}, 'unavailable'], [{}, 'ok']
        ]) assert.equal(app.opsInferDegradedState(ctx), expected);
        app.opsConsole.loading = false;
        app.opsRuntime.loading = false;
        app.changelogPanel.loading = false;
        app.errorLog.loading = false;
        assert.equal(app.opsGlobalLoadingLine(), '');
        app.surfaceFetchHints.ops_error_log = {error: 'HTTP 503'};
        assert.equal(app.opsGlobalLoadingLine(),
            app.surfaceWarmupLoadingLine('ops_diagnostic'));
        app.healthMode = 'loading';
        app.ops.components = {market_data: true};
        const rows = app.opsProbeRuntimeFallbackRows();
        assert.equal(rows.length, 3);
        assert.ok(rows.every(r => r.runtime.includes('RUNTIME UNKNOWN')));
        assert.ok(rows.every(r => r.probeClass !== 'text-green-400'));
        for (const available of [true, false]) {
            assert.match(app.opsProviderRuntimeFallbackLabel(available),
                /unknown|unconfirmed|未明|未確認/);
        }
        assert.equal(app.deployOpen(), false);
    """)


def test_index_html_ops_advanced_diagnostics_bilingual_wiring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    ops = _ops_surface_html(raw)
    assert "opsAdvancedDiagnosticsTitle()" in ops
    assert "opsAdvancedDiagnosticsCollapsedTitle()" in ops
    assert "opsAdvancedCollapsedCopy()" in ops
    assert "opsAdvancedSectionKey(" in ops
    assert "opsAdvancedSectionStatus(" in ops


def test_index_html_autoschedule_button_is_clean():
    assert "autoScheduleExperiments()" in bindings(INDEX_HTML, "@click")
    assert find_js_leaks_in_file(INDEX_HTML) == []
    run_dashboard_js("""
        (async () => {
            let refreshes = 0;
            app.fetchABStatus = async () => { refreshes++; };
            for (const count of [0, 2]) {
                fetch = async (url, opts) => {
                    assert.equal(url,
                        '/api/v7/self-learn/auto-schedule-experiments');
                    assert.equal(opts.method, 'POST');
                    return {ok: true,
                        json: async () => ({total_proposed: count})};
                };
                await app.autoScheduleExperiments();
                assert.equal(app.selfLearn.lastAutoSchedule.total_proposed,
                    count);
                assert.equal(alerts.pop(), 'Auto-schedule: ' + count +
                    ' experiment(s) proposed.');
            }
            assert.equal(refreshes, 2);
            fetch = async () => ({ok: false, status: 503});
            await app.autoScheduleExperiments();
            assert.equal(alerts.pop(), 'Auto-schedule failed: status 503');
            assert.equal(refreshes, 2);
            assert.equal(app.deployOpen(), false);
        })().catch(error => { throw error; });
    """)
