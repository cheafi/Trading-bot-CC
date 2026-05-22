"""Sprint 44: fractional-Kelly position sizing + dashboard data wiring."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

import pytest

from src.algo.position_manager import (
    PositionManager,
    RiskParameters,
    calculate_kelly_fraction,
)


@dataclass
class _ClosedTrade:
    realized_pnl: float
    realized_pnl_pct: float = 0.0


def _seed_pm(wins: int, losses: int, win_size: float, loss_size: float) -> PositionManager:
    pm = PositionManager(params=RiskParameters(account_size=100_000.0))
    closed: List[_ClosedTrade] = []
    closed.extend(_ClosedTrade(realized_pnl=win_size) for _ in range(wins))
    closed.extend(_ClosedTrade(realized_pnl=-loss_size) for _ in range(losses))
    pm.closed_positions = closed  # type: ignore[assignment]
    return pm


class TestKellyFraction:
    def test_positive_edge_returns_positive(self):
        # 60% win rate, 2:1 payoff -> Kelly = 0.6 - 0.4/2 = 0.40; *0.25 = 0.10
        k = calculate_kelly_fraction(win_rate=60, avg_win=200, avg_loss=100, fraction=0.25)
        assert k == pytest.approx(0.10, abs=1e-6)

    def test_negative_edge_clamps_to_zero(self):
        k = calculate_kelly_fraction(win_rate=30, avg_win=100, avg_loss=200)
        assert k == 0.0

    def test_full_kelly_capped_at_25pct(self):
        # huge edge: 90% wr, 10:1 payoff -> raw Kelly 0.89; full fraction
        k = calculate_kelly_fraction(win_rate=90, avg_win=1000, avg_loss=100, fraction=1.0)
        assert k <= 0.25 + 1e-9


class TestKellyMultiplier:
    def test_insufficient_history_returns_none(self):
        pm = _seed_pm(wins=5, losses=5, win_size=200, loss_size=100)
        assert pm._kelly_multiplier() is None

    def test_positive_edge_scales_up(self):
        # 70% win, 2:1 payoff -> Kelly% large, multiplier should be > 1
        pm = _seed_pm(wins=21, losses=9, win_size=200, loss_size=100)
        mult = pm._kelly_multiplier()
        assert mult is not None
        assert mult > 1.0
        assert mult <= 1.5  # ceiling

    def test_negative_edge_clamps_to_floor(self):
        pm = _seed_pm(wins=8, losses=22, win_size=100, loss_size=200)
        mult = pm._kelly_multiplier()
        assert mult == 0.25  # floor

    def test_applied_in_sizing(self, monkeypatch):
        monkeypatch.setenv("KELLY_SIZING", "true")
        pm = _seed_pm(wins=21, losses=9, win_size=200, loss_size=100)
        result = pm.calculate_position_size(
            ticker="AAPL", entry_price=100.0, stop_loss_price=95.0,
        )
        assert result["shares"] > 0

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("KELLY_SIZING", "false")
        pm = _seed_pm(wins=21, losses=9, win_size=200, loss_size=100)
        with_kelly_off = pm.calculate_position_size(
            ticker="AAPL", entry_price=100.0, stop_loss_price=95.0,
        )
        monkeypatch.setenv("KELLY_SIZING", "true")
        with_kelly_on = pm.calculate_position_size(
            ticker="AAPL", entry_price=100.0, stop_loss_price=95.0,
        )
        assert with_kelly_on["shares"] >= with_kelly_off["shares"]


class TestDashboardLiveFallback:
    """When engine has no cached market_state, /api/dashboard should populate
    from yfinance-backed /api/live/market so users always see data."""

    def test_dashboard_endpoint_imports(self):
        from src.api.main import get_dashboard_data, _bootstrap_engine  # noqa: F401
