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


def test_monitor_denied_without_key(auth_client) -> None:
    assert auth_client.get("/api/portfolio/monitor").status_code == 401


def test_var_historical_denied_without_key(auth_client) -> None:
    resp = auth_client.post(
        "/api/portfolio/var-historical",
        json={"positions": [{"ticker": "SPY"}], "equity": 100000},
    )
    assert resp.status_code == 401


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


def test_alerts_history_denied_without_key(auth_client) -> None:
    assert auth_client.get("/api/portfolio/alerts-history").status_code == 401


def test_alerts_history_allowed_with_valid_key(auth_client) -> None:
    resp = auth_client.get(
        "/api/portfolio/alerts-history",
        headers={"X-API-Key": SECRET},
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_alerts_clear_dedupe_denied_without_key(auth_client) -> None:
    assert auth_client.post("/api/portfolio/alerts-clear-dedupe").status_code == 401


def test_alerts_rotate_denied_without_key(auth_client) -> None:
    assert auth_client.post("/api/portfolio/alerts-rotate").status_code == 401


def test_alerts_history_rejects_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert client.get("/api/portfolio/alerts-history").status_code == 401
    assert client.post("/api/portfolio/alerts-clear-dedupe").status_code == 401


def test_operator_status_reports_halt_not_enforced(auth_client) -> None:
    resp = auth_client.get("/api/operator/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("execution_halt_enforced") is False
    assert "enforcement not verified" in (body.get("halt_enforcement_note") or "").lower()


def test_operator_throttle_denied_without_key(auth_client) -> None:
    resp = auth_client.post(
        "/api/operator/throttle",
        params={"throttle": "NO_TRADE", "reason": "test"},
    )
    assert resp.status_code == 401


def test_operator_kill_switch_release_denied_without_key(auth_client) -> None:
    resp = auth_client.post(
        "/api/operator/kill-switch",
        params={"enabled": False, "reason": "test-release"},
    )
    assert resp.status_code == 401


def test_operator_kill_switch_allowed_with_valid_key(auth_client) -> None:
    resp = auth_client.post(
        "/api/operator/kill-switch",
        params={"enabled": True, "reason": "test-engage"},
        headers={"X-API-Key": SECRET},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("kill_switch") is True


def test_operator_mutations_reject_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert (
        client.post(
            "/api/operator/kill-switch",
            params={"enabled": False, "reason": "bypass"},
        ).status_code
        == 401
    )


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
