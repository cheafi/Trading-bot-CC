"""HTTP security for GET /api/v7/portfolio-decision."""

from __future__ import annotations

import pytest


@pytest.fixture
def portfolio_decision_client(monkeypatch):
    monkeypatch.delenv("CC_DEV_ALLOW_UNAUTH_API", raising=False)

    class _Settings:
        api_secret_key = "test-portfolio-secret"
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    async def _stub_build(_request):
        return {
            "summary": {"total_positions": 0},
            "ibkr_linkage": {"broker_connected": False, "broker_truth": False},
        }

    monkeypatch.setattr(
        "src.api.routers.portfolio_decision.build_portfolio_decision",
        _stub_build,
    )

    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)


def test_portfolio_decision_denies_missing_api_key(portfolio_decision_client) -> None:
    resp = portfolio_decision_client.get("/api/v7/portfolio-decision")
    assert resp.status_code == 401
    body = resp.text.lower()
    assert "holdings" not in body or "aapl" not in body


def test_portfolio_decision_denies_invalid_api_key(portfolio_decision_client) -> None:
    resp = portfolio_decision_client.get(
        "/api/v7/portfolio-decision",
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_portfolio_decision_allows_valid_key_and_marks_boundary(
    portfolio_decision_client,
) -> None:
    resp = portfolio_decision_client.get(
        "/api/v7/portfolio-decision",
        headers={"X-API-Key": "test-portfolio-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    boundary = data.get("portfolio_data_boundary") or {}
    assert boundary.get("deployment_model") == "single_operator_global_book"
    assert boundary.get("multi_tenant_data_isolation") is False
    assert boundary.get("broker_verified") is False
