"""Tests for CC operator cleanup pass — dedupe, ranking, page capability."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.cc_state import attach_page_capability, attach_system_state
from src.services.operator_state_contract import (
    classify_rank_bucket,
    resolve_tab_id,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"
CC_APP = ROOT / "src/api/static/cc-app.js"


def test_resolve_tab_id_maps_ui_tabs():
    assert resolve_tab_id("scanners") == "scanners"
    assert resolve_tab_id("signals") == "signals"
    assert resolve_tab_id("stock-intel") == "dossier"


def test_classify_rank_bucket_deploy_and_reject():
    assert classify_rank_bucket(
        {"ticker": "AAA", "action": "TRADE", "ladder_bucket": "deploy_ready", "execution_ready": True}
    ) == "deployQualified"
    assert classify_rank_bucket({"ticker": "ZZZ", "action": "AVOID"}) == "rejectedAvoid"


def test_attach_page_capability_on_payload():
    payload = {
        "cc_state": {
            "tradeability_state": {"tradeability": "WAIT", "should_trade": False},
            "freshness_state": {"worst_tier": "STALE", "board_source": "fallback_brief"},
            "execution_state": {"engine_running": False, "state": "DISCONNECTED"},
            "board_decision_state": {"state": "RESEARCH_ONLY"},
        },
        "decision_authority": {"degraded": True, "gates_active": True},
        "trust": {"stale": True},
    }
    attach_system_state(payload)
    attach_page_capability(payload, "scanners", fetch_state="failed_fetch")
    cap = payload["page_capability"]
    assert cap["can_deploy"] is False
    assert cap["can_research"] is True
    assert cap["operator_sentence"]["scope"] == "discovery"
    assert "cached" in cap["operator_sentence"]["next_action"].lower()


def test_global_strip_dedupes_mission_panel_in_template():
    html = INDEX.read_text(encoding="utf-8")
    assert "today-mission-panel" in html
    assert "!globalSystemStripVisible()" in html
    assert html.count('data-cc="global-system-strip"') == 1


def test_playbook_display_rows_no_visible_fallback():
    js = CC_APP.read_text(encoding="utf-8")
    assert "playbookVisibleRows()" not in re.search(
        r"playbookDisplayRows\(\)\{[\s\S]*?\n      \},", js
    ).group(0)


def test_discovery_cached_fallback_sections_in_template():
    html = INDEX.read_text(encoding="utf-8")
    assert "discoveryShowCachedBreakouts()" in html
    assert "discoveryShowCachedPullbacks()" in html
    assert "discoveryPageStateVisible()" in html


def test_flow_mock_collapsed_in_template():
    html = INDEX.read_text(encoding="utf-8")
    assert "Mock / synthetic samples · debug" in html
    block = html[html.index("flowPanel.decision?.mock_flow") : html.index("Mock / synthetic samples · debug") + 60]
    assert "<details" in block


def test_guide_daily_flow_collapsed_quick_start():
    html = INDEX.read_text(encoding="utf-8")
    assert "Daily operator flow" in html
    assert "第 1 層 · Quick Start" in html
    qs = html.index("第 1 層 · Quick Start")
    assert html.rfind("<details", 0, qs) > html.rfind("Daily operator flow", 0, qs)


def test_dashboard_secondary_strips_hidden_when_global_strip():
    html = INDEX.read_text(encoding="utf-8")
    assert "dashboardSecondaryStripsVisible()" in html
    assert "playbookNoValidMonitors()" in html


def test_best_action_regime_parity_test_exists():
    from tests import test_best_action as tba

    assert hasattr(tba, "test_enrich_ranked_payload_respects_board_wait_gate")
