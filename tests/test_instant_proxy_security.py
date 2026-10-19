"""Instant server must not elevate anonymous proxy requests with server API keys."""

from __future__ import annotations

import pytest

import _cc_instant as instant


def test_dashboard_api_key_never_injects_server_secret(monkeypatch) -> None:
    monkeypatch.setenv("API_SECRET_KEY", "server-only-secret")
    assert instant._dashboard_api_key(None) is None
    assert instant._dashboard_api_key("") is None
    assert instant._dashboard_api_key("dev-secret-local") == "dev-secret-local"
    assert instant._dashboard_api_key("client-provided-key") == "client-provided-key"


def test_patch_dashboard_html_never_embeds_secret(monkeypatch) -> None:
    monkeypatch.setenv("API_SECRET_KEY", "server-only-secret")
    plain = b'window._apiKey = {{ api_key|tojson|safe }};'
    out = instant._patch_dashboard_api_key(plain)
    assert b"server-only-secret" not in out
    assert b'window._apiKey = "";' in out


def test_validate_instant_security_blocks_weak_production_secret(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_SECRET_KEY", "dev-secret-local")
    with pytest.raises(SystemExit):
        instant._validate_instant_security()


def test_validate_instant_security_blocks_short_production_secret(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_SECRET_KEY", "tooshort")
    with pytest.raises(SystemExit):
        instant._validate_instant_security()


def test_validate_instant_security_allows_dev_weak_secret(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("API_SECRET_KEY", "dev-secret-local")
    instant._validate_instant_security()
