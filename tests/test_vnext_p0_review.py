"""P0 items from 2026-10-15 institutional code review."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.core.market_sessions import active_markets_at, us_session_utc_windows
from src.engines.auto_trading_engine import RiskCircuitBreaker
from src.engines.broker_reconciliation import (
    BrokerReconciliationEngine,
    ReconciliationStatus,
)

def test_us_regular_utc_shifts_between_est_and_edt() -> None:
    winter = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)
    w = us_session_utc_windows(winter)["us_regular"]
    s = us_session_utc_windows(summer)["us_regular"]
    assert w != s
    assert w == (14 * 60 + 30, 21 * 60)
    assert s == (13 * 60 + 30, 20 * 60)


def test_active_us_market_midday_et() -> None:
    et = ZoneInfo("America/New_York")
    noon = datetime(2026, 3, 10, 12, 0, tzinfo=et).astimezone(timezone.utc)
    assert "us" in active_markets_at(noon)


def test_broker_reconciliation_fail_closed(tmp_path) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "rec.json")
    assert eng.can_trade() is False
    assert eng.reconcile(broker_positions=None) == ReconciliationStatus.PENDING
    assert eng.can_trade() is False
    assert eng.reconcile(broker_positions={}) == ReconciliationStatus.OK
    assert eng.can_trade() is True
    eng.record_order("o1", "AAPL", "BUY", 10)
    assert eng.can_trade() is False


def test_cold_start_never_trusts_missing_snapshot(tmp_path) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "missing.json")
    assert eng.recovery_gate()["requires_broker_reconcile"] is True
    assert eng.can_trade() is False


def test_cold_start_never_trusts_persisted_ok(tmp_path) -> None:
    snap = tmp_path / "order_reconciliation.json"
    snap.write_text(
        '{"reconciliation_status":"ok","orders":[],"last_reconciliation":"2020-01-01"}',
        encoding="utf-8",
    )
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    assert eng._reconciliation_status == ReconciliationStatus.PENDING
    assert eng.can_trade() is False


def test_reconcile_none_never_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "r.json")
    eng.mark_simulation_ready()
    assert eng.reconcile(broker_positions=None) == ReconciliationStatus.SIMULATION_READY
    eng2 = BrokerReconciliationEngine(snapshot_path=tmp_path / "r2.json")
    assert eng2.reconcile(broker_positions=None) == ReconciliationStatus.PENDING
    assert eng2._reconciliation_status != ReconciliationStatus.OK


def test_simulation_ready_explicit_env(tmp_path, monkeypatch) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "sim.json")
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    eng.mark_simulation_ready()
    assert eng.can_trade() is True


def test_broker_empty_positions_still_compares(tmp_path) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "rec2.json")
    eng.record_order("o1", "AAPL", "BUY", 10)
    eng.record_fill("o1", 10, 100.0)
    status = eng.reconcile(broker_positions={})
    assert status == ReconciliationStatus.MISMATCH


def test_reconciliation_snapshot_survives_restart(tmp_path) -> None:
    snap = tmp_path / "order_reconciliation.json"
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    eng.record_order("o99", "MSFT", "BUY", 5, client_order_id="cid-o99")
    eng2 = BrokerReconciliationEngine(snapshot_path=snap)
    gate = eng2.recovery_gate()
    assert gate["open_count"] == 1
    assert gate["requires_broker_reconcile"] is True
    assert eng2.can_trade() is False


def test_circuit_breaker_severe_requires_manual_reset() -> None:
    cb = RiskCircuitBreaker(max_daily_loss_pct=1.0, max_drawdown_pct=50.0)
    cb.peak_equity = 100_000.0
    cb.daily_pnl = -2000.0
    assert cb.update(equity=98_000.0) is False
    assert cb.manual_reset_required is True
    cb.triggered = False
    assert cb.update(equity=98_000.0) is False
    cb.clear_manual_halt()
    assert cb.manual_reset_required is False
