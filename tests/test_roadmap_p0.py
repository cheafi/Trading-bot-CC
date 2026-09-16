"""P0 roadmap services — override journal, calibration, usage log, weekly IC."""

from __future__ import annotations

import pytest

from src.services.autonomous_learning_loop import (
    build_meta_intelligence_summary,
    persist_weekly_ic_digest,
    run_learning_cycle,
)
from src.services.calibration_report import build_calibration_report
from src.services.override_journal import (
    build_override_summary,
    cooldown_status,
    record_override,
)
from src.services.usage_log import (
    build_ai_usage_summary,
    build_usage_summary,
    record_ai_call,
    record_surface_event,
)
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
    monkeypatch.setattr(
        "src.services.usage_log._AI_LOG_PATH",
        data_dir / "ai_usage.jsonl",
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._STATE_PATH",
        data_dir / "autonomous_learning_loop_state.json",
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._WEEKLY_IC_CACHE",
        data_dir / "weekly_ic_digest_latest.json",
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._DATA_DIR",
        data_dir,
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
    record_ai_call(task="dossier_narrative", provider="local_llm", success=True, chars=120)
    summary = build_usage_summary()
    assert summary["total_events"] >= 2
    assert summary["by_surface"].get("tab_today", 0) >= 1
    assert "deletion_candidates" in summary
    assert summary["ai_usage"]["total_calls"] >= 1


def test_ai_usage_summary():
    record_ai_call(task="signal_reason", provider="azure", model="gpt-4o", success=True)
    ai = build_ai_usage_summary()
    assert ai["authority"] == "research_only"
    assert ai["total_calls"] >= 1
    assert ai["by_task"].get("signal_reason", 0) >= 1


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


def test_autonomous_learning_cycle_research_only(monkeypatch):
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._observe",
        lambda: {
            "closed_trades": 0,
            "forward_outcome_rows": 0,
            "forward_marks_with_r": 0,
            "journal_entries": 0,
        },
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._propose",
        lambda _trades: {
            "beliefs_due": 0,
            "ab_experiments_proposed": 0,
            "may_authorize_deploy": False,
        },
    )
    result = run_learning_cycle(phases=["observe", "calibrate", "propose"])
    assert result["authority"] == "research_only"
    assert result["may_authorize_deploy"] is False
    assert result["apply_changes"] is False
    assert "observe" in result
    assert "headline" in result


def test_meta_intelligence_summary_shape(monkeypatch):
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._observe",
        lambda: {
            "closed_trades": 0,
            "forward_outcome_rows": 0,
            "forward_marks_with_r": 0,
            "journal_entries": 0,
        },
    )
    run_learning_cycle(phases=["observe"])
    summary = build_meta_intelligence_summary()
    assert summary["authority"] == "research_only"
    assert summary["may_authorize_deploy"] is False
    assert "loop" in summary
    assert "ai_usage" in summary
    assert "calibration" in summary
    assert "idos_questions" in summary


def test_weekly_ic_digest_persist(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._WEEKLY_IC_CACHE",
        data_dir / "weekly_ic_digest_latest.json",
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._DATA_DIR",
        data_dir,
    )
    digest = persist_weekly_ic_digest(board={"system_state": {"deploy_open": False}})
    assert digest["authority"] == "research_only"
    assert (data_dir / "weekly_ic_digest_latest.json").is_file()
