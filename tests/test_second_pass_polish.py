"""Second-pass CC polish — duplicate copy, severity vocabulary, helper wiring."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.fetch_surface_state import (
    STATE_EXECUTION_BLOCKED,
    STATE_FAILED_FETCH,
    STATE_LOADING,
    describe_fetch_state,
    severity_badge_class,
    surface_warmup_loading_line,
    surface_warmup_next_action,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"

API_STILL_LOADING = "API still loading — retry in a few seconds."


def _tab_block(tab_id: str, raw: str) -> str:
    """Rough slice between tab main open and next SURFACE comment."""
    start = raw.find(f"x-show=\"tab==='{tab_id}'\"")
    if start < 0:
        return ""
    nxt = raw.find("<!-- SURFACE", start + 20)
    return raw[start:nxt] if nxt > start else raw[start : start + 12000]


def test_no_duplicate_api_still_loading_in_ops_tab():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    ops = _tab_block("ops", raw)
    assert ops.count(API_STILL_LOADING) <= 1


def test_instant_banner_and_warmup_strip_do_not_duplicate_warming_line():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "warmupContextStripVisible()" in raw
    assert 'x-show="warmupStatusLine()" class="text-[8px] mt-1"' not in raw
    assert "CCHelpers.warmupContextStripVisible" in raw
    assert "instantBannerVisible" in raw


def test_severity_vocabulary_consistent_in_fetch_surface_state():
    assert severity_badge_class(STATE_FAILED_FETCH) == "pr"
    assert severity_badge_class(STATE_EXECUTION_BLOCKED) == "pr"
    assert severity_badge_class(STATE_LOADING) == "pa"
    assert severity_badge_class("failed_fetch_fallback") == "pr"
    assert severity_badge_class("unknown_state") == "pw"
    assert "refresh" in surface_warmup_next_action(STATE_LOADING).lower()
    assert surface_warmup_loading_line("ops_diagnostic").startswith("Ops API")
    assert "Retry shortly" not in surface_warmup_loading_line("ops_diagnostic")


def test_describe_fetch_state_failed_fetch_fallback_registered():
    d = describe_fetch_state("failed_fetch_fallback")
    assert d["badge"] == "FETCH FAILED"
    assert "fallback" in d["explanation"].lower()


def test_cc_helpers_wired_in_template():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "/static/cc-helpers.js" in raw
    assert "severityBadgeClass(" in raw
    assert "warmupContextStripVisible()" in raw


def test_cc_helpers_js_exports_severity_and_warmup():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "severityBadgeClass" in js
    assert "surfaceWarmupLoadingLine" in js
    assert "Retry shortly" not in js
