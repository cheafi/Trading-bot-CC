"""Tests for forward outcomes hook on trade close."""

from __future__ import annotations

import json
from pathlib import Path

from src.engines.learning_loop import LearningLoopPipeline


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
