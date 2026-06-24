"""Tests for unified SystemState / PageCapability contract."""

from __future__ import annotations

from src.services.operator_state_contract import (
    build_page_capability,
    build_playbook_rank_buckets,
    build_system_state,
    classify_rank_bucket,
    format_operator_sentence,
    pick_dashboard_monitors,
    structural_valid_for_monitor,
)


def test_format_operator_sentence_joins_parts():
    s = format_operator_sentence(
        now="WAIT · monitor",
        blocker="data stale",
        next_action="refresh",
        scope="global",
    )
    assert s["now"] == "WAIT · monitor"
    assert "阻擋 · BLOCKER: data stale" in s["line"]
    assert s["scope"] == "global"


def test_build_system_state_wait_monitor_only():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    assert ss["tradeability"] == "WAIT"
    assert ss["authority"] == "monitor_only"
    assert ss["deploy_open"] is False
    assert ss["global_strip_active"] is True
    assert "部署" in ss["blocker_compact"] or "WAIT" in ss["blocker_compact"]


def test_global_strip_inactive_when_deploy_open_and_fresh():
    ss = build_system_state(
        tradeability="TRADE",
        should_trade=True,
        cc_state={
            "board_decision_state": {"state": "DEPLOY"},
            "freshness_state": {"worst_tier": "FRESH", "board_source": "live"},
            "execution_state": {"engine_running": True, "state": "CONNECTED"},
        },
        decision_authority={"gates_active": False, "degraded": False},
    )
    assert ss["deploy_open"] is True
    assert ss["global_strip_active"] is False


def test_classify_rank_bucket_pilot_and_near_miss():
    assert classify_rank_bucket({"action": "PILOT", "ladder_bucket": "pilot_ready"}) == "pilotQualified"
    row = {
        "action": "WATCH",
        "thesis_conf": 0.6,
        "timing_conf": 0.55,
        "score": 6,
        "leader": "LEADER",
    }
    assert classify_rank_bucket(row) in ("nearMiss", "watchQualified")


def test_build_system_state_deploy_open_requires_gates():
    ss = build_system_state(
        tradeability="TRADE",
        should_trade=True,
        cc_state={
            "board_decision_state": {"state": "DEPLOY"},
            "freshness_state": {"worst_tier": "FRESH", "board_source": "live"},
            "execution_state": {"engine_running": True, "state": "CONNECTED"},
        },
        decision_authority={"gates_active": False, "degraded": False},
    )
    assert ss["deploy_open"] is True
    assert ss["authority"] == "deploy"


def test_rank_buckets_exclude_avoid_from_monitor():
    rows = [
        {"ticker": "AAA", "action": "WATCH", "ladder_bucket": "watch_upgrade", "score": 7},
        {"ticker": "BBB", "action": "AVOID", "ladder_bucket": "hard_reject", "score": 2},
        {"ticker": "CCC", "action": "WATCH", "thesis_conf": 0.6, "timing_conf": 0.55, "score": 6},
    ]
    buckets = build_playbook_rank_buckets(rows)
    monitor_tickers = [r["ticker"] for r in buckets["monitor_rows"]]
    assert "BBB" not in monitor_tickers
    assert buckets["buckets"]["rejectedAvoid"]
    assert buckets["has_valid_monitors"] is True


def test_pick_dashboard_monitors_skips_avoid():
    watch = [{"ticker": "AAA", "action": "WATCH"}]
    near = [{"ticker": "BBB", "action": "AVOID"}]
    top = [{"ticker": "CCC", "action": "WATCH"}]
    out = pick_dashboard_monitors(watch_qualified=watch, near_miss=near, top_ranked=top, limit=3)
    assert out == ["AAA", "CCC"]


def test_structural_valid_for_monitor_rejects_hard_reject():
    assert structural_valid_for_monitor({"action": "WATCH"}) is True
    assert structural_valid_for_monitor({"action": "AVOID"}) is False
    assert structural_valid_for_monitor({"action": "WATCH", "hard_reject": True}) is False


def test_dossier_page_capability_confirm_only():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    cap = build_page_capability("dossier", system_state=ss)
    assert cap["can_confirm_structure"] is True
    assert cap["can_size"] is False
    assert cap["can_handoff"] is False
    assert cap["operator_sentence"]["scope"] == "dossier"


def test_flow_mock_page_uses_ignore_guidance():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    cap = build_page_capability("flow", system_state=ss, mock_only=True)
    assert "ignore" in cap["operator_sentence"]["next_action"].lower()
    assert cap["can_deploy"] is False


def test_funds_fetch_failed_capability():
    ss = build_system_state(tradeability="WAIT", should_trade=False, trust={"stale": True})
    cap = build_page_capability("funds", system_state=ss, fetch_state="failed_fetch")
    assert cap["can_deploy"] is False
    na = cap["operator_sentence"]["next_action"].lower()
    assert "sleeve" in na or "allocation" in na or "repair" in na


def test_agent_page_research_monitoring_only():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    cap = build_page_capability("agent", system_state=ss)
    assert cap["surface_type"] == "research_monitoring"
    assert cap["can_deploy"] is False
    assert cap["can_size"] is False
    assert cap["can_handoff"] is False
    assert cap["can_research"] is True
    assert "playbook" in cap["operator_sentence"]["next_action"].lower()


def test_ops_ibkr_portfolio_page_capability_scopes():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    assert build_page_capability("ops", system_state=ss)["operator_sentence"]["scope"] == "ops"
    assert build_page_capability("ibkr", system_state=ss)["operator_sentence"]["scope"] == "ibkr"
    assert build_page_capability("portfolio", system_state=ss)["operator_sentence"]["scope"] == "portfolio"


def test_strategy_lab_shadow_reports_research_only():
    ss = build_system_state(tradeability="WAIT", should_trade=False)
    for tab in ("strategy-lab", "shadow", "reports"):
        cap = build_page_capability(tab, system_state=ss)
        assert cap["can_deploy"] is False
        assert cap["can_handoff"] is False
        assert cap["surface_type"] == "research_monitoring"
