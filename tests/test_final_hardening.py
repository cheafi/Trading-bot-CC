"""Final hardening pass — partials, operator copy, data-cc selectors."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    operator_loading_safe_line,
    today_mission_monitors_column_hint,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
OPS_PARTIAL = ROOT / "src/api/templates/cc/partials/ops_recovery_runbook.html"
BUILD_SCRIPT = ROOT / "scripts/build-cc-template.mjs"


def test_today_mission_monitors_column_hint_wait():
    assert "WAIT" in today_mission_monitors_column_hint(wait_day=True)
    assert today_mission_monitors_column_hint(wait_day=False)


def test_operator_loading_safe_line_degraded_fetch():
    line = operator_loading_safe_line(fetch_failed=True)
    assert "fetch badges" in line
    assert "fallback" in line.lower()


def test_operator_loading_safe_line_backend_import():
    assert "backend import" in operator_loading_safe_line(health_mode="loading")


def test_index_html_final_hardening_data_cc():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="data-contract-strip"' in raw
    assert 'data-cc="ops-recovery-runbook"' in raw
    assert 'data-cc="discovery-surface"' in raw
    assert 'data-cc="dossier-surface"' in raw
    assert 'data-cc="playbook-surface"' in raw
    assert 'data-cc="market-strip-stale"' in raw
    assert "<!-- @cc-partial ops_recovery_runbook -->" in raw
    assert "todayMissionMonitorsColumnHint()" in raw


def test_ops_recovery_partial_exists():
    body = OPS_PARTIAL.read_text(encoding="utf-8")
    assert 'data-cc="ops-recovery-runbook"' in body
    assert "opsRecoveryGuide()" in body


def test_cc_helpers_final_hardening_exports():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "todayMissionMonitorsColumnHint" in js
    assert "fetchFailed" in js or "fetch badges" in js


def test_build_cc_template_includes_ops_recovery():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "ops_recovery_runbook" in script
    assert "guide" in script


def test_index_html_guide_partial_markers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "<!-- @cc-partial guide -->" in raw
    assert "CC · Clarity Console — Operator Guide" in raw


def test_index_html_bottom_nav_data_cc_nav():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    for tab in ("guide", "today", "signals", "scanners", "portfolio", "ibkr", "dossier", "ops"):
        assert f'data-cc-nav="{tab}"' in raw
