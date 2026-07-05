"""Paper queue collapsed as Simulation Drafts when deploy blocked."""

from __future__ import annotations

from src.services.system_truth import resolve_system_truth


def test_deploy_blocked_truth_for_simulation_drafts_ui():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0},
        },
        cc_header={},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is False
    assert "Blocked" in truth["truth_strip"]
    assert truth["primary_blocker"]


def test_deploy_open_allows_queue_expansion_signal():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
                "source": "live",
            },
            "qualification_levels": {"deploy_qualified": 1},
            "execution_ready_count": 1,
            "execution_readiness": {"trade_handoff_ready": True, "broker_connected": True},
        },
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is True
    assert "Authority: Open" in truth["truth_strip"]
