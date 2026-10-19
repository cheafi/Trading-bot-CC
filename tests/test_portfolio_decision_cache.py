"""Portfolio decision router — cache lifecycle, regime parsing, deployment boundary."""

from __future__ import annotations

import time

from src.api.routers import portfolio as portfolio_router
from src.api.routers.portfolio_decision import (
    _CACHE_BY_SCOPE,
    _CACHE_TS_BY_SCOPE,
    _TTL,
    fail_closed_should_trade,
    portfolio_data_boundary,
    portfolio_decision_cache_scope,
    portfolio_fingerprint,
    verified_principal_hash,
    _cache_get,
    _cache_put,
)


def test_verified_principal_hash_is_not_raw_key() -> None:
    h = verified_principal_hash("super-secret-key")
    assert h != "super-secret-key"
    assert len(h) == 24


def test_cache_scope_uses_book_revision_not_ip() -> None:
    portfolio_router._user_portfolio = {
        "holdings": [{"ticker": "AAPL"}],
        "source": "manual",
        "updated_at": "2026-03-01T00:00:00Z",
    }
    principal = verified_principal_hash("same-key")
    a = portfolio_decision_cache_scope(principal_hash=principal)
    portfolio_router._user_portfolio["updated_at"] = "2026-03-02T00:00:00Z"
    b = portfolio_decision_cache_scope(principal_hash=principal)
    assert a != b


def test_same_principal_same_book_same_scope() -> None:
    portfolio_router._user_portfolio = {
        "holdings": [],
        "source": "manual",
        "updated_at": "fixed",
    }
    p = verified_principal_hash("k")
    assert portfolio_decision_cache_scope(principal_hash=p) == portfolio_decision_cache_scope(
        principal_hash=p
    )


def test_fail_closed_should_trade_missing_and_none() -> None:
    assert fail_closed_should_trade({}) is False
    assert fail_closed_should_trade({"regime": "NEUTRAL"}) is False
    assert fail_closed_should_trade({"should_trade": None}) is False


def test_fail_closed_should_trade_strict_bool_only() -> None:
    assert fail_closed_should_trade({"should_trade": True}) is True
    assert fail_closed_should_trade({"should_trade": False}) is False
    assert fail_closed_should_trade({"should_trade": "true"}) is False
    assert fail_closed_should_trade({"should_trade": "false"}) is False
    assert fail_closed_should_trade({"should_trade": 1}) is False
    assert fail_closed_should_trade({"should_trade": 0}) is False


def test_cache_expired_not_returned() -> None:
    _CACHE_BY_SCOPE.clear()
    _CACHE_TS_BY_SCOPE.clear()
    scope = "test-scope"
    _cache_put(scope, {"ok": True}, time.time() - _TTL - 1)
    hit, payload = _cache_get(scope, time.time())
    assert hit is False
    assert payload is None


def test_cache_fresh_hit() -> None:
    _CACHE_BY_SCOPE.clear()
    _CACHE_TS_BY_SCOPE.clear()
    scope = "fresh"
    _cache_put(scope, {"marker": 1}, time.time())
    hit, payload = _cache_get(scope, time.time())
    assert hit is True
    assert payload == {"marker": 1}


def test_portfolio_data_boundary_manual_not_broker_verified() -> None:
    portfolio_router._user_portfolio = {"source": "manual", "holdings": []}
    boundary = portfolio_data_boundary({"ibkr_linkage": {"broker_connected": False}})
    assert boundary["portfolio_truth_mode"] == "MANUAL"
    assert boundary["broker_verified"] is False
    assert boundary["multi_tenant_data_isolation"] is False
    assert "not submitted to broker" in boundary["protection_note"]


def test_portfolio_data_boundary_flags_alone_not_broker_verified() -> None:
    portfolio_router._user_portfolio = {"source": "manual", "holdings": []}
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "broker_truth": True,
                "sync_quality": "mixed_local_broker",
            }
        }
    )
    assert boundary["broker_verified"] is False
    assert boundary["portfolio_truth_mode"] == "BROKER_UNVERIFIED"


