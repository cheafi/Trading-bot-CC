"""Ops regressions: optional snapshots must not crash or invent evidence."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.services.ops_operator_console import build_ops_operator_console


@pytest.fixture(autouse=True)
def isolated_optional_panels(monkeypatch):
    """No heartbeat files, error-log writes, or machine-health side effects."""
    monkeypatch.setattr(
        "src.services.ops_operator_console._read_engine_heartbeat",
        lambda: None,
    )
    monkeypatch.setattr(
        "src.services.platform_error_log.get_error_log",
        lambda **kwargs: {"total_buffered": 0},
    )
    monkeypatch.setattr(
        "src.services.decision_machines.build_machines_health_panel",
        lambda **kwargs: {},
    )


@pytest.mark.parametrize("latest", [None, {}])
def test_missing_latest_brief_timestamp_stays_unavailable(latest):
    out = build_ops_operator_console(
        cc_header={"brief_status": {"latest": latest}}
    )
    assert out["last_events"]["last_brief"] is None
    assert out["runnable"] is False


def test_missing_today_trust_timestamp_stays_unavailable():
    out = build_ops_operator_console(today={"trust": None})
    assert out["last_times"]["last_recommendation_refresh"] is None
    assert out["runnable"] is False


def test_null_freshness_stream_is_not_a_successful_probe():
    out = build_ops_operator_console(
        cc_header={"freshness": {"worst_tier": "UNKNOWN", "streams": [None]}}
    )
    assert not any(
        row["name"] == "market_data" and row["ok"]
        for row in out["component_evidence"]
    )
    assert out["last_events"]["market_data_tier"] == "UNKNOWN"


def test_valid_optional_evidence_is_preserved():
    stamp = datetime.now(timezone.utc).isoformat()
    out = build_ops_operator_console(
        cc_header={
            "brief_status": {"latest": {"as_of": stamp}},
            "freshness": {"streams": [None, {"ok": True}]},
        },
        today={"trust": {"as_of": stamp}},
    )
    assert out["last_events"]["last_brief"] == stamp
    assert out["last_times"]["last_recommendation_refresh"] == stamp
    assert any(
        row["name"] == "market_data" and row["ok"]
        for row in out["component_evidence"]
    )


@pytest.mark.parametrize("broker_snapshot", [None, {}])
def test_handler_null_optional_snapshots(monkeypatch, broker_snapshot):
    """Exercise the registered handler without importing the main app."""
    # Unrelated router import requires the real universe file. Isolate it;
    # this test neither calls the risk cockpit nor mounts host market data.
    risk_cockpit = ModuleType("src.services.portfolio_risk_cockpit")
    risk_cockpit.build_portfolio_risk_cockpit = Mock(
        side_effect=AssertionError("Unrelated risk cockpit must not run")
    )
    monkeypatch.setitem(
        sys.modules, "src.services.portfolio_risk_cockpit", risk_cockpit
    )
    from src.api.routers import platform_extras
    from src.core.telemetry import telemetry

    engine = SimpleNamespace(
        _running=False, dry_run=True, _cycle_count=0,
        _signals_today=[], _trades_today=[], _cached_recommendations=[],
        circuit_breaker=None, last_cycle_time=None,
    )
    get_engine = Mock(return_value=engine)
    monkeypatch.setattr("src.api.app_state.get_engine", get_engine)
    service = Mock()
    service.status.return_value = broker_snapshot
    monkeypatch.setattr(
        "src.services.ibkr_service.get_ibkr_service", lambda: service
    )
    readiness = Mock(return_value={})
    monkeypatch.setattr(
        "src.services.execution_readiness.build_execution_readiness", readiness
    )
    header = {
        "brief_status": {"latest": None},
        "freshness": None,
        "ibkr": None,
        "components": None,
    }
    monkeypatch.setattr(
        platform_extras, "_cc_header_for_ops", AsyncMock(return_value=header)
    )
    monkeypatch.setattr(telemetry, "get_jobs_status", lambda: None)
    monkeypatch.setattr(telemetry, "get_signals_status", lambda: None)
    log_stopped = Mock()
    monkeypatch.setattr(
        "src.services.platform_error_log.log_engine_stopped", log_stopped
    )
    app = FastAPI()
    app.state.today_v7_cache = {"trust": None, "no_setup_diagnosis": None}
    app.include_router(platform_extras.router)

    async def fetch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://isolated"
        ) as client:
            response = await client.get("/api/v7/ops-console")
            assert response.status_code == 200
            return response.json()

    out = asyncio.run(fetch())
    assert out["last_events"]["last_brief"] is None
    assert out["last_times"]["last_recommendation_refresh"] is None
    assert out["scheduler"]["alive"] == "unknown"
    assert out["runnable"] is False
    assert out["paper_ready"] is False
    assert out["engine"]["running"] is False
    assert out["ibkr"]["available"] is False
    assert out["ibkr"]["connected"] is None
    assert out["ibkr"]["gateway_reachable"] is None
    assert out["ibkr"]["mode"] is None
    assert "unavailable" in out["ibkr"]["health_label"].lower()
    assert "unavailable" in out["providers_honest"]["broker"]["probe"].lower()
    readiness.assert_not_called()
    get_engine.assert_called_once_with(app)
    service.status.assert_called_once_with()
    assert service.method_calls == [("status", (), {})]


def test_unavailable_broker_does_not_reuse_stale_connected_header():
    stamp = datetime.now(timezone.utc).isoformat()
    out = build_ops_operator_console(
        ops_status={"engine": {
            "running": True, "dry_run": False, "cycle_count": 1,
            "cached_recommendations": 1, "last_cycle": stamp,
        }},
        cc_header={
            "ibkr": {
                "connected": True, "gateway_reachable": True,
                "last_order_ok": stamp,
            },
            "components": {"broker": True},
        },
        execution_readiness={
            "available": False, "health_label": "Broker snapshot unavailable"
        },
    )
    assert out["runnable"] is False
    assert out["ibkr"]["connected"] is None
    assert out["last_times"]["last_paper_order_test"] is None
    assert out["execution_boundary"]["broker_path"] == "unavailable"
    broker = next(
        row for row in out["component_evidence"] if row["name"] == "broker"
    )
    assert broker["ok"] is None
    assert broker["tier"] == "unavailable"
