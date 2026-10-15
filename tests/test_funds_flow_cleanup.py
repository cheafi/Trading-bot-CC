"""Funds and Flow cleanup — constituent labels, honest metrics, flow hierarchy."""

from __future__ import annotations

import json
from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "scripts" / "cc_instant.py"


def test_stale_ranked_bytes_fallback_score_display_mode():
    source = CC_INSTANT.read_text(encoding="utf-8")
    block = source.split("def _stale_ranked_bytes")[1].split(
        "def _load_local_portfolio"
    )[0]
    assert '"score_display_mode": "fallback_rank"' in block
    assert '"priority_tier": tier' in block
    assert "return _encode_degraded(payload, reason=reason)" in block


def test_stale_fund_lab_uses_constituent_labels_not_watch():
    source = CC_INSTANT.read_text(encoding="utf-8")
    assert 'display_name": f"{tk} watch"' not in source
    assert "Research constituent" in source
    assert "Sleeve sample member" in source
    assert "Candidate constituent" in source
    assert '"metrics_pending": True' in source or '"metrics_pending":True' in source
    assert (
        '"benchmark_return_pct": None' in source
        or '"benchmark_return_pct":None' in source
    )


def test_stale_fund_lab_honest_allocation_band():
    source = CC_INSTANT.read_text(encoding="utf-8")
    assert '"allocation_headline": "0% deployable — research context only"' in source
    assert '"max_capital_allowed": "0%"' in source
    assert '"execution_ready": "No"' in source
    assert "HTTP 503" in source
    assert "Backend importing — full API still loading" in source
    assert "Live fund-lab pending" in source


def test_stale_fund_lab_payload_allocation_fields():
    """Runtime check without importing _cc_instant (module starts servers on import)."""
    stub = """
import json
from datetime import datetime, timezone

def _load_latest_brief():
    return None

def _encode_degraded(payload, *, reason=None):
    return json.dumps(payload).encode()

"""
    fn_block = (
        CC_INSTANT.read_text(encoding="utf-8")
        .split("def _stale_fund_lab_bytes(reason: str) -> bytes:")[1]
        .split("\ndef _stale_no_trade_bytes(reason: str) -> bytes:")[0]
    )
    ns: dict = {}
    exec(
        stub + "def _stale_fund_lab_bytes(reason: str) -> bytes:" + fn_block, ns
    )  # noqa: S102
    payload = json.loads(
        ns["_stale_fund_lab_bytes"]("backend importing — full API still loading")
    )
    inv = payload["console"]["investable_now"]
    assert inv["max_capital_allowed"] == "0%"
    assert inv["execution_ready"] == "No"
    assert inv["execution_state_label"] == "Blocked — backend loading"
    assert any("HTTP 503" in ln for ln in inv["allocation_lines"])
    why = payload["console"]["allocator_truth_strip"]["why_not_more"]
    assert len(why) == 2
    assert (
        " · ".join(why)
        == "Backend importing — full API still loading · Live fund-lab pending"
    )


def test_index_html_fund_metric_helpers_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "fundBenchmarkLine()",
        "fundFitDisplay(card)",
        "fundFitDecomposedLabel(card)",
        "fundWhyNotMoreLine(fundMonitor.console.allocator_truth_strip.why_not_more)",
        "fundAllocationMaxCapital()",
        "fundExecutionReadyLabel()",
        "fundReturnDisplay(card)",
        "fundAlphaDisplay(card)",
        "fundDrawdownDisplay(card)",
        "fundEvidenceWindowLine(card)",
    ):
        assert fn in text, f"missing helper {fn}"


def test_index_html_no_fake_zero_benchmark_in_trust_strip():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "benchmark_return_pct||0" not in text
    run_dashboard_js("""
        app.fundMonitor.data = {degraded: true, benchmark_return_pct: null};
        assert.match(app.fundBenchmarkLine(), /unavailable or pending/);
        const pending = {metrics_pending: true, fund_return_pct: 0,
            excess_return_pct: 0, max_drawdown_pct: 0};
        assert.equal(app.fundReturnDisplay(pending), 'Backtest evidence unavailable');
        assert.equal(app.fundAlphaDisplay(pending), 'Metrics pending');
        assert.equal(app.fundDrawdownDisplay(pending), 'Metrics pending');
        app.fundMonitor.data = {benchmark_return_pct: 0};
        assert.equal(app.fundBenchmarkLine(), 'Benchmark SPY (0%)');
        const zero = {fund_return_pct: 0, excess_return_pct: 0,
            max_drawdown_pct: 0, benchmark_return_pct: 0};
        assert.equal(app.fundReturnDisplay(zero), '0%');
        assert.equal(app.fundAlphaDisplay(zero), '+0%');
        assert.equal(app.fundDrawdownDisplay(zero), '0%');
        assert.match(app.fundEvidenceWindowLine(zero), /BM 0%/);
    """)


def test_index_html_no_playbook_style_watch_fund_cards():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'display_name": f"{tk} watch"' not in text
    assert "Research constituent" in text or "fundFitDisplay" in text


