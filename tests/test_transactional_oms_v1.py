"""Transactional OMS v1: bracket intents + unknown-pending gate."""

from __future__ import annotations

from src.core.order_execution import track_ibkr_bracket_intents
from src.engines.broker_reconciliation import BrokerReconciliationEngine, OrderState


def test_track_ibkr_bracket_intents_records_three_legs(tmp_path, monkeypatch) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "bracket.json")
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    monkeypatch.setattr(
        "src.core.order_execution.broker_reconciliation", eng, raising=False
    )
    ids = track_ibkr_bracket_intents(
        symbol="SPY",
        parent_action="BUY",
        child_action="SELL",
        quantity=10,
        parent_order_id=1001,
        stop_order_id=1002,
        target_order_id=1003,
        entry_price=450.0,
        stop_price=440.0,
        take_profit=470.0,
        oca_group="OCA-SPY-1",
    )
    assert ids == {"parent": "1001", "stop": "1002", "target": "1003"}
    assert set(eng._orders.keys()) == {"1001", "1002", "1003"}
    assert eng.can_trade() is False


def test_unknown_pending_blocks_can_trade(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CC_RECON_SIMULATION_READY", "1")
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "unk.json")
    eng.mark_simulation_ready()
    eng.record_order("u1", "AAPL", "BUY", 1)
    eng._orders["u1"].state = OrderState.CANCELLED
    eng.mark_simulation_ready()
    assert eng.can_trade() is True
    eng.mark_order_unknown_pending("u1", "timeout")
    assert eng._orders["u1"].state == OrderState.UNKNOWN_PENDING
    assert eng.can_trade() is False
