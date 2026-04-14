"""
VNext P2 Institutional Review Tests
=====================================

Tests for P2 critical fixes:
  - P2-A: Look-ahead bias fix (_rolling_mean, _compute_indicators)
  - P2-B: Unified risk limits (src/core/risk_limits.py)
  - P2-C: Drawdown circuit breaker in signal engine
  - P2-D: Division-by-zero guards
  - P2-E: Market holiday handling
  - P2-F: Signal card uses real data
  - P2-G: Dashboard UX improvements
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ═══════════════════════════════════════════════════════════════
# P2-A — Look-Ahead Bias Fix
# ═══════════════════════════════════════════════════════════════


class TestRollingMeanCausal:
    """Verify _rolling_mean is right-aligned (causal) — no future leak."""

    @pytest.fixture
    def rolling_mean(self):
        from src.api.main import _rolling_mean

        return _rolling_mean

    def test_simple_case_matches_pandas(self, rolling_mean):
        """Our rolling mean should match pandas .rolling().mean()."""
        import pandas as pd

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        window = 3
        our = rolling_mean(data, window)
        pd_result = pd.Series(data).rolling(window, min_periods=1).mean().values
        np.testing.assert_allclose(our, pd_result, atol=1e-10)

    def test_no_future_data_leaks(self, rolling_mean):
        """Bar i's SMA should only use data from bars [0..i]."""
        data = np.array([10.0, 20.0, 30.0, 100.0, 200.0])
        window = 3
        result = rolling_mean(data, window)
        # Bar 2 (index 2) should be mean(10, 20, 30) = 20.0
        assert abs(result[2] - 20.0) < 1e-10
        # Bar 2 should NOT include bar 3 (100) or bar 4 (200)
        # If look-ahead leaked, result[2] would be much higher
        assert result[2] < 25.0

    def test_first_bars_use_expanding_window(self, rolling_mean):
        """First (window-1) bars should use partial/expanding window."""
        data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        window = 3
        result = rolling_mean(data, window)
        # Bar 0: mean(10) = 10
        assert abs(result[0] - 10.0) < 1e-10
        # Bar 1: mean(10, 20) = 15
        assert abs(result[1] - 15.0) < 1e-10
        # Bar 2: mean(10, 20, 30) = 20
        assert abs(result[2] - 20.0) < 1e-10

    def test_output_same_length_as_input(self, rolling_mean):
        data = np.random.randn(500)
        result = rolling_mean(data, 20)
        assert len(result) == len(data)

    def test_window_1_equals_original(self, rolling_mean):
        data = np.array([5.0, 10.0, 15.0, 20.0])
        result = rolling_mean(data, 1)
        np.testing.assert_allclose(result, data)

    def test_large_window_graceful(self, rolling_mean):
        """Window larger than data should still work."""
        data = np.array([1.0, 2.0, 3.0])
        result = rolling_mean(data, 100)
        assert len(result) == 3
        # All bars use expanding window since window > n
        assert abs(result[0] - 1.0) < 1e-10
        assert abs(result[1] - 1.5) < 1e-10
        assert abs(result[2] - 2.0) < 1e-10


