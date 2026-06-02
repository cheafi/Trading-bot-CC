"""Tests for platform upgrade modules (decision hierarchy, score families, etc.)."""

from __future__ import annotations

from src.services.anti_overtrading import evaluate_restraint
from src.services.core_satellite import (
    build_core_satellite_summary,
    classify_sleeve_role,
)
from src.services.cost_adjusted_edge import compute_gross_vs_net, compute_net_edge
from src.services.crowding_narrative import attach_crowding_to_row, compute_crowding_score
from src.services.decision_hierarchy import (
    LEVEL_EXECUTION,
    LEVEL_PAGE_GATE,
    can_deploy_at_level,
    evaluate_decision_hierarchy,
    hierarchy_for_dashboard,
)
from src.services.passive_baseline import build_passive_baseline_strip
from src.services.score_families import (
    attach_score_families_to_row,
    complexity_verdict,
    extract_families_from_row,
)
from src.services.surface_authority import AUTHORITY_RESEARCH, resolve_authority


def test_decision_hierarchy_blocks_on_wait():
    result = evaluate_decision_hierarchy(
        should_trade=True,
        tradeability="WAIT",
        execution_ready_count=0,
    )
    assert result["binding_level"] == LEVEL_PAGE_GATE
    assert result["can_full_deploy"] is False


def test_decision_hierarchy_allows_deploy_when_clear():
    result = evaluate_decision_hierarchy(
        should_trade=True,
        tradeability="TRADE",
        execution_ready_count=2,
        ibkr_connected=True,
        bracket_ready=True,
    )
    assert result["can_full_deploy"] is True
    assert result["binding_level"] != LEVEL_PAGE_GATE


def test_hierarchy_for_dashboard_wrapper():
    h = hierarchy_for_dashboard(
        decision_model={"honest_tradeability": "WAIT", "macro_regime": "Neutral"},
        should_trade=True,
        tradeability="WAIT",
    )
    assert "levels" in h
    assert len(h["levels"]) == 5


def test_gross_vs_net_edge():
    edge = compute_gross_vs_net(8.0, turnover_burden=0.3, spread_burden=0.2)
    assert edge["gross_edge_score"] == 8.0
    assert edge["net_edge_score"] < 8.0
    assert edge["gross_vs_net"]["survives_cost"] is True


def test_net_edge_weak_after_cost():
    edge = compute_net_edge(5.5, turnover_burden=0.8, spread_burden=0.7)
    assert edge["weak_edge_after_cost"] is True
    assert "Net" in edge["display"]


def test_score_families_separate_roles():
    row = {
        "score": 7.8,
        "thesis_conf": 0.72,
        "final_conf": 0.61,
        "action": "WATCH",
        "execution_ready": False,
        "net_deploy_score": 6.2,
        "net_edge_display": "Gross 7.8 · Net 6.2 after cost",
    }
    card = attach_score_families_to_row(row)["score_card"]
    assert card["thesis_quality"] == 0.72
    assert card["decision_confidence"] == 0.61
    assert "not ready" in card["deployability_label"]
    families = extract_families_from_row(row)
    assert families["board_investability"]["value"] == 7.8


def test_complexity_verdict_wait_day():
    c = complexity_verdict(deployable_count=0, tradeability="WAIT")
    assert c["verdict"] == "justified"
    assert "patience" in c["detail"].lower() or "cash" in c["detail"].lower()


def test_passive_baseline_strip():
    strip = build_passive_baseline_strip(deployable_count=0)
    assert "SPY" in strip["benchmarks"]
    assert strip["data_source"] == "stub"


def test_restraint_active_on_wait():
    r = evaluate_restraint(tradeability="WAIT", deployable_count=0, board_wait=True)
    assert r["restraint_active"] is True
    assert r["cash_valid"] is True
    assert r["restraint_score"] >= 55
    assert "Restraint is correct" in r["headline"]


def test_passive_baseline_insufficient_local_book():
    strip = build_passive_baseline_strip(deployable_count=1, position_count=1, local_only=True)
    assert strip["insufficient_data"] is True
    assert strip["complexity_justified"] is False
    assert "Insufficient data" in strip["expected_advantage_label"]


def test_core_satellite_classify_passive_ticker():
    assert classify_sleeve_role({"ticker": "SPY"}) == "core_passive"
    assert classify_sleeve_role({"ticker": "AAPL", "sleeve": False}) == "active_stock"


def test_core_satellite_insufficient_one_position():
    summary = build_core_satellite_summary(
        [{"ticker": "AAPL", "market_value": 10000}],
        equity=10000,
        local_only=True,
    )
    assert summary["insufficient_data"] is True
    assert len(summary["role_allocation"]) == 4


def test_can_deploy_at_level_helper():
    h = evaluate_decision_hierarchy(
        should_trade=True,
        tradeability="TRADE",
        execution_ready_count=2,
        ibkr_connected=True,
        bracket_ready=True,
    )
    assert can_deploy_at_level(h, LEVEL_EXECUTION) is True
    blocked = evaluate_decision_hierarchy(should_trade=True, tradeability="WAIT")
    assert can_deploy_at_level(blocked, LEVEL_PAGE_GATE) is False


def test_crowding_high_on_extension_and_overlap():
    c = compute_crowding_score(
        rsi=75,
        extended=True,
        sector_overlap_pct=35,
        narrative_bullet_count=5,
        confluence_score=50,
    )
    assert c["level"] == "high"
    assert "rsi_extended" in c["flags"]


def test_attach_crowding_to_row():
    row = attach_crowding_to_row(
        {
            "structure": {"is_extended": True, "rsi": 74},
            "leader": "LEADER",
            "portfolio_gate": {"sector_overlap_pct": 40},
        }
    )
    assert row["crowding_narrative"]["level"] in ("medium", "high")
    assert row["passive_replacement_risk"] in ("medium", "high")


def test_surface_authority_playbook_fallback():
    auth = resolve_authority(
        "playbook",
        tradeability="TRADE",
        board_mode="compressed",
        deployable_count=2,
    )
    assert auth["authority"] == AUTHORITY_RESEARCH


def test_surface_authority_flow_is_confirmation():
    auth = resolve_authority("flow", tradeability="TRADE")
    assert auth["authority"] == "confirmation_only"


def test_surface_authority_discovery_wait_research_only():
    auth = resolve_authority(
        "discovery",
        tradeability="WAIT",
        deployable_count=0,
    )
    assert auth["authority"] == AUTHORITY_RESEARCH
