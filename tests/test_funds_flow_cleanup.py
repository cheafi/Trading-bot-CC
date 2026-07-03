"""Funds + Flow cleanup — research-only surfaces, overlay degraded, no allocator leakage."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def _funds_section() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("x-show=\"tab==='funds'\"")[1].split(
        "x-show=\"tab==='flow'\""
    )[0]


def test_funds_tab_research_lab_not_active_fund_manager():
    funds = _funds_section()
    assert "Fund Research Lab" in funds
    assert "Active Fund Manager" not in funds
    assert "fundResearchOnlyMode()" in funds


def test_funds_no_deploy_reduce_chip_when_research_only():
    funds = _funds_section()
    assert "REDUCED'].includes" in funds or "REDUCED'" in funds
    assert "fundResearchOnlyMode()" in funds


def test_flow_overlay_degraded_helpers_present():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "flowOverlayDegraded" in raw
    assert "flowOverlayDegradedShort" in raw
    assert "Flow overlay unavailable" in raw or "overlay degraded" in raw


def test_flow_research_block_now_blocker_next():
    flow = INDEX_HTML.read_text(encoding="utf-8").split("x-show=\"tab==='flow'\"")[1].split(
        "x-show=\"tab==='rs'\""
    )[0]
    assert "researchSurfaceBlock('flow')" in flow
    assert "BLOCKER" in flow
    assert "NEXT" in flow


def test_discovery_research_block_now_blocker_next():
    disc = INDEX_HTML.read_text(encoding="utf-8").split("x-show=\"tab==='scanners'\"")[1].split(
        "x-show=\"tab==='notrade'\""
    )[0]
    assert "researchSurfaceBlock('discovery')" in disc
    assert "BLOCKER" in disc


def test_cc_helpers_research_surface_block_exported():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "function researchSurfaceBlock" in js
    assert "researchSurfaceBlock: researchSurfaceBlock" in js


def test_ibkr_repair_checklist_has_state_pills():
    ibkr = INDEX_HTML.read_text(encoding="utf-8").split("x-show=\"tab==='ibkr'\"")[1].split(
        "x-show=\"tab==='portfolio'\""
    )[0]
    assert "ibkr-repair-checklist" in ibkr
    assert "ibkrRepairStepLabel" in ibkr


def test_funds_first_screen_blocker_field():
    from src.services.fund_manager_console import build_funds_first_screen, resolve_funds_mode

    mode = resolve_funds_mode(
        execution_readiness={"broker_connected": False},
        tradeability="NO_TRADE",
        cards=[],
        system_truth={"deploy_authority": False},
    )
    screen = build_funds_first_screen(funds_mode=mode)
    assert "blocker" in screen
    assert screen["live_allocation_label"] == "0%"
