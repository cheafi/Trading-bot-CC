"""Agent page — single blocker line from system_truth."""

from __future__ import annotations

from src.services.system_truth import mission_blockers_from_truth, resolve_system_truth


def test_agent_single_blocker_compact():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "NO_TRADE", "should_trade": False},
            "decision_authority": {"authority_level": "suspended", "gates_active": True},
            "execution_readiness": {"engine_running": False},
            "qualification_levels": {"deploy_qualified": 0},
        },
        cc_header={},
        ops_console={"engine_running": False},
    )
    truth["agent_blocker_compact"] = True
    blockers = mission_blockers_from_truth(truth)
    assert len(blockers) == 1
    assert blockers[0]


def test_mission_blockers_deduped():
    truth = resolve_system_truth(
        {
            "trust": {"stale": True},
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0},
        },
        cc_header={"data_tier": "STALE"},
        ops_console={},
    )
    blockers = mission_blockers_from_truth(truth, limit=6)
    assert len(blockers) == len(set(blockers))
    assert all(isinstance(b, str) for b in blockers)
