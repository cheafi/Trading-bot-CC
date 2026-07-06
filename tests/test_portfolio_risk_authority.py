"""Portfolio / Risk authority contract tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


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
