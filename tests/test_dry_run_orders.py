"""Dry-run order boundary — zero live broker calls when not authorised."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.brokers.base import Market, OrderSide, OrderType
from src.brokers.broker_manager import BrokerManager, BrokerType
from src.core.order_execution import LiveTradingRequiredError


@pytest.mark.asyncio
async def test_broker_manager_zero_live_calls_when_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "src.core.order_execution.simulation_ledger_path",
        lambda: tmp_path / "simulation_ledger.jsonl",
    )

    manager = BrokerManager()
    live_broker = MagicMock()
    live_broker.place_order = AsyncMock()
    paper_broker = MagicMock()
    paper_broker.place_order = AsyncMock(
        return_value=MagicMock(success=True, order_id="paper-1")
    )

    manager._brokers = {
        BrokerType.PAPER: paper_broker,
        BrokerType.IB: live_broker,
    }
    manager.set_active_broker(BrokerType.IB)

    await manager.place_order(
        "AAPL",
        OrderSide.BUY,
        10,
        order_type=OrderType.MARKET,
        market=Market.US,
        dry_run=True,
    )

    live_broker.place_order.assert_not_called()
    paper_broker.place_order.assert_called_once()
    ledger = (tmp_path / "simulation_ledger.jsonl").read_text(encoding="utf-8")
    assert "AAPL" in ledger
    assert '"mode": "dry_run"' in ledger.replace(" ", "")


@pytest.mark.asyncio
async def test_broker_manager_live_without_gate_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("LIVE_TRADING", "IB_MODE", "IB_API_PORT", "LIVE_TRADING_ACCOUNT"):
        monkeypatch.delenv(key, raising=False)

    manager = BrokerManager()
    live_broker = MagicMock()
    live_broker.place_order = AsyncMock()
    manager._brokers = {BrokerType.IB: live_broker}
    manager.set_active_broker(BrokerType.IB)

    with pytest.raises(LiveTradingRequiredError):
        await manager.place_order(
            "AAPL",
            OrderSide.BUY,
            1,
            dry_run=False,
            account="DU123",
        )

    live_broker.place_order.assert_not_called()
