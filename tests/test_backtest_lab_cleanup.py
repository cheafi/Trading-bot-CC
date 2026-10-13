"""Backtest Lab cleanup — warning hierarchy, honest metrics, section labels."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "scripts" / "cc_instant.py"
CC_APP = ROOT / "src" / "api" / "static" / "cc-app.js"


def _load_stale_backtest_lab():
    """Load real definitions without executing launcher side effects."""
    tree = ast.parse(CC_INSTANT.read_text(encoding="utf-8"), filename=str(CC_INSTANT))
    required = {
        "_parse_query",
        "_stamp_instant_degraded",
        "_encode_degraded",
        "_stale_backtest_lab_bytes",
    }
    optional = {"_instant_operator_state", "_apply_instant_operator_state"}
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in required | optional
    ]
    assert required <= {
        node.name for node in definitions
    }, "Missing launcher dependencies"
    banners = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DEGRADED_BANNER"
            for target in node.targets
        )
    ]
    assert len(banners) == 1, "Expected one real DEGRADED_BANNER definition"
    namespace: dict = {"json": json}
    module = ast.Module(body=[*banners, *definitions], type_ignores=[])
    exec(compile(module, str(CC_INSTANT), "exec"), namespace)  # noqa: S102
    return namespace["_stale_backtest_lab_bytes"]


def _js_method(name: str) -> str:
    source = CC_APP.read_text(encoding="utf-8")
    match = re.search(
        rf"^[ \t]*{re.escape(name)}\s*\([^\n)]*\)\s*\{{" r".*?^[ \t]*\}[ \t]*,[ \t]*$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Missing JavaScript method {name}"
    return match.group(0)


def test_stale_backtest_lab_honest_metrics():
    stale_backtest_lab = _load_stale_backtest_lab()
    payload = json.loads(
        stale_backtest_lab("/api/v7/backtest-lab?ticker=AAPL", "backend importing")
    )
    review = payload["trade_level_review"]
    assert review["win_rate"] is None
    assert review["avg_win_pct"] is None
    assert review["avg_loss_pct"] is None
    assert review["trade_count"] == 0
    assert payload["attribution"]["benchmark_return_pct"] is None
    assert payload["walk_forward"]["verdict"] == "insufficient_data"
    assert payload["degraded"] is True
    assert payload["research_only"] is True
    assert payload["instant_degraded"] is True
    assert payload["trust"]["stale"] is True
    assert payload["core_backtest"]["strategies"] == []
    assert payload["core_backtest"]["best_strategy"] is None
    assert payload["core_backtest"]["equity_chart"] == {
        "bh": [],
        "strategy": [],
        "signals": [],
    }
    assert payload["attribution"]["ranked"] == []
    assert review["strategy"] is None


def test_stale_backtest_lab_uses_real_query_parser():
    stale_backtest_lab = _load_stale_backtest_lab()
    payload = json.loads(
        stale_backtest_lab(
            "/api/v7/backtest-lab?ticker=msft&strategy=swing&period=2y",
            "backend importing",
        )
    )
    assert payload["ticker"] == "MSFT"
    assert payload["core_backtest"]["ticker"] == "MSFT"
    assert payload["strategy"] == "swing"
    assert payload["period"] == "2y"


def test_stale_backtest_lab_window_label():
    source = CC_INSTANT.read_text(encoding="utf-8")
    assert '"label": "Recent window"' in source


def test_index_html_btlab_hierarchy_helpers_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "btLabAuthorityBlock()",
        "btLabEvidenceLine()",
        "btLabActionLine()",
        "btLabPlainSummary()",
        "btLabVerdictLabel()",
        "btLabWindowLabel(w)",
        "btLabTradeReviewHeading()",
        "btLabTradeMetricsLine()",
    ):
        assert fn in text, f"missing helper {fn}"
        _js_method(fn.split("(")[0])
    for name in ("btLabMetricDisplay", "btLabMetricsPending"):
        _js_method(name)


def test_index_html_btlab_no_duplicate_warning_blocks():
    text = INDEX_HTML.read_text(encoding="utf-8")
    btlab_start = text.find("x-show=\"tab==='btlab'\"")
    assert btlab_start > 0
    chunk = text[btlab_start : btlab_start + 12000]
    assert "btLabWalkForwardUnstableComment()" not in chunk
    assert "btLabAttributionLowValueComment()" not in chunk
    assert "btLabTopComment()" not in chunk
    assert "btLabTopCommentShort()" not in chunk
    assert chunk.count("not deployment authority") <= 2
    assert "Authority</strong>" in chunk
    assert "Evidence quality</strong>" in chunk
    assert "Action</strong>" in chunk


def test_index_html_btlab_no_fake_zero_win_rate_binding():
    text = INDEX_HTML.read_text(encoding="utf-8")
    btlab_start = text.find("x-show=\"tab==='btlab'\"")
    chunk = text[btlab_start : btlab_start + 12000]
    assert "win_rate+'%'" not in chunk
    assert "avg_win_pct+'%'" not in chunk
    assert "btLabTradeMetricsLine()" in chunk


def test_index_html_btlab_section_labels_complete():
    text = INDEX_HTML.read_text(encoding="utf-8")
    btlab_start = text.find("x-show=\"tab==='btlab'\"")
    chunk = text[btlab_start : btlab_start + 12000]
    assert "btLabWindowLabel(w)" in chunk
    assert "btLabTradeReviewHeading()" in chunk
    assert "Trade-level review · best strategy pending" in _js_method(
        "btLabTradeReviewHeading"
    )
    assert "btLabVerdictLabel()" in chunk


def test_index_html_btlab_plain_summary_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    expected = "No usable walk-forward evidence yet. This page is diagnostic only."
    assert expected in _js_method("btLabPlainSummary")
    assert "btLabPlainSummary()" in text


def test_index_html_header_backtest_no_unstable_duplicate():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "Unstable walk-forward = lower trust" not in text


def test_fetch_surface_state_backtest_mode_unchanged():
    source = CC_APP.read_text(encoding="utf-8")
    assert re.search(r"\bbtlab\s*:\s*['\"]backtest_research['\"]", source)
    assert re.search(
        r"\bbacktest_research\s*:\s*\{\s*badge\s*:\s*" r"['\"]BACKTEST ONLY['\"]",
        source,
    )


def test_backtest_metric_display_preserves_pending_null_and_real_zero():
    names = (
        "btLabMetricsPending",
        "btLabMetricDisplay",
        "btLabAttributionLowValue",
        "btLabAuthorityBlock",
    )
    methods = "\n".join(_js_method(name) for name in names)
    script = "const app = {" + methods + "};\n" + """
