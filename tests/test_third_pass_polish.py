"""Third-pass CC polish — banner precedence, loading session copy, mission panel."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    loading_session_recovery_line,
    ops_recovery_guide,
    today_mission_monitors_label,
    today_mission_panel,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_loading_session_recovery_line_only_when_loading():
    assert "port 8000" in loading_session_recovery_line(health_mode="loading")
    assert loading_session_recovery_line(health_mode="full") == ""
    assert "port 8000" in loading_session_recovery_line(cc_mode="LOADING")


def test_ops_recovery_guide_includes_port_line_when_loading():
    g = ops_recovery_guide(health_mode="loading", engine_running=True)
    assert any("port 8000" in r.lower() for r in g["retry"])


def test_today_mission_monitors_label_near_miss():
    label = today_mission_monitors_label(["NVDA", "AAPL"], near_miss_count=2)
    assert "2" in label
    assert "near-miss" in label


def test_today_mission_panel_monitors_label_field():
    m = today_mission_panel(near_miss=[{"ticker": "X"}], top_ranked=[{"ticker": "Y"}])
    assert m["near_miss_count"] == 1
    assert "near-miss" in m["monitors_label"]


def test_index_html_third_pass_wiring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="instant-degraded-banner"' in raw
    assert 'data-cc="warmup-context-strip"' in raw
    assert 'data-cc="today-mission-panel"' in raw
    assert "loadingSessionRecoveryLine()" in raw
    assert "todayMissionMonitorsLabel()" in raw
    assert "CCHelpers.warmupContextStripVisible" in raw
    assert "CCHelpers.instantDegradedBannerHint" in raw


def test_cc_helpers_third_pass_exports():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "warmupContextStripVisible" in js
    assert "loadingSessionRecoveryLine" in js
    assert "instantDegradedBannerHint" in js
    assert "todayMissionMonitorsLabel" in js
