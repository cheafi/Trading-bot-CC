"""Portfolio session scope and privilege separation."""

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


def _login_portfolio_session(client) -> None:
    ok = client.post("/api/operator/session", json={"api_key": SECRET})
    assert ok.status_code == 200


def test_portfolio_monitor_denied_without_header_or_cookie(auth_client) -> None:
    assert auth_client.get("/api/portfolio/monitor").status_code == 401


def test_session_establish_then_monitor_without_header(auth_client) -> None:
    assert auth_client.post("/api/operator/session", json={"api_key": "wrong"}).status_code == 401
    _login_portfolio_session(auth_client)
    resp = auth_client.get("/api/portfolio/monitor")
    assert resp.status_code == 200
    assert "positions" in resp.json()


def test_portfolio_cookie_cannot_place_ibkr_order(auth_client, monkeypatch) -> None:
    _login_portfolio_session(auth_client)

    async def _never_called(*_a, **_k):
        raise AssertionError("broker adapter must not be invoked")

    monkeypatch.setattr(
        "src.api.routers.ibkr.get_ibkr_service",
        lambda: (_ for _ in ()).throw(AssertionError("no service")),
    )
    resp = auth_client.post(
        "/api/ibkr/order",
        json={
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 1,
            "order_type": "MKT",
        },
    )
    assert resp.status_code == 401


def test_portfolio_cookie_cannot_release_kill_switch(auth_client) -> None:
    _login_portfolio_session(auth_client)
    resp = auth_client.post(
        "/api/operator/kill-switch",
        params={"enabled": False, "reason": "cookie-attempt"},
    )
    assert resp.status_code == 401


def test_portfolio_cookie_can_read_ibkr_positions_when_authorized(auth_client) -> None:
    _login_portfolio_session(auth_client)
    resp = auth_client.get("/api/ibkr/positions")
    assert resp.status_code in (200, 503)


def test_ibkr_positions_rejects_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")

    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    assert client.get("/api/ibkr/positions").status_code in (401, 503)
    assert client.get("/api/ibkr/account").status_code in (401, 503)


def test_logout_revokes_portfolio_session(auth_client) -> None:
    _login_portfolio_session(auth_client)
    assert auth_client.get("/api/portfolio/monitor").status_code == 200
    assert auth_client.delete("/api/operator/session").status_code == 200
    assert auth_client.get("/api/portfolio/monitor").status_code == 401


def test_expired_portfolio_session_rejected(auth_client) -> None:
    import hashlib
    import hmac
    import time

    from src.api import deps

    exp = int(time.time()) - 60
    session_id = "expired-test-session"
    body = f"v1.portfolio.{exp}.{session_id}"
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    auth_client.cookies.set(deps.OPERATOR_SESSION_COOKIE, f"{body}.{sig}")
    assert auth_client.get("/api/portfolio/monitor").status_code == 401
