"""Playbook authority semantics — blocked deploy, single buckets, monitor logic."""

from __future__ import annotations

from src.services.authority_engine import primary_operator_state
from src.services.playbook_truth import (
    build_playbook_operator_view,
    bucket_rows,
    enforce_single_primary_bucket,
    format_playbook_qualification_line,
    no_valid_monitors,
)
from src.services.system_truth import _brief_freshness, resolve_system_truth


def test_deploy_gate_open_null_when_blocked():
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
            "top_5": [{"ticker": "AAA", "action": "TRADE"}],
        },
        cc_header={},
        ops_console={"engine_running": True},
    )
    qual = truth["qualification_line"]
    assert "Deploy gate open" not in qual
    assert "gates open" not in qual
    assert "0 deploy-qualified" in qual


def test_trade_not_in_posture_when_blocked():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {"broker_connected": False},
        },
        cc_header={},
        ops_console={},
    )
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["primary"] != "TRADE"
    pov = build_playbook_operator_view(truth, [])
    assert pov["authority"] == "BLOCKED"
    assert pov["qualification"]["deploy"] == 0


def test_deploy_qualified_zero_when_broker_offline():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "qualification_levels": {
                "setup_qualified": 2,
                "trade_qualified": 2,
                "execution_qualified": 2,
                "deploy_qualified": 2,
            },
            "execution_ready_count": 2,
            "execution_readiness": {"broker_connected": False},
            "top_5": [{"ticker": "AAA", "action": "TRADE", "execution_ready": True}],
        },
        cc_header={},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_qualified_count"] == 0
    assert truth["execution_qualified_count"] == 0
    pov = build_playbook_operator_view(
        truth,
        [{"ticker": "AAA", "action": "TRADE", "execution_ready": True}],
    )
    assert pov["qualification"]["deploy"] == 0
    assert pov["qualification"]["execution"] == 0


def test_deploy_qualified_zero_when_board_wait():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "qualification_levels": {"deploy_qualified": 2, "execution_qualified": 1},
            "execution_ready_count": 1,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
            "top_5": [{"ticker": "AAA", "action": "WATCH"}],
        },
        cc_header={},
        ops_console={"engine_running": True},
    )
    assert truth["deploy_qualified_count"] == 0
    pov = build_playbook_operator_view(truth, [{"ticker": "AAA", "action": "WATCH"}])
    assert pov["qualification"]["deploy"] == 0


def test_unique_primary_buckets():
    rows = [
        {"ticker": "AAA", "action": "TRADE", "execution_ready": True},
        {"ticker": "AAA", "action": "WATCH", "fastest_improving": True},
        {"ticker": "BBB", "action": "PILOT"},
    ]
    buckets = bucket_rows(rows, deploy_authority=True)
    seen: set[str] = set()
    for items in buckets.values():
        for row in items:
            ticker = str(row["ticker"]).upper()
            assert ticker not in seen
            seen.add(ticker)
    assert seen == {"AAA", "BBB"}
    assert buckets["Deploy"][0]["ticker"] == "AAA"
    assert "fastest_improving" in (buckets["Deploy"][0].get("playbook_tags") or [])


def test_enforce_single_primary_bucket_dedupes():
    raw = {
        "Deploy": [{"ticker": "SPY", "primary_bucket": "Deploy"}],
        "Watch": [{"ticker": "SPY", "primary_bucket": "Watch"}],
        "Pilot": [],
        "Near-miss": [],
        "Rejected": [],
    }
    out = enforce_single_primary_bucket(raw)
    assert len(out["Deploy"]) == 1
    assert len(out["Watch"]) == 0


def test_paper_queue_hidden_when_blocked():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {"broker_connected": False},
        },
        cc_header={},
        ops_console={},
    )
    pov = build_playbook_operator_view(truth, [])
    assert pov["simulation_drafts_collapsed"] is True
    assert pov["authority"] == "BLOCKED"


