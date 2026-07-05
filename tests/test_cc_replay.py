"""Whole-page Time Travel replay — service + UI contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_replay_service_lists_brief_dates():
    from src.services.cc_replay_service import list_replay_dates

    dates = list_replay_dates()
    assert dates
    assert all(len(d) == 10 and d[4] == "-" for d in dates)


def test_replay_today_payload_blocks_deploy():
    from src.services.cc_replay_service import build_replay_today_payload, list_replay_dates

    as_of = list_replay_dates()[0]
    payload = build_replay_today_payload(as_of)
    assert payload["replay_mode"] is True
    assert payload["replay_as_of"] == as_of
    assert payload["decision_authority"]["deploy_authority"] is False
    assert payload["decision_authority"]["gates"]["handoff"] is False
    assert "重播" in payload["narrative"]


def test_index_replay_ui_wiring():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "replayModeActive()" in html
    assert "enterWholePageReplay()" in html
    assert "exitWholePageReplay()" in html
    assert "ccReplayAsOf" in html
    assert "重播模式" in html
    assert "Time Travel · 重播任何日期" in html
    assert "ccReplayUrl(" in html
    assert "if(this.replayModeActive()) return 'diagnostic';" in html or "if(this.replayModeActive())return 'diagnostic';" in html.replace(" ","")
    assert "if(this.replayModeActive()) return true;" in html
