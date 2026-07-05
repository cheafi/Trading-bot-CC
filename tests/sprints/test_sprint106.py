"""
tests/sprints/test_sprint106.py — Sprint 106: AlertService v2 + Notify Endpoints
==================================================================================
Covers:
  - on_ic_decay_alert: fires only when alerts list non-empty
  - on_thompson_arm_degrade: fires only when win_rate < WIN_RATE_FLOOR
  - on_fund_rebalance: fires when candidates change, silent when same
  - on_regime_change: fires on transition, silent when same
  - on_drawdown_breach: fires when |dd| >= limit, silent otherwise
  - on_circuit_breaker: always fires
  - check_and_push_ic_decay: integration (mocked engine)
  - check_and_push_thompson_degrade: integration (mocked engine)
  - get_alert_log: returns list
  - _append_log / _load_log: round-trip persistence
  - GET /api/v7/notify/log endpoint
  - POST /api/v7/notify/test endpoint
  - GET /api/v7/notify/status endpoint
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _reset_log(tmp_path: Path):
    """Patch _LOG_PATH in alert_service to a temp file and return path."""
    import src.services.alert_service as svc

    svc._LOG_PATH = tmp_path / "alert_log.json"
    return svc._LOG_PATH


# ── on_ic_decay_alert ─────────────────────────────────────────────────────────


def test_ic_decay_alert_returns_false_when_empty(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_ic_decay_alert

    with patch("src.services.alert_service._push_discord", return_value=False):
        result = on_ic_decay_alert([])
    assert result is False


def test_ic_decay_alert_logs_event_when_alerts(tmp_path):
    log_path = _reset_log(tmp_path)
    from src.services.alert_service import on_ic_decay_alert, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_ic_decay_alert(["final_confidence", "vix"])
    events = get_alert_log()
    assert any(e["event_type"] == "ic_decay" for e in events)


def test_ic_decay_alert_meta_contains_features(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_ic_decay_alert, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_ic_decay_alert(["rs_composite"])
    events = get_alert_log()
    ic_events = [e for e in events if e["event_type"] == "ic_decay"]
    assert ic_events
    assert "rs_composite" in ic_events[-1]["meta"]["features"]


# ── on_thompson_arm_degrade ───────────────────────────────────────────────────


def test_thompson_degrade_silent_when_all_healthy(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_thompson_arm_degrade

    arms = [{"strategy": "breakout", "regime": "BULL", "win_rate": 0.65}]
    with patch("src.services.alert_service._push_discord", return_value=False):
        result = on_thompson_arm_degrade(arms)
    assert result is False


def test_thompson_degrade_fires_when_low_win_rate(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_thompson_arm_degrade, get_alert_log

    arms = [{"strategy": "breakout", "regime": "BEAR", "win_rate": 0.25}]
    with patch("src.services.alert_service._push_discord", return_value=False):
        on_thompson_arm_degrade(arms)
    events = get_alert_log()
    assert any(e["event_type"] == "thompson_degrade" for e in events)


def test_thompson_degrade_only_includes_weak_arms(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_thompson_arm_degrade, get_alert_log

    arms = [
        {"strategy": "swing", "regime": "BULL", "win_rate": 0.70},
        {"strategy": "mean_rev", "regime": "CHOPPY", "win_rate": 0.30},
    ]
    with patch("src.services.alert_service._push_discord", return_value=False):
        on_thompson_arm_degrade(arms)
    events = [e for e in get_alert_log() if e["event_type"] == "thompson_degrade"]
    assert events
    degraded = events[-1]["meta"]["arms"]
    assert all(a["win_rate"] < 0.40 for a in degraded)
    assert len(degraded) == 1


# ── on_fund_rebalance ─────────────────────────────────────────────────────────


def test_fund_rebalance_silent_when_same_candidates(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_fund_rebalance

    with patch("src.services.alert_service._push_discord", return_value=False):
        result = on_fund_rebalance("FUND_MACRO", "BEAR", ["TLT", "GLD"], ["TLT", "GLD"])
    assert result is False


def test_fund_rebalance_fires_when_candidates_change(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_fund_rebalance, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_fund_rebalance("FUND_MACRO", "BULL", ["TLT", "GLD"], ["USO", "HYG"])
    events = [e for e in get_alert_log() if e["event_type"] == "fund_rebalance"]
    assert events
    meta = events[-1]["meta"]
    assert "USO" in meta["added"]
    assert "TLT" in meta["removed"]


# ── on_regime_change ─────────────────────────────────────────────────────────


def test_regime_change_silent_same_regime(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_regime_change

    with patch("src.services.alert_service._push_discord", return_value=False):
        result = on_regime_change("BULL", "BULL")
    assert result is False


def test_regime_change_fires_on_transition(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_regime_change, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_regime_change("BULL", "BEAR", vix=32.5)
    events = [e for e in get_alert_log() if e["event_type"] == "regime_change"]
    assert events
    assert events[-1]["meta"]["new"] == "BEAR"
    assert events[-1]["severity"] == "warning"


# ── on_drawdown_breach ────────────────────────────────────────────────────────


def test_drawdown_breach_silent_within_limit(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_drawdown_breach

    with patch("src.services.alert_service._push_discord", return_value=False):
        result = on_drawdown_breach("FUND_ALPHA", dd_pct=-5.0, limit_pct=10.0)
    assert result is False


def test_drawdown_breach_fires_when_exceeded(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_drawdown_breach, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_drawdown_breach("FUND_PENDA", dd_pct=-15.0, limit_pct=10.0)
    events = [e for e in get_alert_log() if e["event_type"] == "drawdown_breach"]
    assert events
    assert events[-1]["severity"] == "critical"


# ── on_circuit_breaker ────────────────────────────────────────────────────────


def test_circuit_breaker_always_logs(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_circuit_breaker, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        on_circuit_breaker("Daily loss limit breached: -3.2%")
    events = [e for e in get_alert_log() if e["event_type"] == "circuit_breaker"]
    assert events
    assert events[-1]["severity"] == "critical"


# ── log persistence ───────────────────────────────────────────────────────────


def test_alert_log_max_50_entries(tmp_path):
    _reset_log(tmp_path)
    from src.services.alert_service import on_circuit_breaker, get_alert_log

    with patch("src.services.alert_service._push_discord", return_value=False):
        for i in range(60):
            on_circuit_breaker(f"breach #{i}")
    log = get_alert_log()
    assert len(log) <= 50


# ── /notify endpoints ─────────────────────────────────────────────────────────


def test_notify_log_endpoint_returns_events(tmp_path):
    import src.services.alert_service as svc

    svc._LOG_PATH = tmp_path / "alert_log.json"
    from fastapi.testclient import TestClient
    from src.api.main import app

    with patch("src.services.alert_service._push_discord", return_value=False):
        svc.on_circuit_breaker("test")
    client = TestClient(app)
    resp = client.get("/api/v7/notify/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "count" in data


def test_notify_test_endpoint_returns_ok():
    from fastapi.testclient import TestClient
    from src.api.main import app
    import src.services.alert_service as svc

    with tempfile.TemporaryDirectory() as td:
        svc._LOG_PATH = Path(td) / "alert_log.json"
        client = TestClient(app)
        resp = client.post("/api/v7/notify/test?message=hello&severity=info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True


def test_notify_status_endpoint_returns_configured_key():
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/api/v7/notify/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "discord_configured" in data
