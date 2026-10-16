"""P0 auth fail-closed and ledger write protection."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.deps import verify_api_key


@pytest.mark.asyncio
async def test_verify_api_key_fails_closed_when_settings_unavailable(monkeypatch):
    def _boom():
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr("src.api.deps._load_settings", _boom)
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(x_api_key="any")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_api_key_requires_secret_or_explicit_dev_bypass(monkeypatch):
    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())
    monkeypatch.delenv("CC_DEV_ALLOW_UNAUTH_API", raising=False)
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_dev_bypass_only_when_explicit(monkeypatch):
    class _Settings:
        api_secret_key = ""
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())
    monkeypatch.setenv("CC_DEV_ALLOW_UNAUTH_API", "1")
    assert await verify_api_key(x_api_key=None) is True


@pytest.mark.asyncio
async def test_verify_api_key_rejects_wrong_key(monkeypatch):
    class _Settings:
        api_secret_key = "secret"
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(x_api_key="wrong")
    assert exc.value.status_code == 401


def test_ledger_close_trade_rejects_unauthenticated(monkeypatch):
    """POST /api/ledger/close-trade must not accept anonymous writes."""
    monkeypatch.delenv("CC_DEV_ALLOW_UNAUTH_API", raising=False)

    class _Settings:
        api_secret_key = "test-secret"
        environment = "development"

    monkeypatch.setattr("src.api.deps._load_settings", lambda: _Settings())

    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    payload = {
        "ticker": "SPY",
        "entry_price": 100.0,
        "exit_price": 101.0,
    }
    resp = client.post("/api/ledger/close-trade", json=payload)
    assert resp.status_code == 401
