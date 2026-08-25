"""Tests for BDR operator summary builder."""

from __future__ import annotations

from src.services.bdr_operator_summary import (
    build_bdr_operator_summary,
    format_bdr_summary_text,
)


def _wait_state():
    return {
        "market_regime": {
            "tradeability": "WAIT",
            "honest_tradeability": "WAIT",
            "should_trade": False,
            "trend": "SIDEWAYS",
            "risk_state": "NEUTRAL",
        },
        "cc_state": {"tradeability_state": {"tradeability": "WAIT", "should_trade": False}},
        "system_state": {
            "tradeability": "WAIT",
            "deploy_open": False,
            "repair_priority": "restore IBKR session",
        },
        "decision_authority": {
            "gates_active": True,
            "gates": {
                "regime_wait": True,
                "broker_offline": True,
                "data_stale": False,
            },
            "degraded_copy": {
                "decision_authority_line": "Decision authority: research-only",
            },
        },
        "execution_readiness": {
            "ibkr_connected": False,
            "broker_connected": False,
            "readiness_label": "OFFLINE",
        },
        "dashboard_monitors": ["AMD", "NVDA"],
    }


def test_bdr_summary_wait_zero_deploy_ibkr_down():
    rows = [
        {
            "rank": 1,
            "ticker": "AMD",
            "action": "AVOID",
            "risk_reward": 1.6,
            "avoid_reason": "R:R below deploy bar",
        },
        {
            "rank": 2,
            "ticker": "NVDA",
            "action": "WATCH",
            "risk_reward": 2.1,
            "invalidation": "Needs volume confirmation",
        },
    ]
    summary = build_bdr_operator_summary(
        _wait_state(),
        rows,
        ibkr_status={"connected": False, "gateway_reachable": False},
        ops={"breaker": False, "running": False},
        unlock_deploy={
            "conditions": [
                {"key": "regime", "met": False, "detail": "Current: WAIT"},
                {"key": "deployable", "met": False, "detail": "0 deploy-qualified"},
                {"key": "broker", "met": False, "detail": "OFFLINE"},
                {"key": "board", "met": True, "detail": "2 watch-qualified"},
            ]
        },
    )
    assert summary["decision_code"] == "NO_TRADE"
    assert "Monitor only" in summary["decision_line"]
    assert summary["deploy_qualified_count"] == 0
    assert summary["gates_active"] is True
    keys = {g["key"] for g in summary["hard_gates_blocking"]}
    assert "regime" in keys
    assert "broker" in keys
    assert "deploy_count" in keys
    assert len(summary["rr_quality_table"]) == 2
    assert summary["what_to_do_now"]["do_not_deploy"]
    assert len(summary["unlock_checklist"]) == 4
    assert "AMD" in summary["text"] or "AMD" in str(summary["what_to_do_now"])
    text = format_bdr_summary_text(summary)
    assert "**Decision:**" in text
    assert "Hard gates blocking" in text


def test_bdr_summary_never_deploy_when_gates_closed():
    state = {
        "market_regime": {
            "tradeability": "SELECTIVE",
            "should_trade": True,
            "trend": "UPTREND",
        },
        "system_state": {"deploy_open": False},
        "decision_authority": {"gates_active": True, "gates": {"broker_offline": True}},
        "execution_readiness": {"ibkr_connected": False},
    }
    rows = [
        {
            "ticker": "QCOM",
            "action": "TRADE",
            "execution_ready": True,
            "risk_reward": 3.0,
        }
    ]
    summary = build_bdr_operator_summary(state, rows, ibkr_status={"connected": False})
    assert summary["decision_code"] in ("SELECTIVE", "NO_TRADE")
    assert summary["decision_code"] != "DEPLOY"
    assert "DEPLOY. Selective" not in summary["decision_line"]


def test_bdr_deploy_when_gates_open():
    state = {
        "market_regime": {
            "tradeability": "TRADE",
            "should_trade": True,
            "trend": "UPTREND",
        },
        "system_state": {"deploy_open": True},
        "decision_authority": {"gates_active": False},
        "execution_readiness": {
            "ibkr_connected": True,
            "trade_handoff_ready": True,
            "unified_label": "HANDOFF READY",
        },
        "deploy_qualified_count": 1,
    }
    rows = [
        {
            "ticker": "QCOM",
            "action": "TRADE",
            "execution_ready": True,
            "risk_reward": 3.0,
        }
    ]
    summary = build_bdr_operator_summary(state, rows, ibkr_status={"connected": True})
    assert summary["decision_code"] == "DEPLOY"
    assert summary["deploy_qualified_count"] == 1
