"""Order intent → reconciliation ledger wiring."""

from __future__ import annotations

from src.core.order_execution import track_broker_fill, track_broker_order_intent
from src.engines.broker_reconciliation import BrokerReconciliationEngine
from src.engines.trade_gate import TradeGate


def test_track_order_intent_blocks_until_reconciled(
    tmp_path, monkeypatch
) -> None:
    snap = tmp_path / "ledger.json"
    eng = BrokerReconciliationEngine(snapshot_path=snap)
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    monkeypatch.setattr(
        "src.engines.trade_gate.broker_reconciliation", eng, raising=False
    )
    assert eng.reconcile(broker_positions={}) is not None
    assert eng.can_trade() is True
    oid = track_broker_order_intent(
        source="test",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_id="t1",
    )
    assert oid == "t1"
    assert eng.can_trade() is False
    track_broker_fill(oid, filled_quantity=1, avg_fill_price=100.0)
    eng.reconcile(broker_positions={"SPY": 1})
    assert eng.can_trade() is True


def test_trade_gate_hard_blocks_when_reconciliation_not_ok(
    tmp_path, monkeypatch
) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "g.json")
    eng.record_order("x1", "AAPL", "BUY", 1)
    monkeypatch.setattr(
        "src.engines.broker_reconciliation.broker_reconciliation", eng
    )
    gate = TradeGate()
    result = gate.evaluate()
    assert result.allowed is False
    assert any("reconciliation" in b.lower() for b in result.hard_blocks)
