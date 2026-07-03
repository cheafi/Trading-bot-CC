"""SystemTruth resolver — canonical freshness, gates, deploy authority."""

from __future__ import annotations

from src.services.system_truth import (
    build_morning_decision_line,
    build_reason_codes,
    format_engine_state_display,
    format_global_truth_strip,
    format_operator_sentence,
    reason_codes_to_copy,
    resolve_deploy_authority,
    resolve_system_truth,
    system_truth_line,
    unified_freshness_tier,
)


def test_unified_freshness_worst_tier_wins():
    assert unified_freshness_tier("fresh", "stale") == "STALE"
    assert unified_freshness_tier("fresh", "expired") == "EXPIRED"
    assert unified_freshness_tier("fresh", "fresh") == "FRESH"


def test_resolve_system_truth_wait_day_no_deploy():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "trust": {"stale": False, "source": "decision_engine", "freshness": "REAL_TIME"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
                "gates": {"regime_wait": True},
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0},
            "execution_ready_count": 0,
            "top_5": [{"ticker": "W", "action": "WATCH"}],
        },
        cc_header={"data_tier": "FRESH"},
        ops={"engine_running": True},
    )
    assert truth["regime_state"] == "WAIT"
    assert truth["board_gate"] == "wait"
    assert truth["deploy_authority"] is False
    assert "BOARD_WAIT" in truth["reason_codes"]
    assert "NO_DEPLOY_QUALIFIED" in truth["reason_codes"]
    assert truth["freshness_tier"] == "FRESH"


def test_resolve_system_truth_stale_data_single_tier():
    truth = resolve_system_truth(
        {
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {},
        },
        cc_header={"data_tier": "STALE"},
        ops={},
    )
    assert truth["market_data_freshness"] == "stale"
    line = system_truth_line(truth)
    assert "DATA STALE" not in line
    assert "DATA FRESH" not in line
    assert "Market:" in line


def test_morning_decision_line_format():
    line = build_morning_decision_line(
        {
            "regime_state": "NO_TRADE",
            "deploy_authority": False,
            "reason_codes": ["REGIME_NO_TRADE"],
        },
        best_candidate="",
    )
    assert line.startswith("Today: NO_TRADE")
    assert "monitor only" in line
    assert "Best candidate: none" in line


def test_reason_codes_deduped():
    codes = build_reason_codes(
        market_data_freshness="stale",
        ranked_board_freshness="stale",
        brief_freshness="fresh",
        engine_state="off",
        broker_freshness="offline",
        regime_state="WAIT",
        board_gate="wait",
        execution_gate="offline",
        deploy_authority=False,
        today={"qualification_levels": {"deploy_qualified": 0}},
    )
    assert len(codes) == len(set(codes))
    copy = reason_codes_to_copy(codes)
    assert all(isinstance(c, str) for c in copy)


def test_resolve_deploy_authority_requires_execution_ready():
    assert resolve_deploy_authority(
        decision_authority={
            "authority_level": "deploy",
            "gates_active": False,
            "allows_trade_labels": True,
            "source": "live",
        },
        execution_ready_count=1,
        tradeability="TRADE",
        should_trade=True,
    )
    assert not resolve_deploy_authority(
        decision_authority={
            "authority_level": "deploy",
            "gates_active": False,
            "allows_trade_labels": True,
            "source": "live",
        },
        execution_ready_count=0,
        tradeability="TRADE",
        should_trade=True,
    )


def test_format_global_truth_strip_scoped():
    strip = format_global_truth_strip(
        {
            "market_data_freshness": "fresh",
            "ranked_board_freshness": "stale",
            "brief_freshness": "expired",
            "brief_age_days": 21,
            "broker_freshness": "offline",
            "deploy_authority": False,
        }
    )
    assert "Market: Fresh" in strip
    assert "Board: Stale" in strip
    assert "Expired 21d" in strip
    assert "Broker: Offline" in strip
    assert "Authority: Blocked" in strip
    assert "DATA FRESH" not in strip
    assert "DATA STALE" not in strip
    assert "Runtime:" in strip


def test_format_operator_sentence_one_line():
    sentence = format_operator_sentence(
        {
            "regime_state": "WAIT",
            "primary_blocker": "Board WAIT — monitor only",
            "deploy_authority": False,
            "deploy_qualified_count": 0,
        }
    )
    assert sentence.startswith("Today WAIT")
    assert "monitor only" in sentence


def test_resolve_system_truth_full_output_fields():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "trust": {"stale": False, "source": "decision_engine", "freshness": "REAL_TIME"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0},
            "top_5": [{"ticker": "AAPL", "action": "WATCH", "score": 7.0}],
        },
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    for field in (
        "market_data_freshness",
        "ranked_board_freshness",
        "brief_freshness",
        "dossier_freshness",
        "portfolio_freshness",
        "broker_freshness",
        "runtime_state",
        "regime_state",
        "volatility_state",
        "breadth_state",
        "leadership_state",
        "board_gate",
        "execution_gate",
        "deploy_authority",
        "primary_blocker",
        "repair_priority",
        "reason_codes",
        "timestamp",
        "truth_strip",
        "operator_sentence",
    ):
        assert field in truth, f"missing {field}"


def test_format_engine_state_never_undefined():
    assert format_engine_state_display(None) == "Unknown"
    assert format_engine_state_display("undefined") == "Unknown"
    assert format_engine_state_display("on") == "On"
    rendered = format_global_truth_strip(
        {
            "market_data_freshness": "fresh",
            "ranked_board_freshness": "fresh",
            "brief_freshness": "fresh",
            "broker_freshness": "offline",
            "runtime_state": "unknown",
            "engine_state": "unknown",
            "deploy_authority": False,
        }
    )
    assert "undefined" not in rendered.lower()
    assert "Runtime: Unknown" in rendered


def test_global_strip_includes_runtime_and_scoped_labels():
    strip = format_global_truth_strip(
        {
            "market_data_freshness": "stale",
            "ranked_board_freshness": "fallback",
            "brief_freshness": "expired",
            "brief_age_days": 21,
            "broker_freshness": "offline",
            "runtime_state": "engine_off",
            "engine_state": "off",
            "deploy_authority": False,
        }
    )
    assert "Market: Stale" in strip
    assert "Board: Fallback" in strip
    assert "Brief: Expired 21d" in strip
    assert "Broker: Offline" in strip
    assert "Runtime:" in strip
    assert "Authority: Blocked" in strip


def test_deploy_qualified_zero_when_broker_offline():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
                "source": "live",
            },
            "qualification_levels": {"deploy_qualified": 3},
            "execution_ready_count": 2,
            "execution_readiness": {"broker_connected": False},
            "top_5": [{"ticker": "X", "action": "TRADE"}],
        },
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is False
    assert truth["deploy_qualified_count"] == 0


def test_deploy_qualified_zero_when_board_stale():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "scanner_degraded": True,
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
                "source": "live",
            },
            "qualification_levels": {"deploy_qualified": 2},
            "execution_ready_count": 2,
            "execution_readiness": {"trade_handoff_ready": True, "broker_connected": True},
            "top_5": [{"ticker": "X", "action": "TRADE"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_authority"] is False
    assert truth["deploy_qualified_count"] == 0
    assert truth["ranked_board_freshness"] == "stale"


def test_selective_stale_tradeability_authority_line():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {},
            "top_5": [{"ticker": "W", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops={},
    )
    assert "Selective candidate review only" in truth.get("tradeability_authority_line", "")
    assert "Deploy authority: Blocked" in truth.get("tradeability_authority_line", "")

