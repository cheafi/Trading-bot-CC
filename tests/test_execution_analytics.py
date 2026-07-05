"""Execution analytics — no deploy authority."""

from src.services.execution_analytics import (
    STATUS_DEGRADED,
    STATUS_UNKNOWN,
    build_execution_analytics,
    build_execution_analytics_from_ibkr,
    build_recent_fills_summary,
    evaluate_fill_quality,
)


def test_degraded_slippage():
    assert evaluate_fill_quality(slippage_bps=30, fill_rate_pct=90) == STATUS_DEGRADED


def test_payload_no_authorize_execution():
    p = build_execution_analytics(ibkr_connected=False, degraded=True)
    assert p["authorizes_execution"] is False
    assert p["backtest_not_live_edge"] is True


def test_unknown_low_sample():
    p = build_execution_analytics(orders_sampled=2, degraded=True)
    assert p["fill_quality"]["status"] == STATUS_UNKNOWN


def test_sample_state_insufficient_when_degraded():
    p = build_execution_analytics(orders_sampled=2, degraded=True)
    assert p["sample_state"] == "insufficient_sample"
    assert p["sample_state_label"]


def test_ibkr_fills_bridge_insufficient_sample():
    fills = [
        {"exec_id": "1", "symbol": "AAPL", "quantity": 10, "price": 150.0},
        {"exec_id": "2", "symbol": "MSFT", "quantity": 5, "price": 400.0},
    ]
    p = build_execution_analytics_from_ibkr(fills, ibkr_connected=True)
    assert p["authorizes_execution"] is False
    assert p["orders_sampled"] == 2
    assert p["sample_state"] == "insufficient_sample"


def test_ibkr_fills_bridge_live_sample():
    fills = [
        {"exec_id": str(i), "symbol": "SPY", "quantity": 1, "price": 500.0}
        for i in range(6)
    ]
    p = build_recent_fills_summary(fills)
    assert p["orders_sampled"] == 6
    assert p["sample_state"] == "live_sample"
    assert p["authorizes_execution"] is False

