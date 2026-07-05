"""Actionable Today panel + paper-first daily trading authority."""

from __future__ import annotations

import os

import pytest

from src.services.authority_engine import primary_operator_state
from src.services.cc_daily_trading import (
    build_actionable_today,
    build_actionable_today_card,
    is_trade_display_qualified,
)


@pytest.fixture(autouse=True)
def _daily_mode(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    monkeypatch.setenv("CC_DEFAULT_AUTHORITY", "paper_first")


def _paper_truth() -> dict:
    return {
        "deploy_authority": False,
        "deploy_authority_tier": "paper_only",
        "paper_deploy_available": True,
        "regime_state": "SELECTIVE",
        "broker_freshness": "offline",
        "operator_tier_now": "PAPER DEPLOY · 紙上可試 · Paper deploy available",
    }


def _ko_row() -> dict:
    return {
        "ticker": "KO",
        "action": "WATCH",
        "grade": "B+",
        "score": 7.2,
        "risk_reward": 2.0,
        "entry_price": 62.5,
        "stop_price": 60.0,
        "target_price": 66.0,
    }


def test_paper_only_actionable_today_non_empty():
    truth = _paper_truth()
    panel = build_actionable_today([_ko_row()], system_truth=truth)
    assert panel["count"] >= 1
    assert panel["cards"][0]["ticker"] == "KO"
    assert panel["cards"][0]["paper_draft_enabled"] is True


def test_paper_only_primary_not_monitor_only():
    posture = primary_operator_state(_paper_truth())
    assert posture["primary"] != "MONITOR ONLY"
    assert "PAPER" in posture["primary"].upper()


def test_broker_offline_handoff_disabled_paper_draft_enabled():
    card = build_actionable_today_card(
        _ko_row(),
        deploy_tier="paper_only",
        deploy_authority=False,
        broker_offline=True,
    )
    assert card["paper_draft_enabled"] is True
    assert card["ibkr_handoff_enabled"] is False


def test_live_card_handoff_when_allowed():
    card = build_actionable_today_card(
        {**_ko_row(), "action": "TRADE", "execution_ready": True},
        deploy_tier="allowed",
        deploy_authority=True,
        broker_offline=False,
    )
    assert card["ibkr_handoff_enabled"] is True


def test_trade_display_qualified_structure_and_rr():
    assert is_trade_display_qualified(_ko_row())
    assert not is_trade_display_qualified(
        {"ticker": "KO", "grade": "C", "score": 5.5, "risk_reward": 2.0, "action": "WATCH"}
    )
    assert not is_trade_display_qualified(
        {"ticker": "KO", "grade": "B+", "score": 7.0, "risk_reward": 1.2, "action": "WATCH"}
    )
