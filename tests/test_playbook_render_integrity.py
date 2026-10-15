"""Playbook UI string integrity — no visible $1/$2 replace placeholders."""

from __future__ import annotations

import re
from pathlib import Path

from _dashboard_html_contract import bindings
from _dashboard_js_runtime import run_dashboard_js

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_playbook_unlock_detail_uses_capture_not_dollar_one():
    """Board counts come from the funnel, never a legacy validated label."""
    assert "playbookUnlockConditionDetail(c)" in bindings(INDEX_HTML, "x-text")
    run_dashboard_js("""
        const condition = {key: 'board', detail: '50 validated · data STALE'};
        app.rankedOpps.filter_funnel = {watch_qualified_setups: 3};
        app.rankedOpps.rows = Array.from({length: 5}, () => ({}));
        assert.equal(app.playbookUnlockConditionDetail(condition),
            '3 funnel watch-qualified · 5 board scan pool · data STALE');
        app.rankedOpps.rows = [];
        assert.equal(app.playbookUnlockConditionDetail(condition),
            '3 funnel watch-qualified · data STALE');
        app.rankedOpps.filter_funnel = {
            watch_qualified_setups: 0, triggered_setups: 7};
        assert.equal(app.playbookUnlockConditionDetail(condition),
            '7 scan-ranked (not watch-qualified) · data STALE');
        app.rankedOpps.filter_funnel = {};
        assert.equal(app.playbookUnlockConditionDetail(condition),
            '0 watch-qualified · data STALE');
        assert.equal(app.deployOpen(), false);
        assert.equal(app.playbookCanSendToIbkr({action: 'TRADE',
            execution_ready: true, entry_price: 100, stop_price: 95}), false);
    """)


def test_playbook_unlock_detail_replace_produces_numeric_count():
    """Exercise actual JS replacement, not a Python mirror of the algorithm."""
    run_dashboard_js("""
        for (const count of [0, 1, 50, 123]) {
            const result = app.playbookUnlockConditionDetail({key: 'data',
                detail: count + ' validated · data STALE'});
            assert.equal(result, count +
                ' scan-ranked (not watch-qualified) · data STALE');
            assert.ok(!/\\$[12]/.test(result));
        }
        assert.equal(app.playbookUnlockConditionDetail(null), '');
        assert.equal(app.playbookUnlockConditionDetail({detail: ''}), '');
        assert.equal(app.playbookUnlockConditionDetail({detail: 'Volume pending'}),
            'Volume pending');
    """)


def test_index_html_no_callback_replace_dollar_placeholders():
    """Audit actual scripts too now that JS lives outside index.html."""
    for path in (
        INDEX_HTML,
        ROOT / "src/api/static/cc-app.js",
        ROOT / "src/api/static/cc-helpers.js",
    ):
        raw = path.read_text(encoding="utf-8")
        assert not re.search(r"\([^)]*\)\s*=>\s*['\"]\$\d", raw), path