def test_no_valid_monitors_logic():
    assert no_valid_monitors({"Watch": 0, "Near-miss": 0})
    assert not no_valid_monitors({"Watch": 1, "Near-miss": 0})
    assert not no_valid_monitors({"Watch": 0, "Near-miss": 1})
    truth = resolve_system_truth(
        {"market_regime": {"tradeability": "WAIT"}, "top_5": []},
        cc_header={},
        ops_console={},
    )
    pov = build_playbook_operator_view(truth, [{"ticker": "X", "action": "AVOID"}])
    assert pov["no_valid_monitors"] is True


def test_brief_expired_not_fallback():
    today = {
        "brief_status": {"age_days": 26, "tier": "STALE"},
        "trust": {"source": "brief-fallback"},
        "used_brief_fallback": True,
        "top_5": [{"ticker": "AAA"}],
    }
    assert _brief_freshness(today, brief_age_days=26) == "expired"
    truth = resolve_system_truth(today, cc_header={}, ops_console={}, brief_age_days=26)
    assert truth["brief_freshness"] == "expired"
    assert truth["brief_freshness"] != "fallback"
    pov = build_playbook_operator_view(truth, [])
    assert "Expired" in pov["truth_strip"] or "expired" in pov["truth_strip"].lower()


def test_format_qualification_never_gate_open():
    line = format_playbook_qualification_line(
        setup_qualified=2,
        deploy_qualified=0,
        deploy_authority=False,
        regime_state="WAIT",
        board_gate="wait",
    )
    assert "gate open" not in line.lower()


def test_blocked_fixture_deploy_qualified_zero_in_viewmodel():
    """Raw payload may carry deploy_qualified=2 — rendered view must show 0."""
    from src.services.playbook_truth import build_playbook_operator_view

    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "qualification_levels": {
                "setup_qualified": 3,
                "trade_qualified": 2,
                "execution_qualified": 2,
                "deploy_qualified": 2,
            },
            "execution_ready_count": 2,
            "execution_readiness": {"broker_connected": False},
            "top_5": [
                {"ticker": "AAA", "action": "TRADE", "execution_ready": True},
                {"ticker": "BBB", "action": "WATCH", "score": 7.0},
            ],
        },
        cc_header={},
        ops_console={"engine_running": False},
    )
    # resolve_system_truth zeroes deploy counts when blocked — raw payload not echoed
    assert truth.get("qualification_levels") is None
    assert truth["deploy_qualified_count"] == 0
    pov = build_playbook_operator_view(
        truth,
        [{"ticker": "AAA", "action": "TRADE", "execution_ready": True}],
        near_miss_rows=[{"ticker": "BBB", "action": "WATCH", "score": 7.0}],
    )
    assert pov["authority"] == "BLOCKED"
    assert pov["qualification"]["deploy"] == 0
    assert "2 deploy-qualified" not in pov["qualification_line"]
    assert "0 deploy-qualified" in pov["qualification_line"]
    assert pov["no_valid_monitors"] is False
    assert len(pov["buckets"]["watch"]) + len(pov["buckets"]["near_miss"]) >= 1


def test_no_valid_monitors_only_when_both_empty():
    pov = build_playbook_operator_view(
        resolve_system_truth(
            {"market_regime": {"tradeability": "WAIT"}, "top_5": []},
            cc_header={},
            ops_console={},
        ),
        [{"ticker": "X", "action": "WATCH", "score": 6.5}],
    )
    assert pov["no_valid_monitors"] is False


def test_index_playbook_no_brief_fallback_when_expired():
    """Template + JS must not surface 'brief fallback' on Playbook when brief expired."""
    from pathlib import Path

    blob = Path(__file__).resolve().parents[1].joinpath(
        "src/api/templates/index.html"
    ).read_text(encoding="utf-8", errors="replace")
    start = blob.index('data-cc="playbook-surface"')
    end = blob.index('x-show="tab===\'dossier\'"', start)
    playbook = blob[start:end]
    assert "playbookBriefExpired" in blob
    assert "Brief fallback" not in playbook
    assert "brief fallback" not in playbook.lower()
