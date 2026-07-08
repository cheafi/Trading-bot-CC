"""Portfolio / Risk authority contract tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_resolve_portfolio_mode_manual_book_broker_offline():
    from src.services.portfolio_risk_mode import resolve_portfolio_risk_mode

    mode = resolve_portfolio_risk_mode(
        positions=[{"ticker": "AAPL", "market_value": 10000}],
        source="manual",
        execution_readiness={"broker_connected": False, "portfolio_synced": False},
        ibkr_linkage={"broker_truth": False, "broker_connected": False},
        system_truth={"deploy_authority": False, "deploy_authority_tier": "blocked"},
    )
    assert mode["mode"] == "manual_book"
    assert mode["risk_review_only"] is True
    assert mode["may_authorize_deploy"] is False
    assert mode["risk_capacity_authority"] == "none"
    assert mode["capital_action_queue_enabled"] is False
    assert "broker offline" in mode["blockers"]


def test_resolve_portfolio_mode_demo_sample_watermark():
    from src.services.portfolio_risk_mode import resolve_portfolio_risk_mode

    mode = resolve_portfolio_risk_mode(
        positions=[{"ticker": "SPY", "market_value": 5000, "source": "demo-seed"}],
        source="demo-seed",
        execution_readiness={"broker_connected": True, "portfolio_synced": True},
        ibkr_linkage={"broker_truth": True, "broker_connected": True},
        system_truth={"deploy_authority": True, "deploy_authority_tier": "allowed"},
    )
    assert mode["mode"] == "demo_sample"
    assert mode["demo_watermark"] is True
    assert mode["capital_action_queue_enabled"] is False
    assert mode["may_authorize_deploy"] is False


def test_resolve_portfolio_mode_broker_synced_requires_deploy_auth():
    from src.services.portfolio_risk_mode import resolve_portfolio_risk_mode

    mode = resolve_portfolio_risk_mode(
        positions=[{"ticker": "MSFT", "market_value": 8000, "source": "broker"}],
        source="ibkr",
        execution_readiness={"broker_connected": True, "portfolio_synced": True},
        ibkr_linkage={"broker_truth": True, "broker_connected": True},
        system_truth={
            "deploy_authority": True,
            "deploy_authority_tier": "allowed",
            "brief_freshness": "fresh",
            "ranked_board_freshness": "fresh",
            "market_data_freshness": "fresh",
        },
    )
    assert mode["mode"] == "broker_synced_live"
    assert mode["capital_action_queue_enabled"] is True
    assert mode["may_authorize_deploy"] is True


def test_operator_block_risk_review_only_when_blocked():
    from src.services.portfolio_risk_mode import (
        RISK_REVIEW_ONLY,
        build_portfolio_operator_block,
        resolve_portfolio_risk_mode,
    )

    pm = resolve_portfolio_risk_mode(
        positions=[{"ticker": "NVDA", "market_value": 10000}],
        source="manual",
        execution_readiness={"broker_connected": False},
        ibkr_linkage={"broker_truth": False},
        system_truth={"deploy_authority": False, "deploy_authority_tier": "blocked"},
    )
    block = build_portfolio_operator_block(
        {"deploy_authority": False, "deploy_authority_tier": "blocked", "regime_state": "WAIT"},
        portfolio_mode=pm,
    )
    assert block["now"] == RISK_REVIEW_ONLY
    assert block["capital_action_queue_enabled"] is False
    assert "no sizing" in block["blocked"].lower() or "handoff" in block["blocked"].lower()


def test_sanitize_portfolio_action_strips_deploy_when_blocked():
    from src.services.portfolio_risk_mode import sanitize_portfolio_action_copy

    out = sanitize_portfolio_action_copy(
        "Deploy capital on AAPL — half size trim",
        portfolio_mode={"capital_action_queue_enabled": False},
    )
    assert "Deploy" not in out
    assert "half size" not in out


def test_portfolio_template_has_operator_block_and_capital_gate():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "portfolio_operator_block" in text
    assert "pfCapitalActionsEnabled" in text
    assert "portfolio_mode.demo_watermark" in text or "demo_watermark" in text


def test_build_portfolio_decision_includes_portfolio_mode(monkeypatch=None):
    from src.services.portfolio_decision_console import build_ibkr_linkage
    from src.services.portfolio_risk_mode import resolve_portfolio_risk_mode

    linkage = build_ibkr_linkage(
        source="manual",
        execution={"broker_connected": False, "mode": "manual"},
        positions=[{"ticker": "AAPL", "market_value": 10000}],
    )
    mode = resolve_portfolio_risk_mode(
        positions=[{"ticker": "AAPL", "market_value": 10000}],
        source="manual",
        execution_readiness={"broker_connected": False},
        ibkr_linkage=linkage,
        system_truth={"deploy_authority": False},
    )
    assert mode["risk_review_only"] is True
    blob = json.dumps({"portfolio_mode": mode})
    assert "capital_action_queue_enabled" in blob
    assert "false" in blob.lower()


def test_portfolio_risk_view_model_broker_offline_defaults():
    from src.services.portfolio_risk_mode import (
        build_portfolio_risk_view_model,
        resolve_portfolio_risk_mode,
    )

    pm = resolve_portfolio_risk_mode(
        positions=[],
        source="manual",
        execution_readiness={"broker_connected": False, "portfolio_synced": False},
        ibkr_linkage={"broker_truth": False, "broker_connected": False},
        system_truth={"deploy_authority": False},
    )
    vm = build_portfolio_risk_view_model(
        pm,
        positions=[],
        ibkr_linkage={"broker_truth": False, "broker_connected": False},
        critical_risk_event={"active": False},
    )
    assert vm["risk_capacity_authority"] == "none"
    assert vm["capital_action_enabled"] is False
    assert vm["sleeve_authority"] == "research_only"
    assert vm["live_allocation_eligibility_pct"] == 0
    assert vm["show_sleeve_research_default"] is False
    assert vm["show_demo_tools_default"] is False
    assert vm["show_historical_journal_default"] is False
    assert vm["default_details_collapsed"] is True
    assert vm["broker_truth_banner_active"] is True
    assert "Risk review only until sync" in (vm["broker_truth_banner"] or "")


def test_critical_risk_event_not_active_broker_offline_only():
    from src.services.portfolio_decision_console import (
        build_critical_risk_event,
        build_ibkr_linkage,
    )

    linkage = build_ibkr_linkage(
        source="manual",
        execution={"broker_connected": False, "mode": "manual"},
        positions=[],
    )
    event = build_critical_risk_event(
        positions=[],
        heat={"stop_breached_tickers": []},
        ibkr_linkage=linkage,
        allocation_rows=[],
        top_concentration_pct=0.0,
    )
    assert event["active"] is False


def test_portfolio_template_risk_review_contract():
    text = INDEX_HTML.read_text(encoding="utf-8")
    portfolio = text.split("tab==='portfolio'", 1)[1].split("<!-- SURFACE 4:", 1)[0]
    assert "pfRiskVM()" in portfolio
    assert "portfolioRiskViewModel" in HELPERS.read_text(encoding="utf-8")
    assert "Historical Journal" in portfolio
    assert "Sleeve Research" in portfolio
    assert "Broker truth unavailable" in portfolio
    # Default collapsed posture — banned in default-visible bindings
    assert 'x-text="pfRiskVM().manualAddLabel"' in portfolio
    banned_default = [
        "Active sleeves",
        "Seed Demo Book",
        "Closed-Trade Ledger",
    ]
    for phrase in banned_default:
        assert phrase not in portfolio, f"banned default copy: {phrase}"
