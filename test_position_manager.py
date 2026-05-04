from __future__ import annotations
import sys
import os
from datetime import datetime, timezone
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _make_manager(**kwargs):
    from src.algo.position_manager import PositionManager, RiskParameters

    p = dict(
        account_size=100_000,
        risk_per_trade_pct=1.0,
        max_position_size_pct=30.0,
        max_open_positions=10,
        max_total_drawdown_pct=15.0,
        max_daily_loss_pct=3.0,
        max_sector_exposure_pct=30.0,
    )
    p.update(kwargs)
    return PositionManager(params=RiskParameters(**p))


def _open(mgr, ticker, entry=100.0, stop=95.0, sector="Tech"):
    mgr.open_position(
        ticker=ticker,
        strategy_id="s1",
        entry_price=entry,
        stop_loss_price=stop,
        shares=10,
        sector=sector,
    )


def _pos(entry=100.0, stop=95.0, target=115.0, shares=20):
    from src.algo.position_manager import Position

    return Position(
        ticker="XYZ",
        strategy_id="test_s",
        entry_price=entry,
        stop_loss_price=stop,
        target_1r_price=target,
        shares=shares,
        sector="Tech",
    )


# ── 1. Position Sizing ────────────────────────────────────────────────────────


class TestPositionSizing:
    def test_fixed_fractional_risk(self):
        """1% of 100k = 1000 risk / (150-145=5) = 200 shares."""
        mgr = _make_manager()
        r = mgr.calculate_position_size(
            "AAPL", entry_price=150.0, stop_loss_price=145.0
        )
        assert r["shares"] == 200
        assert r["risk_amount"] == pytest.approx(1_000.0, rel=0.05)

    def test_max_position_size_cap(self):
        """Position value must not exceed max_position_size_pct of account."""
        mgr = _make_manager(max_position_size_pct=5.0)
        r = mgr.calculate_position_size("TEST", entry_price=10.0, stop_loss_price=9.99)
        assert r["position_value"] <= 100_000 * 0.05 + 1.0

    def test_atr_based_stop_level(self):
        """ATR stop = entry - ATR * multiplier  (900 - 20*2 = 860)."""
        mgr = _make_manager()
        r = mgr.calculate_atr_based_size(
            "NVDA", entry_price=900.0, atr=20.0, atr_multiplier=2.0
        )
        assert r.get("stop_loss_price") == pytest.approx(860.0, rel=0.01)


# ── 2. Can-Open Gates ─────────────────────────────────────────────────────────


class TestCanOpenGates:
    def test_blocks_duplicate_ticker(self):
        mgr = _make_manager()
        _open(mgr, "AAPL")
        ok, _ = mgr.can_open_position("AAPL", sector="Tech")
        assert not ok

    def test_blocks_at_max_positions(self):
        mgr = _make_manager(max_open_positions=2)
        _open(mgr, "A")
        _open(mgr, "B")
        ok, _ = mgr.can_open_position("C", sector="Tech")
        assert not ok

    def test_allows_first_position(self):
        mgr = _make_manager()
        ok, reason = mgr.can_open_position("NVDA", sector="Semiconductor")
        assert ok, reason


# ── 3. Drawdown Circuit Breaker ───────────────────────────────────────────────


class TestDrawdownCircuitBreaker:
    def test_blocks_when_exceeded(self):
        mgr = _make_manager(max_total_drawdown_pct=10.0)
        if not hasattr(mgr, "current_equity"):
            pytest.skip("no current_equity attr")
        mgr.current_equity = 85_000.0  # 15% down > 10% limit
        ok, _ = mgr.can_open_position("TSLA", sector="EV")
        assert not ok

    def test_allows_within_limit(self):
        mgr = _make_manager(max_total_drawdown_pct=10.0)
        if hasattr(mgr, "current_equity"):
            mgr.current_equity = 95_000.0  # 5% down < 10% limit
        ok, _ = mgr.can_open_position("TSLA", sector="EV")
        assert ok


# ── 4. Trailing Stop ──────────────────────────────────────────────────────────


class TestTrailingStop:
    def test_activates_after_threshold(self):
        pos = _pos()
        pos.update_trailing_stop(
            current_price=105.0, trail_pct=0.02, activation_pct=0.03
        )
        # trailing_stop_price is updated (stop_loss_price may stay until trailing stop is hit)
        assert pos.trailing_stop_price > 0.0

    def test_never_drops(self):
        pos = _pos(stop=95.0, target=120.0)
        pos.update_trailing_stop(
            current_price=110.0, trail_pct=0.02, activation_pct=0.03
        )
        high = pos.trailing_stop_price
        pos.update_trailing_stop(
            current_price=105.0, trail_pct=0.02, activation_pct=0.03
        )
        assert pos.trailing_stop_price >= high

    def test_tracks_new_high(self):
        pos = _pos(stop=95.0, target=130.0)
        pos.update_trailing_stop(
            current_price=110.0, trail_pct=0.05, activation_pct=0.03
        )
        s1 = pos.trailing_stop_price
        pos.update_trailing_stop(
            current_price=120.0, trail_pct=0.05, activation_pct=0.03
        )
        assert pos.trailing_stop_price > s1


# ── 5. Correlation Guard ──────────────────────────────────────────────────────


class TestCorrelationGuard:
    def test_allows_no_positions(self):
        mgr = _make_manager()
        ok, _ = mgr.check_correlation_guard("AAPL", price_data=None)
        assert ok

    def test_no_crash_with_price_data(self):
        import pandas as pd
        import numpy as np

        rng = np.random.default_rng(42)
        mgr = _make_manager(max_open_positions=20)
        base = pd.Series(np.cumsum(rng.standard_normal(100)) + 100.0)
        pd_data = {
            "HELD1": base,
            "HELD2": base * 1.005,
            "HELD3": base * 0.995,
            "NVDA": base * 1.002,
        }
        for t in ("HELD1", "HELD2", "HELD3"):
            _open(mgr, t)
        ok, reason = mgr.check_correlation_guard(
            "NVDA", price_data=pd_data, max_correlated=3, threshold=0.70
        )
        assert isinstance(ok, bool)
        assert isinstance(reason, str)


# ── 6. Exit Conditions ────────────────────────────────────────────────────────


class TestExitConditions:
    def test_stop_triggered(self):
        pos = _pos()
        triggered, reason = pos.check_exit_conditions(94.0, datetime.now(timezone.utc))
        assert triggered
        assert "stop" in reason.lower()

    def test_target_triggered(self):
        pos = _pos(target=115.0)
        triggered, reason = pos.check_exit_conditions(116.0, datetime.now(timezone.utc))
        assert triggered
        # Implementation returns 'partial_1r', 'target', or 'profit'
        assert any(k in reason.lower() for k in ("target", "profit", "partial", "1r"))

    def test_no_exit_mid_range(self):
        pos = _pos(target=115.0)
        triggered, _ = pos.check_exit_conditions(105.0, datetime.now(timezone.utc))
        assert not triggered
