"""Playbook deploy gate copy — no 'Deploy gate open' when blocked."""

from __future__ import annotations

from src.services.playbook_truth import format_playbook_qualification_line
from src.services.system_truth import resolve_system_truth, system_truth_line


def test_no_deploy_gate_open_when_authority_blocked():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "qualification_levels": {
                "setup_qualified": 2,
                "trade_qualified": 1,
                "execution_qualified": 1,
                "deploy_qualified": 2,
            },
            "execution_ready_count": 2,
            "execution_readiness": {"broker_connected": False},
        },
        cc_header={},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is False
    line = system_truth_line(truth)
    qual = truth["qualification_line"]
    assert "Deploy gate open" not in line
    assert "gates open" not in line
    assert "Deploy gate open" not in qual
    assert "2 setup-qualified" in qual
    assert "0 deploy-qualified" in qual


def test_format_qualification_never_implies_open_gate():
    blocked = format_playbook_qualification_line(
        setup_qualified=2,
        deploy_qualified=0,
        deploy_authority=False,
        regime_state="NO_TRADE",
    )
    assert "gate open" not in blocked.lower()
    assert "TRADE" not in blocked or "trade-qualified" in blocked
