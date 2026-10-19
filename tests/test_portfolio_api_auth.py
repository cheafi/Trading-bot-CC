"""HTTP auth boundary for shared in-process portfolio book routes."""

from __future__ import annotations

import pytest


SECRET = "portfolio-sensitive-secret"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.delenv("CC_DEV_ALLOW_UNAUTH_API", raising=False)

    class _Settings:
        api_secret_key = SECRET
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)


def test_holdings_denied_without_key(auth_client) -> None:
    resp = auth_client.get("/api/portfolio/holdings")
    assert resp.status_code == 401


def test_holdings_denied_with_wrong_key(auth_client) -> None:
    resp = auth_client.get(
        "/api/portfolio/holdings",
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_holdings_allowed_with_valid_key(auth_client) -> None:
    resp = auth_client.get(
        "/api/portfolio/holdings",
        headers={"X-API-Key": SECRET},
    )
    assert resp.status_code == 200
    assert "holdings" in resp.json()


def test_import_denied_without_key(auth_client) -> None:
    resp = auth_client.post(
        "/api/portfolio/import",
        json={"holdings": [{"ticker": "SPY", "shares": 1, "avg_cost": 400}]},
    )
    assert resp.status_code == 401


def test_seed_demo_denied_without_key(auth_client) -> None:
    resp = auth_client.post("/api/portfolio/seed-demo")
    assert resp.status_code == 401


def test_seed_demo_requires_auth_even_with_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert client.post("/api/portfolio/seed-demo").status_code == 401
    assert client.get("/api/portfolio/holdings").status_code == 401


def test_risk_alerts_denied_without_key(auth_client) -> None:
    resp = auth_client.get("/api/portfolio/risk-alerts")
    assert resp.status_code == 401


def test_portfolio_decision_rejects_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    async def _stub(_request):
        return {"ibkr_linkage": {}, "summary": {}}

    monkeypatch.setattr(
        "src.api.routers.portfolio_decision.build_portfolio_decision",
        _stub,
    )

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert client.get("/api/v7/portfolio-decision").status_code == 401