class TestComputeIndicators:
    """Verify _compute_indicators returns correct structure."""

    @pytest.fixture
    def compute(self):
        from src.api.main import _compute_indicators

        return _compute_indicators

    def test_returns_all_required_keys(self, compute):
        close = np.cumsum(np.random.normal(0.1, 1.0, 300)) + 100
        close = np.maximum(close, 10)
        volume = np.random.uniform(1e6, 5e6, 300)
        result = compute(close, volume)
        for key in ["sma20", "sma50", "sma200", "rsi", "vol_ratio", "atr", "atr_pct"]:
            assert key in result, f"Missing key: {key}"
            assert len(result[key]) == 300

    def test_rsi_in_valid_range(self, compute):
        close = np.cumsum(np.random.normal(0.1, 1.0, 300)) + 100
        close = np.maximum(close, 10)
        volume = np.ones(300)
        result = compute(close, volume)
        assert np.all(result["rsi"] >= 0)
        assert np.all(result["rsi"] <= 100)

    def test_sma20_is_causal(self, compute):
        """SMA20 at bar i should not use data from bar i+1."""
        np.random.seed(42)
        close = np.ones(100) * 50.0
        close[50:] = 100.0  # sudden jump at bar 50
        volume = np.ones(100)
        result = compute(close, volume)
        # Bar 49 (before jump) should have SMA20 = 50.0
        assert abs(result["sma20"][49] - 50.0) < 1e-5
        # If future leaked, bar 49 would be > 50

    def test_atr_pct_positive(self, compute):
        close = np.cumsum(np.random.normal(0.1, 1.0, 300)) + 100
        close = np.maximum(close, 10)
        volume = np.ones(300)
        result = compute(close, volume)
        assert np.all(result["atr_pct"] >= 0)


