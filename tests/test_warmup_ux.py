"""Warmup / cold-start UX helpers — parity with index.html Alpine."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    loading_session_recovery_line,
    today_mission_panel,
    trust_provenance_line,
    warmup_status_line,
    warmup_upgrade_queue_preview,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_warmup_status_line_states():
    assert "WARMING" in warmup_status_line(health_mode="loading")
    assert "OFFLINE" in warmup_status_line(api_reachable=False)
    assert "DEGRADED" in warmup_status_line(instant_degraded=True, health_mode="full")
    assert "LIVE" in warmup_status_line(health_mode="full")


def test_warmup_upgrade_queue_preview():
    assert "monitor queue" in warmup_upgrade_queue_preview(
        health_mode="loading", has_near_miss=True
    )
    assert warmup_upgrade_queue_preview(health_mode="full") == ""


def test_trust_provenance_line():
    line = trust_provenance_line(source="brief_fallback", freshness="DELAYED", age_minutes=45)
    assert "brief fallback" in line
    assert "45m ago" in line


def test_today_mission_panel_from_payload():
    m = today_mission_panel(
        risk_blockers=["WAIT gate"],
        near_miss=[{"ticker": "NVDA"}],
        top_ranked=[{"ticker": "AAPL"}],
    )
    assert m["card_gates"][0] == "WAIT gate"
    assert "WAIT gate" in m["blockers"]
    assert "NVDA" in m["monitors"]
    assert "system_blockers" in m
    assert "card_gates" in m


def test_loading_session_recovery_line():
    assert "8001" in loading_session_recovery_line(health_mode="loading")


def test_index_html_warmup_helpers_wired():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "/static/cc-helpers.js" in raw
    assert "warmupStatusLine()" in raw
    assert "warmupUpgradeQueue()" in raw
    assert "warmupContextStripVisible()" in raw
    assert "loadingSessionRecoveryLine()" in raw
    assert "trustProvenanceLine()" in raw
    assert "todayMissionPanel()" in raw
    assert "todayMissionMonitorsLabel()" in raw
    assert "severityBadgeClass(" in raw
