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
from src.services.system_truth import resolve_system_truth


def _paper_only_truth_payload() -> dict:
    return {
        "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
        "decision_authority": {
            "authority_level": "deploy",
            "gates_active": False,
            "allows_trade_labels": True,
        },
        "execution_readiness": {"broker_connected": False},
        "qualification_levels": {
            "trade_qualified": 2,
            "setup_qualified": 3,
            "deploy_qualified": 0,
        },
        "filter_funnel": {"trade_qualified_setups": 2},
        "top_5": [
            {
                "ticker": "KO",
                "action": "WATCH",
                "grade": "B+",
                "score": 7.2,
                "risk_reward": 2.0,
                "entry_price": 62.5,
                "stop_price": 60.0,
                "target_price": 66.0,
            }
        ],
    }


@pytest.fixture(autouse=True)
def _daily_mode(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    monkeypatch.setenv("CC_DEFAULT_AUTHORITY", "paper_first")


def test_paper_only_actionable_today_non_empty():
    truth = resolve_system_truth(_paper_only_truth_payload(), cc_header={"data_tier": "FRESH"})
    assert truth["deploy_authority_tier"] == "paper_only"
    panel = build_actionable_today(
        truth.get("top_5") or _paper_only_truth_payload()["top_5"],
        system_truth=truth,
    )
    assert panel["count"] >= 1
    assert panel["cards"][0]["ticker"] == "KO"
    assert panel["cards"][0]["paper_draft_enabled"] is True


def test_paper_only_primary_not_monitor_only():
    truth = resolve_system_truth(_paper_only_truth_payload(), cc_header={"data_tier": "FRESH"})
    posture = primary_operator_state(truth)
    assert posture["primary"] != "MONITOR ONLY"
    assert "PAPER" in posture["primary"].upper()


def test_broker_offline_handoff_disabled_paper_draft_enabled():
    truth = resolve_system_truth(_paper_only_truth_payload(), cc_header={"data_tier": "FRESH"})
    card = build_actionable_today_card(
        _paper_only_truth_payload()["top_5"][0],
        deploy_tier="paper_only",
        deploy_authority=False,
        broker_offline=True,
    )
    assert card["paper_draft_enabled"] is True
    assert card["ibkr_handoff_enabled"] is False


def test_live_deploy_still_requires_broker_and_execution():
    truth = resolve_system_truth(
        {
            **_paper_only_truth_payload(),
            "execution_readiness": {
                "broker_connected": True,
                "trade_handoff_ready": True,
            },
            "execution_ready_count": 1,
            "qualification_levels": {
                "trade_qualified": 1,
                "deploy_qualified": 1,
                "execution_qualified": 1,
            },
            "top_5": [
                {
                    "ticker": "NVDA",
                    "action": "TRADE",
                    "grade": "A",
                    "score": 8.5,
                    "risk_reward": 2.5,
                    "execution_ready": True,
                    "entry_price": 120,
                    "stop_price": 115,
                    "target_price": 130,
                }
            ],
        },
        cc_header={"data_tier": "FRESH", "ibkr_ready": True, "ibkr_connected": True},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is True
    assert truth["deploy_authority_tier"] == "allowed"


def test_trade_display_qualified_structure_and_rr():
    assert is_trade_display_qualified(
        {"ticker": "KO", "grade": "B+", "score": 7.0, "risk_reward": 1.6, "action": "WATCH"}
    )
    assert not is_trade_display_qualified(
        {"ticker": "KO", "grade": "C", "score": 5.5, "risk_reward": 2.0, "action": "WATCH"}
    )
    assert not is_trade_display_qualified(
        {"ticker": "KO", "grade": "B+", "score": 7.0, "risk_reward": 1.2, "action": "WATCH"}
    )
