"""Stabilization + soak + extraction pass — partials, recovery copy, selectors."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    engine_off_recovery_line,
    ibkr_login_to_ready_hint,
    route_abort_recovery_hint,
    stale_refresh_recovery_line,
    today_mission_safe_unlock_hint,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
GUIDE_PARTIAL = ROOT / "src/api/templates/cc/partials/guide.html"
BUILD_SCRIPT = ROOT / "scripts/build-cc-template.mjs"


def test_route_abort_recovery_hint_surfaces():
    assert "CONFIRM ONLY" in route_abort_recovery_hint("dossier")
    assert "Run Scanners" in route_abort_recovery_hint("discovery")
    assert route_abort_recovery_hint("")


def test_stale_and_engine_recovery_lines():
    assert "stale" in stale_refresh_recovery_line().lower()
    assert "Engine OFF" in engine_off_recovery_line()
    assert "READY" in ibkr_login_to_ready_hint()


def test_today_mission_safe_unlock_hint_wait():
    assert "Blocked: deploy" in today_mission_safe_unlock_hint(wait_day=True)
    assert "IBKR" in today_mission_safe_unlock_hint(wait_day=False, ibkr_ready=False)


def test_index_stabilization_selectors():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="guide-surface"' in raw
    assert 'data-cc-nav="today"' in raw
    assert 'data-cc-nav="guide"' in raw
    assert "<!-- @cc-partial guide -->" in raw
    assert "todayMissionSafeUnlockHint()" in raw
    assert "gate context below (not deploy)" in raw


def test_guide_partial_extracted():
    body = GUIDE_PARTIAL.read_text(encoding="utf-8")
    assert "guide-hero" in body
    assert "Layer 3 — Reference Manual" in body
    assert body.strip().endswith("</div>")


def test_build_script_includes_guide():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "guide:" in script
    assert "ops_recovery_runbook" in script
    assert "deploy_surfaces:" in script


def test_deploy_status_strip_selector():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="deploy-status-strip"' in raw


def test_cc_helpers_stabilization_exports():
    js = CC_HELPERS.read_text(encoding="utf-8")
    for name in (
        "routeAbortRecoveryHint",
        "staleRefreshRecoveryLine",
        "engineOffRecoveryLine",
        "ibkrLoginToReadyHint",
        "todayMissionSafeUnlockHint",
    ):
        assert name in js
