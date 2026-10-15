"""IBKR reconciliation replay (no live gateway)."""

from __future__ import annotations

from src.engines.broker_reconciliation import BrokerReconciliationEngine
from src.services.broker_reconciliation_ibkr import positions_to_qty_map


def test_import_broker_open_orders(tmp_path) -> None:
    eng = BrokerReconciliationEngine(snapshot_path=tmp_path / "r.json")
    orders = [
        {
            "order_id": "42",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "status": "Filled",
            "filled": 10,
        }
    ]
    out = eng.import_broker_open_orders(orders)
    assert out["imported"] == 1
    eng.reconcile(broker_positions={"AAPL": 10})
    assert eng.can_trade() is True


def test_positions_to_qty_map_long_short() -> None:
    class Pos:
        def __init__(self, symbol, quantity, side):
            self.symbol = symbol
            self.quantity = quantity
            self.side = side

    m = positions_to_qty_map([Pos("SPY", 5, "long"), Pos("QQQ", 2, "short")])
    assert m["SPY"] == 5
    assert m["QQQ"] == -2