def test_index_html_fund_fit_no_duplicate_fit_label():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'x-text="fundFitDisplay(card)"' in text
    run_dashboard_js("""
        assert.equal(app.fundFitDisplay({regime_fit: 'warming'}), 'Warming');
        assert.equal(app.fundFitDisplay({regime_fit: 'Fit warming'}), 'Warming');
        assert.equal(app.fundFitDisplay({regime_fit: 0}), '0%');
        assert.equal(app.fundFitDisplay({metrics_pending: true}), 'Metrics pending');
        assert.equal(app.fundFitDecomposedLabel({
            regime_fit_decomposed: {composite: 'warming'}}), 'Fit: warming');
    """)


def test_index_html_fund_card_tag_stack_simplified():
    text = INDEX_HTML.read_text(encoding="utf-8")
    card_hdr = text.split('<template x-for="card in (fundMonitor.data?.cards||[])"')[
        1
    ].split("Current state")[0]
    assert ">Research</span>" in card_hdr
    assert ">RESEARCH</span>" not in card_hdr
    assert "card.stance!=='NEUTRAL'" in card_hdr
    assert "RESEARCH','NO_DATA'" in card_hdr


def test_index_html_why_not_more_middot_separator():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert (
        "fundWhyNotMoreLine(fundMonitor.console.allocator_truth_strip.why_not_more)"
        in text
    )
    run_dashboard_js("""
        assert.equal(app.fundWhyNotMoreLine(['Backend importing', '', null,
            'Live fund-lab pending']), 'Backend importing · Live fund-lab pending');
        assert.equal(app.fundWhyNotMoreLine([]), '—');
    """)


def test_index_html_honest_allocation_band_rows():
    text = INDEX_HTML.read_text(encoding="utf-8")
    band = text.split("Honest allocation band")[1].split("Execution readiness")[0]
    assert "fundAllocationMaxCapital()" in band
    assert "fundExecutionReadyLabel()" in band
    assert "fundAllocationExecutionState()" in band
    assert "fundAllocationStatusNote()" in band
    assert "Execution ready?" in band


def test_index_html_flow_status_hierarchy():
    text = INDEX_HTML.read_text(encoding="utf-8")
    flow_start = text.find("x-show=\"tab==='flow'\"")
    assert flow_start > 0
    chunk = text[flow_start : flow_start + 8000]
    assert "flowStatusAuthority()" in chunk
    assert "flowStatusSource()" in chunk
    assert "flowStatusActionability()" in chunk
    assert "flowOverlaySummaryLine()" in chunk
    assert chunk.count("research-only") <= 1
    assert "flowTopComment()" not in chunk
    assert "Watch for stock confirm" not in chunk
    assert "Live flow candidates:" in text
    assert "Mock preview rows below" in text
    assert "flowCardDisclaimerShort(c)" in text
    assert "flowMockWarning()" not in text


def test_index_html_flow_overlay_summary_deduped():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "flowOverlaySummaryLine()" in text
    assert "flowOverlayPanelStyle()" in text
    assert "overlay degraded" in text
    run_dashboard_js("""
        app.flowPanel.decision = {count_live: 0,
            freshness: {synthetic: true}, calibration: {available: false},
            mock_flow: [{underlying: 'SYN'}]};
        const line = app.flowOverlaySummaryLine();
        assert.equal(line.split('flow cannot confirm entries').length - 1, 1);
        assert.equal(app.flowStatusSummary(), '');
        assert.equal(app.flowOverlayDegraded(), true);
        assert.notEqual(app.flowOverlayPanelStyle(), '');
        assert.equal(app.flowShowMockPreviewSubtitle(), true);
        assert.equal(app.flowKpiValue(), '—');
        app.flowPanel.decision = {count_live: 1,
            freshness: {synthetic: false, provider: 'Synthetic test provider'},
            calibration: {available: true}, live_flow: [{underlying: 'SYN'}]};
        assert.equal(app.flowOverlaySummaryLine(), '');
        assert.equal(app.flowOverlayPanelStyle(), '');
        assert.equal(app.flowOverlayDegraded(), false);
        assert.equal(app.flowShowMockPreviewSubtitle(), false);
        assert.match(app.flowStatusSummary(), /cannot replace regime/);
        assert.match(app.flowStatusAuthority(), /Confirm only/);
        assert.equal(app.flowStatusActionability(), 'Not standalone entry trigger');
    """)


def test_index_html_flow_helpers_defined():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "flowOverlaySummaryLine()",
        "flowCardDisclaimerShort(c)",
        "flowShowMockPreviewSubtitle()",
        "flowRegimeContextHint()",
    ):
        assert fn in text, f"missing binding {fn}"
    run_dashboard_js("""
        for (const action of ['BUYABLE_NOW', 'ACTIONABLE', 'PROMOTION_CANDIDATE']) {
            assert.match(app.flowPmActionLabel(action), /research candidate/);
        }
        assert.match(app.flowCardDisclaimerShort({underlying: 'SYN'}), /not deployable/);
        assert.match(app.flowCardDisclaimerDetail({underlying: 'NET'}), /synthetic/);
        assert.match(app.flowRegimeContextHint(), /Calibration pending/);
    """)


def test_index_html_preserves_flow_supporting_authority_mode():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "flowStatusAuthority()" in text
    run_dashboard_js("""
        app.tab = 'flow';
        assert.equal(app.pageSurface(), 'flow_supporting');
        assert.equal(app.surfaceShowsDecisionChips(app.pageSurface()), false);
        assert.notEqual(app.pageAuthorityMode(), 'active');
        assert.match(app.flowStatusAuthority(), /Confirm only/);
    """)
