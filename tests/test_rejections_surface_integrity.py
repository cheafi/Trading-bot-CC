"""Rejections tab fetch UX — single banner, ops degraded copy, surface hints."""

from __future__ import annotations

from pathlib import Path

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
    assert "surfaceFetchHints.notrade" in raw or "surfaceFetchHints[tab]" in raw
    assert "if(mode==='rejections_diagnostic')" in raw


def test_rejections_no_duplicate_fetch_failed_in_strip():
    raw = _rejections_section(INDEX_HTML.read_text(encoding="utf-8"))
    assert "rejectionsPanel.error" not in raw
    assert "FETCH FAILED — Network or server error prevented a fresh read." not in raw


def test_rejections_empty_copy_when_fetch_failed():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    section = _rejections_section(raw)
    assert "rejectionsEmptyMessage()" in section
    assert "Fresh rejection data unavailable; no blocked signals shown" in raw
    assert "No blocked signals available from the last readable batch" in raw


def test_rejections_loading_excludes_failed_fetch():
    raw = _rejections_section(INDEX_HTML.read_text(encoding="utf-8"))
    assert "rejectionsFetchFailed()" in raw
    assert "rejectionsPanel.loading && !rejectionsPanel.data && !rejectionsFetchFailed()" in raw


def test_rejections_fetch_uses_ops_degraded_not_surface_fetch_message():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    chunk = raw[raw.find("async fetchRejections"): raw.find("async fetchConviction")]
    assert "opsDegradedLine(degraded)" in chunk
    assert "surfaceFetchStateMessage" not in chunk


def test_rejections_header_uses_ops_degraded_on_failure():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "mode==='rejections_diagnostic'&&(fetchState==='failed_fetch'||fetchState==='stale')" in raw


def test_rejections_ops_degraded_vocabulary():
    assert "RETRY" in ops_degraded_line(OPS_STATE_RETRY_RECOMMENDED)
    assert "UNAVAILABLE" in ops_degraded_line(OPS_STATE_UNAVAILABLE)


def test_index_html_no_js_leaks():
    assert find_js_leaks_in_file(INDEX_HTML) == []
