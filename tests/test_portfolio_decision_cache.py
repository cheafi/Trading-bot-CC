"""Portfolio decision router — scoped cache and fail-closed regime flags."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.api.routers import portfolio as portfolio_router
from src.api.routers.portfolio_decision import (
    _CACHE_BY_SCOPE,
    _CACHE_TS_BY_SCOPE,
    fail_closed_should_trade,
    portfolio_decision_cache_scope,
)


def _mock_request(*, api_key: str = "", host: str = "127.0.0.1") -> MagicMock:
    req = MagicMock()
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req.headers = headers
    client = MagicMock()
    client.host = host
    req.client = client
    return req


def test_cache_scope_differs_by_api_key() -> None:
    portfolio_router._user_portfolio = {
        "holdings": [{"ticker": "AAPL"}],
        "source": "manual",
        "updated_at": "2026-03-01T00:00:00Z",
    }
    a = portfolio_decision_cache_scope(_mock_request(api_key="key-a"))
    b = portfolio_decision_cache_scope(_mock_request(api_key="key-b"))
    assert a != b


def test_cache_scope_changes_when_portfolio_updates() -> None:
    portfolio_router._user_portfolio = {
        "holdings": [],
        "source": "manual",
        "updated_at": "t1",
    }
    first = portfolio_decision_cache_scope(_mock_request(api_key="same"))
    portfolio_router._user_portfolio["updated_at"] = "t2"
    second = portfolio_decision_cache_scope(_mock_request(api_key="same"))
    assert first != second


def test_fail_closed_should_trade_missing_key() -> None:
    assert fail_closed_should_trade({}) is False
    assert fail_closed_should_trade({"regime": "NEUTRAL"}) is False


def test_fail_closed_should_trade_explicit() -> None:
    assert fail_closed_should_trade({"should_trade": True}) is True
    assert fail_closed_should_trade({"should_trade": False}) is False


def test_scoped_cache_storage_isolated() -> None:
    _CACHE_BY_SCOPE.clear()
    _CACHE_TS_BY_SCOPE.clear()
    _CACHE_BY_SCOPE["scope-a"] = {"marker": "A"}
    _CACHE_TS_BY_SCOPE["scope-a"] = 1.0
    _CACHE_BY_SCOPE["scope-b"] = {"marker": "B"}
    _CACHE_TS_BY_SCOPE["scope-b"] = 1.0
    assert _CACHE_BY_SCOPE["scope-a"]["marker"] == "A"
    assert _CACHE_BY_SCOPE["scope-b"]["marker"] == "B"
