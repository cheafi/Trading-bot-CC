"""Rejections tab fetch UX — single banner, ops degraded copy, surface hints."""

from __future__ import annotations

import json
from pathlib import Path

from _dashboard_html_contract import bindings
from _dashboard_js_runtime import run_dashboard_js

from src.services.fetch_surface_state import (
    OPS_STATE_RETRY_RECOMMENDED,
    OPS_STATE_UNAVAILABLE,
    ops_degraded_line,
)
from src.services.ui_render_safety import find_js_leaks_in_file

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def _rejections_section(raw: str) -> str:
    start = raw.find("SURFACE: REJECTIONS")
    end = raw.find("SURFACE: IBKR", start)
    assert start >= 0 and end > start
    return raw[start:end]


def test_rejections_helpers_and_hints_wired():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "rejectionsFetchBanner()" in raw
    assert "rejectionsTrustStripStatus()" in raw
    assert "rejectionsEmptyMessage()" in raw
    assert "rejectionsInferDegradedState()" in raw
    run_dashboard_js("""
        app.tab = 'notrade';
        assert.equal(app.pageSurface(), 'rejections_diagnostic');
        app.surfaceFetchHints.notrade = {loading: true};
        assert.equal(app.headerContext().loading, true);
        assert.equal(app.rejectionsInferDegradedState(), 'loading');
        assert.equal(app.rejectionsFetchBanner(), '');
        assert.equal(app.headerSummary().show_decision_chips, false);
        assert.equal(app.deployOpen(), false);
    """)


def test_rejections_no_duplicate_fetch_failed_in_strip():
    raw = _rejections_section(INDEX_HTML.read_text(encoding="utf-8"))
    assert "rejectionsPanel.error" not in raw
    duplicate = "FETCH FAILED — Network or server error prevented a fresh read."
    assert duplicate not in raw


def test_rejections_empty_copy_when_fetch_failed():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    section = _rejections_section(raw)
    assert "rejectionsEmptyMessage()" in section
    run_dashboard_js("""
        app.rejectionsPanel.loading = false;
        app.surfaceFetchHints.notrade = {
            failed_fetch: true, error: 'HTTP 503'};
        assert.match(app.rejectionsEmptyMessage(),
            /Fresh rejection data unavailable; no blocked signals shown/);
        assert.match(app.rejectionsEmptyMessage(),
            /No blocked signals available from the last readable batch/);
        assert.ok(!app.rejectionsTrustStripStatus().includes('FETCH FAILED'));
        app.surfaceFetchHints.notrade = {};
        app.rejectionsPanel.data = {count: 0, no_trade_signals: []};
        assert.equal(app.rejectionsFetchBanner(), '');
        assert.match(app.rejectionsEmptyMessage(), /No blocked signals/);
        assert.equal(app.rejectionsTrustStripStatus(), 'Blocked: 0');
    """)


def test_rejections_loading_excludes_failed_fetch():
    raw = _rejections_section(INDEX_HTML.read_text(encoding="utf-8"))
    assert "rejectionsFetchFailed()" in raw
    expression = next(
        c
        for c in bindings(INDEX_HTML, "x-if")
        if c.startswith("rejectionsPanel.loading") and "rejectionsFetchFailed()" in c
    )
    run_dashboard_js("""
        const expression = EXPRESSION;
        const visible = () => { with (app) { return eval(expression); } };
        app.rejectionsPanel.loading = true;
        app.rejectionsPanel.data = null;
        app.surfaceFetchHints.notrade = {loading: true};
        assert.equal(visible(), true);
        app.surfaceFetchHints.notrade.failed_fetch = true;
        assert.equal(visible(), false);
        app.surfaceFetchHints.notrade.failed_fetch = false;
        app.rejectionsPanel.data = {no_trade_signals: []};
        assert.equal(visible(), false);
    """.replace("EXPRESSION", json.dumps(expression)))


def test_rejections_fetch_uses_ops_degraded_not_surface_fetch_message():
    run_dashboard_js("""
        (async () => {
            app.tab = 'notrade';
            for (const thrown of [false, true]) {
                app.rejectionsPanel.data = {count: 1,
                    no_trade_signals: [{ticker: 'TEST'}]};
                app.surfaceFetchStateMessage = () => {
                    throw new Error('Wrong degraded vocabulary');
                };
                app.ccFetchJson = async (url, opts) => {
                    assert.equal(url, '/api/v7/playbook/no-trade');
                    assert.equal(opts.tab, 'notrade');
                    assert.equal(app.rejectionsPanel.loading, true);
                    if (thrown) throw new Error('HTTP 503');
                    return {ok: false, error: 'HTTP 503'};
                };
                await app.fetchRejections();
                assert.equal(app.rejectionsPanel.data, null);
                assert.equal(app.rejectionsPanel.loading, false);
                assert.equal(app.surfaceFetchHints.notrade.loading, false);
                assert.equal(app.surfaceFetchHints.notrade.failed_fetch, true);
                assert.equal(app.surfaceFetchHints.notrade.error,
                    app.opsDegradedLine('retry_recommended'));
                assert.ok(app.rejectionsFetchBanner());
                assert.equal(app.deployOpen(), false);
            }
        })().catch(error => { throw error; });
    """)


def test_rejections_header_uses_ops_degraded_on_failure():
    run_dashboard_js("""
        app.tab = 'notrade';
        app.rejectionsPanel.loading = false;
        // Broker handoff evidence isolates fetch-state copy from EXEC BLOCKED.
        app.today7.execution_readiness = {trade_handoff_ready: true};
        for (const [hints, state] of [
            [{failed_fetch: true, error: 'HTTP 503'}, 'retry_recommended'],
            [{failed_fetch: true, error: 'HTTP 500'}, 'unavailable'],
            [{stale: true}, 'fallback']
        ]) {
            app.surfaceFetchHints.notrade = hints;
            const summary = app.headerSummary();
            const copy = app.opsDegradedCopy(state);
            assert.equal(summary.badge, copy.badge);
            assert.equal(summary.explanation, copy.explanation);
            assert.equal(summary.next_action, copy.next_action);
            assert.equal(summary.show_decision_chips, false);
            assert.equal(app.deployOpen(), false);
        }
        // Missing execution evidence must outrank a stale-data badge.
        app.today7.execution_readiness = {};
        app.surfaceFetchHints.notrade = {stale: true};
        assert.equal(app.headerSummary().badge, 'EXEC BLOCKED');
        assert.equal(app.headerSummary().show_decision_chips, false);
    """)


def test_rejections_ops_degraded_vocabulary():
    assert "RETRY" in ops_degraded_line(OPS_STATE_RETRY_RECOMMENDED)
    assert "UNAVAILABLE" in ops_degraded_line(OPS_STATE_UNAVAILABLE)


def test_index_html_no_js_leaks():
    assert find_js_leaks_in_file(INDEX_HTML) == []
