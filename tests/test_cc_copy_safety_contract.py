"""Copy safety — blocked cards must not leak trade/sizing/handoff language."""

from __future__ import annotations

from src.services.fetch_surface_state import (
    execution_repair_one_liner,
    remove_trade_language_when_blocked,
    sanitize_blocked_candidate_copy,
)


def test_sanitize_blocked_candidate_copy_monitor_only():
    line = sanitize_blocked_candidate_copy(
        {"ticker": "KO", "primary_bucket": "Watch"},
        blocked=True,
        blocker="no pilot entry — deploy authority blocked",
    )
    assert "KO" in line
    assert "Watch candidate" in line
    assert "monitor only" in line
    assert "taking a Pilot entry" not in line


def test_remove_trade_language_when_blocked():
    raw = "KO decent setup — taking a Pilot entry · Deploy gate open · half size max"
    cleaned = remove_trade_language_when_blocked(raw, blocked=True)
    assert "taking a Pilot entry" not in cleaned
    assert "Deploy gate open" not in cleaned
    assert "half size" not in cleaned
    assert "monitor only" in cleaned
    assert "Blocked" in cleaned


def test_remove_trade_language_half_size_when_blocked():
    cleaned = remove_trade_language_when_blocked("Pilot only — half size, stop required", blocked=True)
    assert "half size" not in cleaned
    assert "no sizing" in cleaned.lower()


def test_execution_repair_one_liner_broker_offline():
    line = execution_repair_one_liner({"broker_freshness": "offline"})
    assert line.startswith("Execution blocked:")
    assert "Repair Console" in line
