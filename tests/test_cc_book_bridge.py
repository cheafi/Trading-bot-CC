"""CC book bridge — holdings normalization and live curve inputs."""

from __future__ import annotations

from src.services.cc_book_bridge import (
    load_live_strategy_health,
    normalize_portfolio_positions,
    resolve_curve_inputs_for_os,
)


def test_normalize_portfolio_positions():
    rows = normalize_portfolio_positions(
        [{"ticker": "AAPL", "sector": "Technology"}, {"symbol": "MSFT"}]
    )
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"
    assert rows[1]["sector"] == "unknown"


def test_resolve_curve_inputs_degraded_without_live():
    out = resolve_curve_inputs_for_os(live_health=None, degraded=True)
    assert out.get("degraded") is True


def test_load_live_strategy_health_no_crash():
    result = load_live_strategy_health()
    assert result is None or result.get("may_authorize_deploy") is False
