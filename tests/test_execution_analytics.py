"""Execution analytics — no deploy authority."""

from src.services.execution_analytics import (
    STATUS_DEGRADED,
    STATUS_UNKNOWN,
    build_execution_analytics,
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
