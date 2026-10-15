"""Unified surface rule maps — IDOS overlays + research contract."""

from __future__ import annotations

from src.services.research_safety import research_safety_contract
from src.services.surface_authority import AUTHORITY_RESEARCH, resolve_authority
from src.services.surface_rule_maps import (
    RESEARCH_ONLY_SURFACE_KEYS,
    all_required_surface_modes,
    research_overlay_for_surface,
    surface_mode_for_ui_tab,
)


def test_all_header_modes_have_rule_map_entry():
    modes = set(all_required_surface_modes())
    assert "strategy_lab_research" in modes
    assert "agent_monitoring" in modes
    assert modes >= set(surface_mode_for_ui_tab(t) for t in ("strategy-lab", "shadow", "reports"))


def test_research_tabs_always_research_authority():
    for tab in ("strategy_lab", "agent", "shadow", "reports"):
        auth = resolve_authority(tab, tradeability="TRADE", deployable_count=5)
        assert auth["authority"] == AUTHORITY_RESEARCH


def test_research_contract_pipeline_stops_shadow():
    c = research_safety_contract(surface="shadow")
    assert c["pipeline_stops_at"] == "journal_only"
    assert c["idos"]["act"] == "Improve watch rules; no deploy"


def test_research_contract_strategy_lab_playbook():
    overlay = research_overlay_for_surface("strategy-lab")
    assert overlay["pipeline_stops_at"] == "playbook_review"


def test_research_only_surface_keys_include_lab():
    assert "strategy_lab" in RESEARCH_ONLY_SURFACE_KEYS
    assert "today" not in RESEARCH_ONLY_SURFACE_KEYS
