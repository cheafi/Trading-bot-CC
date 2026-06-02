"""CC consistency cleanup pass — mission panel, funnel parity, dossier authority."""

from __future__ import annotations

from pathlib import Path

from src.services.decision_truth_model import normalize_playbook_funnel
from src.services.fetch_surface_state import (
    today_mission_empty_blockers_copy,
    today_mission_system_blockers,
    today_mission_panel,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_today_mission_system_blockers_wires_infra():
    blk = today_mission_system_blockers(
        ibkr_ready=False,
        ibkr_short="OFFLINE",
        engine_running=False,
        data_tier="STALE",
        brief_fallback=True,
    )
    assert any("IBKR" in x for x in blk)
    assert "ENGINE OFF" in blk
    assert any("DATA STALE" in x for x in blk)
    assert any("FALLBACK" in x for x in blk)


def test_today_mission_panel_splits_system_and_card_gates():
    m = today_mission_panel(
        risk_blockers=[],
        system_blockers=["ENGINE OFF", "IBKR OFFLINE"],
        near_miss=[{"ticker": "X"}],
    )
    assert m["system_blockers"]
    assert m["card_gates"] == []
    assert "ENGINE OFF" in m["blockers"]
    assert today_mission_empty_blockers_copy(
        system_blockers=m["system_blockers"],
        card_gates=m["card_gates"],
    ) == "No card-level gate flags"


def test_playbook_funnel_label_uses_funnel_not_row_actions():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookFunnelLabel(rankedOpps.filter_funnel||today7.filter_funnel, null)" in raw
    idx = raw.index("playbookFunnelCounts(funnel")
    body = raw[idx : idx + 420]
    assert "rows.filter" not in body
    assert "watch_qualified_setups" in body


def test_index_mission_panel_system_blockers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "todayMissionSystemBlockersList()" in raw
    assert "system_blockers" in raw
    assert "card_gates" in raw
    assert "todayMissionBlockersTitle()" in raw
    assert "No card-level gate flags" in raw


def test_index_dossier_confirm_only_actions_blocked():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierActionsBlocked()" in raw
    assert "pending calibration" in raw
    assert ":disabled=\"dossierActionsBlocked()\"" in raw


def test_index_header_chip_groups():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "headerChipGroups()" in raw
    helpers = CC_HELPERS.read_text(encoding="utf-8")
    assert "partitionHeaderChips" in helpers
    assert "todayMissionSystemBlockers" in helpers


def test_playbook_wait_day_compression_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookWaitDayIntro()" in raw
    assert "Monitor ranking only" in raw


def test_normalize_watch_not_inflated_from_board_rows():
    out = normalize_playbook_funnel(
        {"watch_qualified_setups": 0, "universe_scanned": 40},
        opportunities=[{"action": "WATCH"}] * 5,
    )
    assert out["watch_qualified_setups"] == 0
