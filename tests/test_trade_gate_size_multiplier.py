"""TradeGate soft-gate size reduction must reach the broker order.

Regression guard: the gate's ``size_multiplier`` used to be applied to
``rec.position_size_shares`` before sizing had run (default 0), so elevated-VIX /
uncertain-regime / earnings-week reductions never affected the submitted order.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.brokers.base import OrderResult, OrderStatus
from src.core.models import Direction
from src.engines.auto_trading_engine import AutoTradingEngine, RiskCircuitBreaker
from src.engines.trade_gate import TradeGate


class _StubRec:
    """Minimal stand-in for TradeRecommendation on the execution path."""

    def __init__(self):
        self.ticker = "AAPL"
        self.direction = Direction.LONG.value
        self.strategy_id = "momentum"
        self.edge_p_t1 = 0.55
        self.risk_reward_ratio = 2.0
        self.entry_price = 100.0
        self.signal_confidence = 80.0
        self.composite_score = 0.9
        self.source_strategies = ["momentum"]
        self.position_size_shares = 0
        self.executed = False
        self.execution_time = None
        self.fill_price = None
        self.trust = None

    def to_entry_snapshot(self):
        return {"ticker": self.ticker}


class _StubBroker:
    def __init__(self):
        self.orders = []

    async def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return OrderResult(
            success=True,
            order_id="stub-1",
            status=OrderStatus.FILLED,
            filled_qty=kwargs["quantity"],
            avg_fill_price=100.0,
            timestamp=datetime.now(timezone.utc),
        )


def _engine(sized_qty: int) -> tuple[AutoTradingEngine, _StubBroker]:
    """Build an engine shell without running the heavy __init__ wiring."""
    eng = AutoTradingEngine.__new__(AutoTradingEngine)
    broker = _StubBroker()
    eng.dry_run = False
    eng._cached_regime = {}
    eng._calculate_position_size = lambda *a, **k: sized_qty
    eng._get_broker = lambda: asyncio.sleep(0, result=broker)
    eng._notify_trade_executed = lambda *a, **k: asyncio.sleep(0)
    return eng, broker


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_gate_multiplier_reduces_submitted_quantity():
    eng, broker = _engine(sized_qty=100)
    result = _run(eng._execute_recommendation(_StubRec(), gate_size_mult=0.5))

    assert result is not None
    assert broker.orders[0]["quantity"] == 50


def test_full_multiplier_leaves_quantity_untouched():
    eng, broker = _engine(sized_qty=100)
    _run(eng._execute_recommendation(_StubRec(), gate_size_mult=1.0))

    assert broker.orders[0]["quantity"] == 100


@pytest.mark.parametrize("sized_qty", [0, -5])
def test_sizing_veto_places_no_order(sized_qty):
    eng, broker = _engine(sized_qty=sized_qty)
    result = _run(eng._execute_recommendation(_StubRec()))

    assert result is None
    assert broker.orders == []


def test_recorded_shares_match_submitted_quantity():
    """position_size_shares feeds PositionManager tracking; it must not drift."""
    eng, broker = _engine(sized_qty=80)
    rec = _StubRec()
    _run(eng._execute_recommendation(rec, gate_size_mult=0.5))

    assert rec.position_size_shares == broker.orders[0]["quantity"] == 40


def test_gate_soft_warnings_produce_sub_unity_multiplier():
    """The gate must actually emit a reduction for the engine to apply."""
    gate = TradeGate(vix_soft_warn=25.0, vix_hard_block=45.0)
    result = gate.evaluate(vix=30.0, regime="TRENDING")

    assert result.allowed is True
    assert 0.0 < result.size_multiplier < 1.0


def test_daily_loss_window_uses_utc_not_local_time():
    """A local-midnight rollover would clear the daily loss limit mid-session."""
    cb = RiskCircuitBreaker()

    assert cb.today == datetime.now(timezone.utc).date()

    cb.reset_daily()
    assert cb.today == datetime.now(timezone.utc).date()