def test_portfolio_data_boundary_broker_truth_without_alignment_unverified() -> None:
    portfolio_router._user_portfolio = {"source": "ibkr", "holdings": [{"ticker": "A"}]}
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "manual",
                "broker_position_count": 5,
                "local_only_count": 0,
            }
        }
    )
    assert boundary["broker_verified"] is False
    assert boundary["portfolio_truth_mode"] == "BROKER_UNVERIFIED"


def test_portfolio_data_boundary_broker_verified_when_aligned() -> None:
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    portfolio_router._user_portfolio = {
        "source": "ibkr",
        "holdings": [{"ticker": "A"}],
        "broker_account_id": "DU123",
    }
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "ibkr",
                "broker_position_count": 1,
                "local_only_count": 0,
                "holdings_snapshot_at": fresh,
                "broker_account_id": "DU123",
            }
        }
    )
    assert boundary["broker_verified"] is True
    assert boundary["position_symbol_qty_reconciled"] is False
    assert boundary["broker_account_identity_verified"] is True
    assert boundary["portfolio_truth_mode"] == "BROKER_VERIFIED"


def test_portfolio_data_boundary_stale_sync_not_broker_verified() -> None:
    portfolio_router._user_portfolio = {"source": "ibkr", "holdings": [{"ticker": "A"}]}
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "ibkr",
                "broker_position_count": 3,
                "local_only_count": 0,
                "holdings_snapshot_at": "2020-01-01T00:00:00Z",
            }
        }
    )
    assert boundary["broker_verified"] is False
    assert boundary["portfolio_truth_mode"] == "BROKER_UNVERIFIED"


def test_portfolio_data_boundary_heartbeat_without_snapshot_not_verified() -> None:
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    portfolio_router._user_portfolio = {
        "source": "ibkr",
        "holdings": [{"ticker": "A"}],
        "broker_account_id": "DU123",
    }
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "ibkr",
                "broker_position_count": 1,
                "local_only_count": 0,
                "broker_heartbeat_at": fresh,
                "broker_account_id": "DU123",
            }
        }
    )
    assert boundary["broker_verified"] is False


def test_portfolio_data_boundary_missing_local_account_not_verified() -> None:
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    portfolio_router._user_portfolio = {"source": "ibkr", "holdings": [{"ticker": "A"}]}
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "ibkr",
                "broker_position_count": 1,
                "local_only_count": 0,
                "holdings_snapshot_at": fresh,
                "broker_account_id": "DU123",
            }
        }
    )
    assert boundary["broker_account_identity_verified"] is False
    assert boundary["broker_verified"] is False


def test_build_ibkr_linkage_includes_broker_account_id() -> None:
    from src.services.portfolio_decision_console import build_ibkr_linkage

    link = build_ibkr_linkage(
        source="ibkr",
        execution={"broker_connected": True, "broker_account_id": "DU999", "mode": "paper"},
        positions=[{"source": "broker", "ticker": "SPY"}],
        updated_at="2026-01-01T00:00:00Z",
    )
    assert link.get("broker_account_id") == "DU999"
    assert link.get("account_id") == "DU999"


def test_portfolio_data_boundary_misaligned_counts_not_verified() -> None:
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    portfolio_router._user_portfolio = {
        "source": "ibkr",
        "holdings": [{"ticker": "A"}, {"ticker": "B"}],
    }
    boundary = portfolio_data_boundary(
        {
            "ibkr_linkage": {
                "broker_connected": True,
                "sync_quality": "broker_truth",
                "portfolio_source": "ibkr",
                "broker_position_count": 1,
                "local_only_count": 0,
                "last_sync": fresh,
                "broker_account_id": "DU123",
            }
        }
    )
    assert boundary["broker_verified"] is False
    assert boundary["position_count_aligned"] is False
    assert boundary["position_symbol_qty_reconciled"] is False


def test_portfolio_fingerprint_reflects_source() -> None:
    portfolio_router._user_portfolio = {
        "holdings": [{"ticker": "X"}],
        "source": "demo-seed",
        "updated_at": "t",
    }
    fp = portfolio_fingerprint()
    assert "demo-seed" in fp
    assert "1:" in fp
