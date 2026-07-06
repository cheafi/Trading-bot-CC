"""Strategy Lab offline draft mode and action gating."""

from __future__ import annotations

from src.services.authority_engine import primary_operator_state
from src.services.strategy_lab_mode import (
    build_strategy_lab_page_state,
    build_strategy_validation_status,
    exclude_expired_brief_from_strategy_context,
    resolve_strategy_action_availability,
    resolve_strategy_lab_mode,
)
from src.services.system_truth import resolve_system_truth


def _degraded_truth(*, brief_age_days: int = 26) -> dict:
    return resolve_system_truth(
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
            "brief_status": {"age_days": brief_age_days},
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )


def test_no_brief_fallback_when_brief_age_over_two_days():
    truth = _degraded_truth(brief_age_days=26)
    assert exclude_expired_brief_from_strategy_context(truth) is True
    status = build_strategy_validation_status(truth)
    assert "fallback" not in status["brief"]["label"].lower()
    assert "Expired 26d" in status["brief"]["label"]
    assert status["brief"]["passed"] is False


def test_degraded_primary_is_research_only_not_selective():
    truth = _degraded_truth()
    page = build_strategy_lab_page_state(truth)
    assert page["primary"] == "RESEARCH ONLY"
    assert page["now"].startswith("RESEARCH ONLY")
    assert "SELECTIVE" not in page["now"]
    posture = primary_operator_state(truth)
    assert posture["secondary"] == "SELECTIVE"
    assert page["primary"] != posture["secondary"]


def test_offline_draft_only_disables_validation_committee_pine_playbook():
    truth = _degraded_truth()
    mode = resolve_strategy_lab_mode(truth)
    assert mode == "offline_draft_only"
    actions = resolve_strategy_action_availability(mode, truth)
    assert actions["generate_draft"]["enabled"] is True
    assert actions["save_draft"]["enabled"] is True
    assert actions["refresh_context"]["enabled"] is True
    assert actions["run_validation"]["enabled"] is False
    assert actions["committee_review"]["enabled"] is False
    assert actions["export_pine"]["enabled"] is False
    assert actions["send_playbook"]["enabled"] is False
    assert "offline" in actions["run_validation"]["reason"].lower()


def test_pine_disabled_until_validation_passes():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
            "qualification_levels": {"deploy_qualified": 2, "execution_qualified": 2},
            "top_5": [{"ticker": "XLP", "action": "WATCH", "execution_ready": True}],
        },
        cc_header={"data_tier": "FRESH", "ibkr_ready": True},
        ops_console={"engine_running": True},
    )
    mode = resolve_strategy_lab_mode(truth)
    actions = resolve_strategy_action_availability(mode, truth)
    assert actions["export_pine"]["enabled"] is False
    assert "validation" in actions["export_pine"]["reason"].lower()


def test_playbook_disabled_when_board_stale():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
            "qualification_levels": {"deploy_qualified": 2, "execution_qualified": 2},
            "top_5": [{"ticker": "XLP", "action": "WATCH", "execution_ready": True}],
            "scanner_degraded": True,
            "strategy_lab_validation": {
                "backtest": True,
                "walk_forward": True,
                "costs": True,
                "calibration": True,
            },
        },
        cc_header={"data_tier": "FRESH", "ibkr_ready": True},
        ops_console={"engine_running": True},
    )
    truth = {**truth, "ranked_board_freshness": "stale"}
    actions = resolve_strategy_action_availability("validated_research", truth)
    assert actions["send_playbook"]["enabled"] is False
    assert "board stale" in actions["send_playbook"]["reason"].lower()


def test_max_one_blocker_line():
    truth = _degraded_truth(brief_age_days=26)
    page = build_strategy_lab_page_state(truth)
    blocked = str(page["blocked"])
    assert blocked
    assert blocked.count("·") <= 1
    assert "Brief expired 26d" in blocked


def test_no_deploy_sizing_handoff_authority_when_blocked():
    truth = _degraded_truth()
    status = build_strategy_validation_status(truth)
    assert status["authority"]["deploy"] is False
    assert status["authority"]["sizing"] is False
    assert status["authority"]["handoff"] is False
    assert "no deploy" in status["authority"]["label"].lower()


def test_validated_research_enables_pine_when_gates_pass():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
            "qualification_levels": {"deploy_qualified": 2, "execution_qualified": 2},
            "top_5": [{"ticker": "XLP", "action": "WATCH", "execution_ready": True}],
            "strategy_lab_validation": {
                "backtest": True,
                "walk_forward": True,
                "costs": True,
                "calibration": True,
            },
        },
        cc_header={"data_tier": "FRESH", "ibkr_ready": True},
        ops_console={"engine_running": True},
    )
    mode = resolve_strategy_lab_mode(truth)
    assert mode == "validated_research"
    actions = resolve_strategy_action_availability(mode, truth)
    assert actions["export_pine"]["enabled"] is True
    assert actions["send_playbook"]["enabled"] is True
