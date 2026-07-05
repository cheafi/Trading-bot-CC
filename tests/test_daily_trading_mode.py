"""Daily trading mode — paper deploy, pilot path, council thresholds."""

from __future__ import annotations

import os

import pytest

from src.services.authority_engine import (
    deploy_authority_tier,
    live_handoff_blocked,
    paper_deploy_allowed,
    primary_operator_state,
)
from src.services.cc_daily_trading import (
    council_deploy_rr_min,
    council_deploy_score_min,
    is_daily_pilot_row,
    is_daily_trading_mode,
    resolve_board_gate,
)
from src.services.playbook_truth import assign_primary_bucket
from src.services.system_truth import resolve_system_truth


def _fresh_today(**extra):
    base = {
        "market_regime": {"tradeability": "TRADE", "should_trade": True},
        "decision_authority": {
            "authority_level": "deploy",
            "gates_active": False,
            "allows_trade_labels": True,
            "source": "live",
        },
        "execution_readiness": {
            "broker_connected": False,
            "trade_handoff_ready": False,
        },
        "qualification_levels": {
            "trade_qualified": 2,
            "execution_qualified": 2,
            "deploy_qualified": 2,
        },
        "execution_ready_count": 2,
        "pilot_eligible_count": 0,
        "top_5": [{"ticker": "NVDA", "action": "TRADE", "execution_ready": True}],
    }
    base.update(extra)
    return base


@pytest.fixture
def daily_on(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "1")
    monkeypatch.setenv("APP_ENV", "production")


@pytest.fixture
def daily_off(monkeypatch):
    monkeypatch.setenv("CC_DAILY_TRADING_MODE", "0")
    monkeypatch.setenv("APP_ENV", "production")


def test_daily_mode_default_on_in_development(monkeypatch):
    monkeypatch.delenv("CC_DAILY_TRADING_MODE", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert is_daily_trading_mode() is True


def test_daily_mode_off_uses_strict_council_defaults(daily_off):
    assert is_daily_trading_mode() is False
    assert council_deploy_score_min() == 7.5
    assert council_deploy_rr_min() == 2.0


def test_daily_mode_on_uses_practical_thresholds(daily_on):
    assert is_daily_trading_mode() is True
    assert council_deploy_score_min() == 7.0
    assert council_deploy_rr_min() == 1.8


def test_selective_board_gate_in_daily_mode(daily_on):
    gate = resolve_board_gate(
        "SELECTIVE",
        brief_freshness="fresh",
        ranked_board_freshness="fresh",
    )
    assert gate == "selective"


def test_broker_offline_fresh_board_paper_only(daily_on):
    truth = resolve_system_truth(
        _fresh_today(),
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is False
    assert truth["deploy_authority_tier"] == "paper_only"
    assert truth["deployAuthority"] == "paper_only"
    assert truth["paper_deploy_available"] is True
    assert "BROKER_OFFLINE" in truth["reason_codes"]
    assert paper_deploy_allowed(truth)
    assert live_handoff_blocked(truth)


def test_broker_ready_execution_qualified_allowed(daily_on):
    truth = resolve_system_truth(
        _fresh_today(
            execution_readiness={
                "broker_connected": True,
                "trade_handoff_ready": True,
            },
        ),
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is True
    assert truth["deploy_authority_tier"] == "allowed"
    assert not live_handoff_blocked(truth)


def test_broker_offline_never_live_handoff(daily_on):
    truth = resolve_system_truth(
        _fresh_today(
            execution_readiness={
                "broker_connected": True,
                "trade_handoff_ready": True,
            },
        ),
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    truth_off = resolve_system_truth(
        _fresh_today(),
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is True
    assert truth_off["deploy_authority"] is False
    assert live_handoff_blocked(truth_off)


def test_daily_pilot_bucket_b_plus_not_execution_ready(daily_on):
    row = {
        "ticker": "KO",
        "grade": "B+",
        "score": 7.2,
        "risk_reward": 2.0,
        "action": "WATCH",
        "execution_ready": False,
    }
    assert is_daily_pilot_row(row, regime_state="SELECTIVE")
    assert assign_primary_bucket(row, regime_state="SELECTIVE") == "Pilot"


def test_paper_operator_copy(daily_on):
    truth = resolve_system_truth(
        _fresh_today(),
        cc_header={"data_tier": "FRESH"},
    )
    posture = primary_operator_state(truth)
    assert "Paper deploy" in posture["now"] or "紙上" in posture["now"]
    assert deploy_authority_tier(truth) == "paper_only"


def test_qualification_counts_line_includes_paper(daily_on):
    truth = resolve_system_truth(
        _fresh_today(),
        cc_header={"data_tier": "FRESH"},
    )
    line = truth.get("qualification_counts_line") or ""
    assert "Paper-qualified" in line or "Trade-qualified" in line
