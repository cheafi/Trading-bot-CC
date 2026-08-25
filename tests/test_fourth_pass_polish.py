"""Fourth-pass CC polish — operator safe lines, partial markers, mission WAIT."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    operator_loading_safe_line,
    today_mission_wait_subtitle,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
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
    assert "CCHelpers.operatorLoadingSafeLine" in raw


def test_cc_helpers_fourth_pass_exports():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "operatorLoadingSafeLine" in js
    assert "todayMissionWaitSubtitle" in js


def test_degraded_banners_partial_exists():
    body = PARTIAL.read_text(encoding="utf-8")
    assert 'data-cc="instant-degraded-banner"' in body
    assert 'data-cc="warmup-context-strip"' in body
    assert "operatorLoadingSafeLine()" in body


def test_build_cc_template_script_present():
    assert BUILD_SCRIPT.is_file()
