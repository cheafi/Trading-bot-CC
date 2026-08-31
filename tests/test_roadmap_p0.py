"""P0 roadmap services — override journal, calibration, usage log, weekly IC."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.calibration_report import build_calibration_report
from src.services.override_journal import (
    build_override_summary,
    cooldown_status,
    record_override,
)
from src.services.usage_log import build_usage_summary, record_surface_event
from src.services.weekly_ic_digest import build_weekly_ic_digest


@pytest.fixture(autouse=True)
def _isolate_data_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(
        "src.services.override_journal._JOURNAL_PATH",
        data_dir / "override_journal.jsonl",
    )
    monkeypatch.setattr(
        "src.services.usage_log._LOG_PATH",
        data_dir / "surface_usage.jsonl",
    )
    yield


def test_record_override_and_summary():
    row = record_override(
        advice_class="cc_recommendation",
        action="ignored",
        reason="manual trade",
        ticker="AAPL",
    )
    assert row["authority"] == "research_only"
    assert row["ticker"] == "AAPL"
    summary = build_override_summary()
    assert summary["total"] >= 1
    assert summary["cooldown"]["cooldown_hours"] == 24


def test_cooldown_after_override():
    record_override(advice_class="deploy_gate", action="override", reason="test")
    status = cooldown_status(hours=24)
    assert status["in_cooldown"] is True
    assert status["last_override"] is not None


def test_usage_log_summary():
    record_surface_event(surface="tab_today", event="open", tab="today")
    record_surface_event(surface="buffett_strip", event="dismiss", tab="today")
    summary = build_usage_summary()
    assert summary["total_events"] >= 2
    assert summary["by_surface"].get("tab_today", 0) >= 1
    assert "deletion_candidates" in summary


def test_calibration_report_shape():
    report = build_calibration_report(limit=10)
    assert report["authority"] == "research_only"
    assert "sample" in report
    assert "headline" in report


def test_weekly_ic_digest_from_board():
    digest = build_weekly_ic_digest(
        board={
            "system_state": {"deploy_open": False},
            "best_action": {"best_trade": "MSFT"},
        }
    )
    assert digest["cadence"] == "weekly"
    assert digest["best_trade"] == "MSFT"
    assert len(digest["sections"]) >= 5
    assert digest["daily_ic"] is not None
