"""Tests for forward outcomes hook on trade close and scheduler marks."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.engines.learning_loop import LearningLoopPipeline
from src.services.forward_outcomes import run_forward_outcome_marks


def test_record_closed_trade_writes_forward_outcome_stub(tmp_path, monkeypatch):
    outcomes = tmp_path / "forward_outcomes.jsonl"
    monkeypatch.setattr(
        "src.services.forward_outcomes._OUTCOMES_PATH",
        outcomes,
    )
    monkeypatch.setattr(
        "src.engines.learning_loop._TRADES_FILE",
        tmp_path / "closed_trades.jsonl",
    )
    loop = LearningLoopPipeline()
    loop.record_closed_trade(
        ticker="AAPL",
        direction="LONG",
        entry_price=100.0,
        exit_price=105.0,
        entry_time="2026-08-25T09:00:00Z",
        exit_time="2026-08-25T15:00:00Z",
        strategy_id="test-strat",
        decision_id="dec-AAPL-001",
        alpha_id="alpha-001",
    )
    assert outcomes.is_file()
    row = json.loads(outcomes.read_text(encoding="utf-8").strip())
    assert row["decision_id"] == "dec-AAPL-001"
    assert row["alpha_id"] == "alpha-001"
    assert row["horizon"] == "T+0"
    assert row["authority"] == "research_only"


def test_run_forward_outcome_marks_records_due_horizons(tmp_path, monkeypatch):
    outcomes = tmp_path / "forward_outcomes.jsonl"
    closed = tmp_path / "closed_trades.jsonl"
    closed.write_text(
        json.dumps(
            {
                "ticker": "AAPL",
                "decision_id": "dec-001",
                "exit_time": "2026-08-01",
                "r_multiple": 1.5,
                "alpha_id": "alpha-001",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.services.forward_outcomes._OUTCOMES_PATH", outcomes)
    monkeypatch.setattr("src.services.forward_outcomes._CLOSED_TRADES_PATH", closed)

    result = run_forward_outcome_marks(as_of=date(2026, 8, 25))
    assert result["recorded"] == 3
    assert result["skipped"] == 0
    rows = [json.loads(line) for line in outcomes.read_text(encoding="utf-8").splitlines()]
    assert {row["horizon"] for row in rows} == {"T+1", "T+5", "T+20"}
    assert all(row["decision_id"] == "dec-001" for row in rows)
    assert all(row["authority"] == "research_only" for row in rows)

    # Idempotent — second run must not duplicate
    again = run_forward_outcome_marks(as_of=date(2026, 8, 25))
    assert again["recorded"] == 0
    assert len(outcomes.read_text(encoding="utf-8").splitlines()) == 3


def test_run_forward_outcome_marks_skips_missing_decision_id(tmp_path, monkeypatch):
    outcomes = tmp_path / "forward_outcomes.jsonl"
    closed = tmp_path / "closed_trades.jsonl"
    closed.write_text(
        json.dumps({"ticker": "MSFT", "exit_time": "2026-08-01", "r_multiple": -1.0}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.services.forward_outcomes._OUTCOMES_PATH", outcomes)
    monkeypatch.setattr("src.services.forward_outcomes._CLOSED_TRADES_PATH", closed)

    result = run_forward_outcome_marks(as_of=date(2026, 8, 10))
    assert result["recorded"] == 0
    assert result["skipped"] == 1
    assert not outcomes.exists()


def test_run_forward_outcome_marks_no_closed_trades_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.services.forward_outcomes._CLOSED_TRADES_PATH",
        tmp_path / "missing.jsonl",
    )
    result = run_forward_outcome_marks(as_of=date(2026, 8, 25))
    assert result["recorded"] == 0
    assert result["reason"] == "no_closed_trades"
