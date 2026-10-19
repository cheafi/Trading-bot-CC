"""Operator session cookie auth for sensitive portfolio routes."""

from __future__ import annotations

import pytest

SECRET = "operator-session-secret"


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


def test_portfolio_monitor_denied_without_header_or_cookie(auth_client) -> None:
    assert auth_client.get("/api/portfolio/monitor").status_code == 401


def test_session_establish_then_monitor_without_header(auth_client) -> None:
    bad = auth_client.post("/api/operator/session", json={"api_key": "wrong"})
    assert bad.status_code == 401

    ok = auth_client.post("/api/operator/session", json={"api_key": SECRET})
    assert ok.status_code == 200
    assert ok.json().get("authenticated") is True

    resp = auth_client.get("/api/portfolio/monitor")
    assert resp.status_code == 200
    assert "positions" in resp.json()


def test_ibkr_positions_rejects_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert client.get("/api/ibkr/positions").status_code == 401
    assert client.get("/api/ibkr/account").status_code == 401
