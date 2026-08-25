"""Backtest Lab cleanup — warning hierarchy, honest metrics, section labels."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "_cc_instant.py"


def test_stale_backtest_lab_honest_metrics():
    stub = """
import json
from datetime import datetime, timezone

def _parse_query(path):
    return {"ticker": "AAPL", "strategy": "all", "period": "6mo"}
"""
    fn_block = (
        CC_INSTANT.read_text(encoding="utf-8")
        .split("def _stale_backtest_lab_bytes(path: str, reason: str) -> bytes:")[1]
        .split("\ndef _stale_ops_console_bytes(reason: str) -> bytes:")[0]
    )
    ns: dict = {}
    exec(stub + "def _stale_backtest_lab_bytes(path: str, reason: str) -> bytes:" + fn_block, ns)  # noqa: S102
    payload = json.loads(ns["_stale_backtest_lab_bytes"]("/api/v7/backtest-lab?ticker=AAPL", "backend importing"))
    review = payload["trade_level_review"]
    assert review["win_rate"] is None
    assert review["avg_win_pct"] is None
    assert review["avg_loss_pct"] is None
    assert review["trade_count"] == 0
    assert payload["attribution"]["benchmark_return_pct"] is None
    assert payload["walk_forward"]["verdict"] == "insufficient_data"
    assert payload["degraded"] is True


def test_stale_backtest_lab_window_label():
    source = CC_INSTANT.read_text(encoding="utf-8")
    assert '"label": "Recent window"' in source


def test_index_html_btlab_hierarchy_helpers_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "btLabAuthorityBlock()",
        "btLabEvidenceLine()",
        "btLabActionLine()",
        "btLabMetricDisplay(",
        "btLabPlainSummary()",
        "btLabVerdictLabel()",
        "btLabWindowLabel(w)",
        "btLabTradeReviewHeading()",
        "btLabTradeMetricsLine()",
        "btLabMetricsPending()",
    ):
        assert fn in text, f"missing helper {fn}"


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
    assert "Trade-level review · best strategy pending" in text
    assert "btLabVerdictLabel()" in chunk


def test_index_html_btlab_plain_summary_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "No usable walk-forward evidence yet. This page is diagnostic only." in text
    assert "btLabPlainSummary()" in text


def test_index_html_header_backtest_no_unstable_duplicate():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "Unstable walk-forward = lower trust" not in text


def test_fetch_surface_state_backtest_mode_unchanged():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "btlab:'backtest_research'" in text
    assert "backtest_research:{badge:'BACKTEST ONLY'" in text
