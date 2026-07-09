"""Capital allocation governor — cannot override page authority."""

from __future__ import annotations

from src.services.capital_allocation_governor import evaluate_capital_allocation


def test_broker_offline_no_capital_or_paper_only():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": False,
            "execution_readiness": {"broker_connected": False},
        },
    )
    assert out["capital_mode"] in ("no_capital", "paper_only")
    assert out["max_new_risk_pct"] == 0.0 or out["capital_mode"] == "paper_only"


def test_manual_demo_book_no_capital():
    out = evaluate_capital_allocation(
        truth={"deploy_authority": True, "execution_readiness": {"broker_connected": True}},
        portfolio_context={"local_only": True},
    )
    assert out["capital_mode"] == "no_capital"
    assert out["sizing_allowed"] is False


def test_drawdown_breach_de_risk():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": True,
            "deploy_qualified_count": 2,
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
        },
        drawdown_pct=18.0,
        dd_budget_pct=15.0,
    )
    assert out["capital_mode"] == "de_risk"
    assert out["max_new_risk_pct"] <= 0.2


def test_high_correlation_lowers_max_risk():
    base = evaluate_capital_allocation(
        truth={"deploy_authority": True, "deploy_qualified_count": 2},
        correlation_cluster=0.2,
    )
    high = evaluate_capital_allocation(
        truth={"deploy_authority": True, "deploy_qualified_count": 2},
        correlation_cluster=0.7,
    )
    assert high["max_new_risk_pct"] <= base["max_new_risk_pct"]


def test_no_edge_today_preserves_cash():
    out = evaluate_capital_allocation(
        truth={
            "deploy_authority": False,
            "deploy_qualified_count": 0,
            "watch_qualified_count": 2,
            "execution_readiness": {"broker_connected": True},
        },
    )
    assert out["capital_mode"] == "monitor_only"
    assert out["cash_valid"] is True
    assert out["cannot_override_authority"] is True
