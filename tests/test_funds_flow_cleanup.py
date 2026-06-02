"""Funds and Flow cleanup — constituent labels, honest metrics, flow hierarchy."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "_cc_instant.py"


def test_stale_ranked_bytes_fallback_score_display_mode():
    source = CC_INSTANT.read_text(encoding="utf-8")
    block = source.split("def _stale_ranked_bytes")[1].split("def _load_local_portfolio")[0]
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
    assert '"benchmark_return_pct": None' in source or '"benchmark_return_pct":None' in source


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
    exec(stub + "def _stale_fund_lab_bytes(reason: str) -> bytes:" + fn_block, ns)  # noqa: S102
    payload = json.loads(ns["_stale_fund_lab_bytes"]("backend importing — full API still loading"))
    inv = payload["console"]["investable_now"]
    assert inv["max_capital_allowed"] == "0%"
    assert inv["execution_ready"] == "No"
    assert inv["execution_state_label"] == "Blocked — backend loading"
    assert any("HTTP 503" in ln for ln in inv["allocation_lines"])
    why = payload["console"]["allocator_truth_strip"]["why_not_more"]
    assert len(why) == 2
    assert " · ".join(why) == "Backend importing — full API still loading · Live fund-lab pending"


def test_index_html_fund_metric_helpers_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "fundBenchmarkLine()",
        "fundFitDisplay(card)",
        "fundFitDecomposedLabel(card)",
        "fundWhyNotMoreLine(items)",
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
    assert "unavailable or pending" in text


def test_index_html_no_playbook_style_watch_fund_cards():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'display_name": f"{tk} watch"' not in text
    assert "Research constituent" in text or "fundFitDisplay" in text


def test_index_html_fund_fit_no_duplicate_fit_label():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "return 'Warming';" in text
    assert "'Fit warming'" not in text.split("fundFitDisplay(card)")[1].split("fundFitDecomposedLabel")[0]


def test_index_html_fund_card_tag_stack_simplified():
    text = INDEX_HTML.read_text(encoding="utf-8")
    card_hdr = text.split('<template x-for="card in (fundMonitor.data?.cards||[])"')[1].split("Current state")[0]
    assert ">Research</span>" in card_hdr
    assert ">RESEARCH</span>" not in card_hdr
    assert "card.stance!=='NEUTRAL'" in card_hdr
    assert "RESEARCH','NO_DATA'" in card_hdr


def test_index_html_why_not_more_middot_separator():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "fundWhyNotMoreLine(fundMonitor.console.allocator_truth_strip.why_not_more)" in text
    assert "list.join(' · ')" in text


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
    assert "Live actionable flow:" in text
    assert "Mock preview rows below" in text
    assert "flowCardDisclaimerShort(c)" in text
    assert "flowMockWarning()" not in text


def test_index_html_flow_overlay_summary_deduped():
    text = INDEX_HTML.read_text(encoding="utf-8")
    phrase = "flow cannot confirm entries"
    assert text.count(phrase) == 1
    assert "flowOverlaySummaryLine()" in text
    assert "function flowOverlaySummaryLine" in text or "flowOverlaySummaryLine(){" in text
    assert "flowOverlayPanelStyle()" in text
    assert "overlay degraded" in text


def test_index_html_flow_helpers_defined():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "flowOverlaySummaryLine()",
        "flowPmActionLabel(action)",
        "flowCardDisclaimerShort(c)",
        "flowCardDisclaimerDetail(c)",
        "flowShowMockPreviewSubtitle()",
        "flowRegimeContextHint()",
    ):
        assert fn in text, f"missing helper {fn}"


def test_index_html_preserves_flow_supporting_authority_mode():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "flow:'flow_supporting'" in text
    assert "flow_supporting" in text
    assert "CONFIRMATION ONLY" in text