const assert = require('node:assert/strict');
const valid = () => ({
    walk_forward: {verdict: 'stable_across_windows'},
    trade_level_review: {trade_count: 5},
    attribution: {ranked: [{total_trades: 5}]},
});
for (const flag of ['degraded', 'research_only']) {
    app.btLab = {data: {...valid(), [flag]: true}};
    assert.equal(app.btLabMetricDisplay('Win', 75), 'Win · pending');
}
for (const verdict of ['insufficient_data', 'skipped']) {
    app.btLab = {data: {...valid(), walk_forward: {verdict}}};
    assert.equal(app.btLabMetricDisplay('Win', 0), 'Win · pending');
}
app.btLab = {data: {...valid(), trade_level_review: {trade_count: 0}}};
assert.equal(app.btLabMetricDisplay('Win', null), 'Win · pending');
app.btLab = {data: {...valid(), attribution: {ranked: []}}};
assert.equal(app.btLabMetricDisplay('Win', 75), 'Win · pending');
app.btLab = {data: valid()};
for (const missing of [null, undefined, '', 'invalid']) {
    assert.equal(app.btLabMetricDisplay('Win', missing), 'Win · unavailable');
}
assert.equal(app.btLabMetricDisplay('Win', 0), 'Win 0%');
assert.equal(app.btLabMetricDisplay('Win', 75), 'Win 75%');
assert.equal(
    app.btLabAuthorityBlock(),
    'Backtest research only — not deployment authority.',
);
"""
    result = subprocess.run(
        ["node", "-"],
        input=script,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