class TestLookAheadBiasRemoved:
    """Source code analysis: confirm no np.convolve(mode='full')[:n] remains."""

    def test_no_convolve_full_in_main_signals(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        # Find all instances of mode="full" in indicator-computing contexts
        # The old pattern: np.convolve(close, np.ones(X)/X, mode="full")[:n]
        import re

        matches = re.findall(r'np\.convolve\(.+mode=["\']full["\']\)\[:n\]', src)
        assert len(matches) == 0, (
            f"Found {len(matches)} instances of np.convolve(mode='full')[:n] — "
            "these have look-ahead bias. Use _rolling_mean() instead."
        )

    def test_compute_indicators_used_in_scan(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "_compute_indicators(close, volume)" in src

    def test_rolling_mean_function_exists(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "def _rolling_mean(" in src


# ═══════════════════════════════════════════════════════════════
# P2-B — Unified Risk Limits
# ═══════════════════════════════════════════════════════════════


class TestUnifiedRiskLimits:
    """Verify src/core/risk_limits.py is the single source of truth."""

    def test_risk_limits_importable(self):
        from src.core.risk_limits import BACKTEST_DEFAULTS, RISK, SIGNAL_THRESHOLDS

        assert RISK is not None
        assert SIGNAL_THRESHOLDS is not None
        assert BACKTEST_DEFAULTS is not None

    def test_risk_has_all_fields(self):
        from src.core.risk_limits import RISK

        required = [
            "max_position_pct",
            "max_positions",
            "max_sector_pct",
            "max_drawdown_pct",
            "drawdown_warning_pct",
            "daily_loss_limit_pct",
            "max_gross_exposure",
            "risk_off_max_exposure",
            "max_portfolio_beta",
            "earnings_blackout_days",
            "target_annual_vol",
            "max_atr_pct_for_entry",
            "min_atr_pct_for_entry",
        ]
        for field in required:
            assert hasattr(RISK, field), f"RISK missing field: {field}"

    def test_signal_thresholds_has_rsi_bounds(self):
        from src.core.risk_limits import SIGNAL_THRESHOLDS

        assert SIGNAL_THRESHOLDS.rsi_oversold == 30.0
        assert SIGNAL_THRESHOLDS.rsi_overbought == 70.0

    def test_backtest_defaults_reasonable(self):
        from src.core.risk_limits import BACKTEST_DEFAULTS

        assert BACKTEST_DEFAULTS.account_size >= 10_000
        assert BACKTEST_DEFAULTS.commission_per_share > 0
        assert BACKTEST_DEFAULTS.slippage_base_bps > 0

    def test_max_position_is_5_pct(self):
        from src.core.risk_limits import RISK

        assert RISK.max_position_pct == 0.05

    def test_max_drawdown_is_15_pct(self):
        from src.core.risk_limits import RISK

        assert RISK.max_drawdown_pct == 0.15

    def test_daily_loss_limit_is_3_pct(self):
        from src.core.risk_limits import RISK

        assert RISK.daily_loss_limit_pct == 0.03

    def test_risk_limits_are_frozen(self):
        """Risk limits should be immutable (frozen dataclass)."""
        from src.core.risk_limits import RISK

        with pytest.raises(Exception):
            RISK.max_position_pct = 0.99


# ═══════════════════════════════════════════════════════════════
# P2-C — Drawdown Circuit Breaker
# ═══════════════════════════════════════════════════════════════


class TestDrawdownCircuitBreaker:
    """Verify signal engine rejects signals when account is in drawdown."""

    @pytest.fixture
    def engine(self):
        from src.engines.signal_engine import SignalEngine

        return SignalEngine.__new__(SignalEngine)

    def test_preflight_passes_normal_conditions(self, engine):
        import logging

        engine.logger = logging.getLogger("test")
        result, reason = engine._preflight_check(
            {
                "vix": 20,
                "spx_change_pct": -0.5,
                "account_drawdown_pct": 0,
                "daily_pnl_pct": 0,
            }
        )
        assert result is True

    def test_preflight_rejects_max_drawdown(self, engine):
        import logging

        engine.logger = logging.getLogger("test")
        result, reason = engine._preflight_check(
            {
                "vix": 20,
                "spx_change_pct": -0.5,
                "account_drawdown_pct": 16.0,  # > 15% limit
                "daily_pnl_pct": 0,
            }
        )
        assert result is False
        assert "drawdown" in reason.lower()

    def test_preflight_rejects_daily_loss(self, engine):
        import logging

        engine.logger = logging.getLogger("test")
        result, reason = engine._preflight_check(
            {
                "vix": 20,
                "spx_change_pct": -0.5,
                "account_drawdown_pct": 0,
                "daily_pnl_pct": -3.5,  # > 3% daily loss limit
            }
        )
        assert result is False
        assert "daily" in reason.lower()

    def test_preflight_rejects_vix_crisis(self, engine):
        import logging

        engine.logger = logging.getLogger("test")
        result, reason = engine._preflight_check(
            {
                "vix": 45,  # > 35 crisis
                "spx_change_pct": -0.5,
            }
        )
        assert result is False
        assert "vix" in reason.lower()


# ═══════════════════════════════════════════════════════════════
# P2-D — Division-by-Zero Guards
# ═══════════════════════════════════════════════════════════════


class TestDivisionByZeroGuards:
    """Verify no division by zero in critical paths."""

    def test_equity_curve_with_zero_peak(self):
        """Equity curve dd calculation should handle peak=0."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        # Check that the drawdown calculation has the guard
        assert "np.where(peak > 0" in src or "errstate" in src

    def test_rolling_mean_with_zeros(self):
        from src.api.main import _rolling_mean

        data = np.zeros(50)
        result = _rolling_mean(data, 20)
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))

    def test_compute_indicators_with_constant_price(self):
        """Constant price should not cause division errors."""
        from src.api.main import _compute_indicators

        close = np.ones(100) * 50.0
        volume = np.ones(100) * 1e6
        result = _compute_indicators(close, volume)
        assert not np.any(np.isnan(result["sma20"]))
        assert not np.any(np.isinf(result["sma20"]))
        # RSI should be ~50 for constant price (no gains or losses)
        # Due to implementation, it should be 50 or handle gracefully
        assert not np.any(np.isnan(result["rsi"]))


# ═══════════════════════════════════════════════════════════════
# P2-E — Market Holiday Handling
# ═══════════════════════════════════════════════════════════════


class TestMarketHolidays:
    """Verify _is_market_open handles US holidays."""

    def test_holiday_set_exists(self):
        from src.api.main import _US_MARKET_HOLIDAYS_2024_2027

        assert len(_US_MARKET_HOLIDAYS_2024_2027) >= 30  # 10/year × 3-4 years

    def test_christmas_2025_is_holiday(self):
        from src.api.main import _US_MARKET_HOLIDAYS_2024_2027

        assert (2025, 12, 25) in _US_MARKET_HOLIDAYS_2024_2027

    def test_july_4_2026_observed(self):
        from src.api.main import _US_MARKET_HOLIDAYS_2024_2027

        # July 4 2026 is Saturday, observed Friday July 3
        assert (2026, 7, 3) in _US_MARKET_HOLIDAYS_2024_2027

    def test_source_code_checks_holidays(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        idx = src.find("def _is_market_open")
        assert idx > 0
        func_body = src[idx : idx + 500]
        assert "_US_MARKET_HOLIDAYS" in func_body


# ═══════════════════════════════════════════════════════════════
# P2-F — Signal Card Real Data
# ═══════════════════════════════════════════════════════════════


class TestSignalCardRealData:
    """Verify signal card no longer returns hardcoded demo data."""

    def test_no_hardcoded_150_price(self):
        """The old fake card had entry_price=150.0 for all tickers."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        idx = src.find("def get_signal_card")
        assert idx > 0
        func_body = src[idx : idx + 3000]
        # Should NOT contain the old hardcoded values
        assert "entry_price=150.0" not in func_body
        assert "stop_loss=142.5" not in func_body
        assert "confidence=0.78" not in func_body

    def test_uses_market_data(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        idx = src.find("def get_signal_card")
        assert idx > 0
        func_body = src[idx : idx + 3000]
        assert "get_quote" in func_body or "get_history" in func_body

    def test_uses_compute_indicators(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        idx = src.find("def get_signal_card")
        assert idx > 0
        func_body = src[idx : idx + 3000]
        assert "_compute_indicators" in func_body


# ═══════════════════════════════════════════════════════════════
# P2-G — Dashboard UX Improvements
# ═══════════════════════════════════════════════════════════════


class TestDashboardUXImprovements:
    """Verify dashboard has new regime banner and risk guards."""

    @pytest.fixture
    def template(self):
        return (
            Path(__file__).parent.parent / "src" / "api" / "templates" / "index.html"
        ).read_text()

    def test_regime_alert_banner_exists(self, template):
        """Should have a RISK-OFF / TRADING HALTED banner."""
        assert "RISK-OFF REGIME" in template or "TRADING HALTED" in template

    def test_risk_guard_banner_on_signals(self, template):
        assert "Risk Guard Active" in template

    def test_risk_on_banner_exists(self, template):
        assert "Normal Trading Conditions" in template

    def test_methodology_mentions_causal(self, template):
        """Should mention causal/right-aligned indicators."""
        assert "causal" in template.lower() or "right-aligned" in template.lower()

    def test_methodology_mentions_not_financial_advice(self, template):
        assert "not financial advice" in template.lower()

    def test_methodology_mentions_transaction_costs(self, template):
        assert (
            "commission" in template.lower() or "transaction cost" in template.lower()
        )


# ═══════════════════════════════════════════════════════════════
# P2-H — Cross-Cutting Integrity Checks
# ═══════════════════════════════════════════════════════════════


class TestCrossCuttingIntegrity:
    """System-wide integrity checks."""

    def test_no_convolve_full_anywhere_in_indicators(self):
        """No look-ahead convolution should remain in indicator code paths."""
        import re

        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        # Find np.convolve with mode="full" followed by [:n]
        pattern = r'np\.convolve\([^)]+mode=["\']full["\']\)\[:n\]'
        matches = re.findall(pattern, src)
        assert (
            len(matches) == 0
        ), f"Found {len(matches)} look-ahead bias patterns still in code"

    def test_risk_limits_file_exists(self):
        path = Path(__file__).parent.parent / "src" / "core" / "risk_limits.py"
        assert path.exists()

    def test_signal_engine_imports_risk_limits(self):
        src = (
            Path(__file__).parent.parent / "src" / "engines" / "signal_engine.py"
        ).read_text()
        assert "risk_limits" in src

    def test_main_has_compute_indicators(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "def _compute_indicators(" in src
        assert "def _rolling_mean(" in src
