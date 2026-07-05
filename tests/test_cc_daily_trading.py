"""Daily trading mode — paper deploy, pilot path, board gate, qualification tiers."""

from __future__ import annotations

import os

import pytest

from src.services.authority_engine import primary_operator_state
from src.services.cc_daily_trading import (
    TIER_ALLOWED,
    TIER_BLOCKED,
    TIER_PAPER_ONLY,
    TIER_PILOT_ONLY,
    is_daily_pilot_row,
    is_daily_trading_mode,
    resolve_board_gate,
    resolve_deploy_authority_tier,
)
from src.services.operator_surface import build_operator_block
from src.services.system_truth import resolve_system_truth


def test_daily_mode_env_toggle(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    assert is_daily_trading_mode() is True
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "0")
    assert is_daily_trading_mode() is False
    monkeypatch.delenv("CC_DAILY_TRADING_MODE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert is_daily_trading_mode() is False


def test_selective_board_gate_only_in_daily_mode(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    assert resolve_board_gate("SELECTIVE") == "selective"
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "0")
    assert resolve_board_gate("SELECTIVE") == "wait"


def test_paper_only_when_broker_offline_trade_qualified(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    tier = resolve_deploy_authority_tier(
        {
            "decision_authority": {
                "authority_level": "deploy",
                "allows_trade_labels": True,
                "gates_active": False,
            },
        },
        board_gate="selective",
        execution_gate="offline",
        brief_freshness="fresh",
        ranked_board_freshness="fresh",
        broker_freshness="offline",
        market_data_freshness="fresh",
        regime_state="SELECTIVE",
        trade_qualified=2,
        execution_qualified=0,
        live_deploy_allowed=False,
    )
    assert tier == TIER_PAPER_ONLY


def test_live_deploy_when_execution_qualified_broker_ready(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    tier = resolve_deploy_authority_tier(
        {"decision_authority": {"authority_level": "deploy", "allows_trade_labels": True}},
        board_gate="open",
        execution_gate="ready",
        brief_freshness="fresh",
        ranked_board_freshness="fresh",
        broker_freshness="fresh",
        market_data_freshness="fresh",
        regime_state="TRADE",
        trade_qualified=1,
        execution_qualified=1,
        live_deploy_allowed=True,
    )
    assert tier == TIER_ALLOWED


def test_pilot_path_when_pilot_eligible(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    tier = resolve_deploy_authority_tier(
        {
            "decision_authority": {"authority_level": "deploy", "allows_trade_labels": True},
            "pilot_eligible_count": 2,
        },
        board_gate="selective",
        execution_gate="ready",
        brief_freshness="fresh",
        ranked_board_freshness="fresh",
        broker_freshness="fresh",
        market_data_freshness="fresh",
        regime_state="SELECTIVE",
        trade_qualified=1,
        execution_qualified=0,
        live_deploy_allowed=False,
    )
    assert tier == TIER_PILOT_ONLY


def test_gates_active_blocks_paper_even_in_daily_mode(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {
                "deploy_qualified": 2,
                "setup_qualified": 3,
                "trade_qualified": 2,
            },
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority_tier"] == TIER_BLOCKED
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    block = build_operator_block(truth, "dashboard")
    assert block["now"] == "MONITOR ONLY · Deploy blocked"


def test_daily_pilot_row_b_plus_structure(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    row = {
        "ticker": "AAPL",
        "grade": "B+",
        "score": 7.2,
        "risk_reward": 2.0,
        "stop_price": 180,
        "action": "WATCH",
        "execution_ready": False,
    }
    assert is_daily_pilot_row(row, regime_state="SELECTIVE") is True


def test_qualification_counts_on_dashboard_truth(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "allows_trade_labels": True,
                "gates_active": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {
                "setup_qualified": 4,
                "trade_qualified": 2,
                "execution_qualified": 0,
                "deploy_qualified": 0,
            },
            "top_5": [{"ticker": "NVDA", "action": "WATCH", "grade": "B+", "score": 7.5}],
        },
        cc_header={"data_tier": "FRESH", "ibkr_connected": False},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority_tier"] == TIER_PAPER_ONLY
    assert "Trade-qualified: 2" in truth["qualification_counts_line"]
    assert truth["daily_use_zh"]
