"""Primary operator posture must be MONITOR ONLY when deploy blocked — not SELECTIVE."""

from __future__ import annotations

from src.services.authority_engine import primary_operator_state
from src.services.operator_surface import build_operator_block
from src.services.system_truth import resolve_system_truth


def test_selective_regime_blocked_deploy_is_monitor_only():
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
            "qualification_levels": {"deploy_qualified": 2, "setup_qualified": 3},
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["primary"] != "SELECTIVE"
    assert posture["secondary"] == "SELECTIVE"


def test_all_surfaces_operator_block_monitor_only():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "top_5": [{"ticker": "X", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    for page in ("dashboard", "playbook", "discovery", "funds", "agent", "dossier"):
        block = build_operator_block(truth, page)
        assert "MONITOR ONLY" in block["now"] or block["primary"] == "MONITOR ONLY"
        assert block["now"] != "SELECTIVE"


def test_broker_offline_no_half_size_in_allowed():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"pilot_eligible": 1, "deploy_qualified": 0},
            "top_5": [{"ticker": "X", "action": "PILOT"}],
        },
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    block = build_operator_block(truth, "dashboard")
    assert "half size" not in block["allowed"].lower()
