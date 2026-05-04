"""
VNext P2/P3 Institutional Review Tests
========================================

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


# ═══════════════════════════════════════════════════════════════
# P2.1 — Risk Limits Wiring
# ═══════════════════════════════════════════════════════════════


class TestRiskLimitsWiring:
    """Verify all modules reference risk_limits instead of hardcoded values."""

    def test_main_imports_risk_limits(self):
        """main.py should import from risk_limits."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "from src.core.risk_limits import" in src

    def test_main_uses_signal_thresholds_for_rsi(self):
        """main.py should reference SIGNAL_THRESHOLDS for RSI checks."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "SIGNAL_THRESHOLDS.rsi_oversold" in src
        assert "SIGNAL_THRESHOLDS.rsi_overbought" in src
        assert "SIGNAL_THRESHOLDS.rsi_momentum_low" in src
        assert "SIGNAL_THRESHOLDS.rsi_momentum_high" in src

    def test_main_uses_backtest_defaults(self):
        """Backtest constants should come from BACKTEST_DEFAULTS."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "BACKTEST_DEFAULTS.commission_per_share" in src
        assert "BACKTEST_DEFAULTS.slippage_base_bps" in src
        assert "BACKTEST_DEFAULTS.account_size" in src

    def test_main_uses_risk_max_position_pct(self):
        """Position sizing should reference RISK.max_position_pct."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "RISK.max_position_pct" in src

    def test_main_uses_signal_thresholds_for_volume(self):
        """Volume surge thresholds should reference SIGNAL_THRESHOLDS."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "SIGNAL_THRESHOLDS.volume_surge_threshold" in src
        assert "SIGNAL_THRESHOLDS.volume_strong_surge" in src

    def test_main_uses_signal_thresholds_for_stops(self):
        """ATR stop multipliers should reference SIGNAL_THRESHOLDS."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "SIGNAL_THRESHOLDS.stop_atr_multiplier_momentum" in src
        assert "SIGNAL_THRESHOLDS.stop_atr_multiplier_breakout" in src
        assert "SIGNAL_THRESHOLDS.stop_atr_multiplier_swing" in src

    def test_main_uses_signal_thresholds_for_targets(self):
        """Target return percentages should reference SIGNAL_THRESHOLDS."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "SIGNAL_THRESHOLDS.target_trending" in src
        assert "SIGNAL_THRESHOLDS.target_swing_trending" in src

    def test_main_uses_signal_thresholds_for_confidence(self):
        """Grade thresholds should reference SIGNAL_THRESHOLDS."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "SIGNAL_THRESHOLDS.strong_buy_threshold" in src
        assert "SIGNAL_THRESHOLDS.buy_threshold" in src
        assert "SIGNAL_THRESHOLDS.watch_threshold" in src
        assert "SIGNAL_THRESHOLDS.abstention_threshold" in src

    def test_portfolio_risk_budget_imports_risk(self):
        """portfolio_risk_budget.py should import RISK from risk_limits."""
        src = (
            Path(__file__).parent.parent
            / "src"
            / "engines"
            / "portfolio_risk_budget.py"
        ).read_text()
        assert "from src.core.risk_limits import RISK" in src

    def test_portfolio_risk_budget_uses_risk_values(self):
        """DEFAULT_LIMITS should reference RISK singleton fields."""
        src = (
            Path(__file__).parent.parent
            / "src"
            / "engines"
            / "portfolio_risk_budget.py"
        ).read_text()
        assert "RISK.max_position_pct" in src
        assert "RISK.max_sector_pct" in src
        assert "RISK.max_positions" in src

    def test_position_manager_aligned(self):
        """position_manager RiskParameters should match RISK defaults."""
        from src.algo.position_manager import RiskParameters
        from src.core.risk_limits import RISK

        rp = RiskParameters()
        assert rp.max_position_size_pct == RISK.max_position_pct * 100
        assert rp.max_open_positions == RISK.max_positions
        assert rp.max_total_drawdown_pct == RISK.max_drawdown_pct * 100
        assert rp.max_daily_loss_pct == RISK.daily_loss_limit_pct * 100

    def test_signal_thresholds_has_new_fields(self):
        """Verify newly added fields exist."""
        from src.core.risk_limits import SIGNAL_THRESHOLDS

        assert hasattr(SIGNAL_THRESHOLDS, "rsi_near_oversold")
        assert SIGNAL_THRESHOLDS.rsi_near_oversold == 35.0
        assert hasattr(SIGNAL_THRESHOLDS, "rsi_near_overbought")
        assert SIGNAL_THRESHOLDS.rsi_near_overbought == 65.0
        assert hasattr(SIGNAL_THRESHOLDS, "volume_strong_surge")
        assert SIGNAL_THRESHOLDS.volume_strong_surge == 1.5
        assert hasattr(SIGNAL_THRESHOLDS, "high_confidence_threshold")
        assert SIGNAL_THRESHOLDS.high_confidence_threshold == 75.0


# ═══════════════════════════════════════════════════════════════
# P3 — Correlation Guard, Regime Hysteresis, Stale Data
# ═══════════════════════════════════════════════════════════════


class TestSectorCorrelationGuard:
    """Verify sector clustering and max-signals-per-sector filter."""

    def test_ticker_sector_map_exists(self):
        from src.api.main import _TICKER_SECTOR

        assert isinstance(_TICKER_SECTOR, dict)
        assert len(_TICKER_SECTOR) > 10

    def test_sector_clusters_defined(self):
        from src.api.main import _SECTOR_CLUSTERS

        assert "Semiconductor" in _SECTOR_CLUSTERS
        assert "Big Tech" in _SECTOR_CLUSTERS
        assert "NVDA" in _SECTOR_CLUSTERS["Semiconductor"]
        assert "AAPL" in _SECTOR_CLUSTERS["Big Tech"]

    def test_max_signals_per_sector_uses_risk_limits(self):
        from src.api.main import _MAX_SIGNALS_PER_SECTOR
        from src.core.risk_limits import RISK

        assert _MAX_SIGNALS_PER_SECTOR == RISK.max_correlated_names

    def test_ticker_to_sector_lookup(self):
        from src.api.main import _TICKER_SECTOR

        assert _TICKER_SECTOR.get("NVDA") == "Semiconductor"
        assert _TICKER_SECTOR.get("AAPL") == "Big Tech"
        assert _TICKER_SECTOR.get("JPM") == "Financials"
        assert _TICKER_SECTOR.get("SPY") == "ETF"

    def test_scanner_output_includes_sector_field(self):
        """Source code should add 'sector' to each recommendation."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert 'rec["sector"]' in src or "rec['sector']" in src

    def test_sector_cap_filter_in_scanner(self):
        """Scanner should have sector_counts filtering logic."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "sector_counts" in src
        assert "_MAX_SIGNALS_PER_SECTOR" in src


class TestRegimeHysteresis:
    """Verify EMA smoothing + minimum hold time in RegimeRouter."""

    def test_regime_router_has_ema_state(self):
        from src.engines.regime_router import RegimeRouter

        router = RegimeRouter()
        assert hasattr(router, "_ema_probs")
        assert hasattr(router, "_ema_alpha")
        assert hasattr(router, "_min_hold_seconds")

    def test_ema_smoothing_dampens_transitions(self):
        """With alpha=0.3, a sudden shift should be dampened."""
        from src.engines.regime_router import RegimeRouter

        router = RegimeRouter(ema_alpha=0.3, min_hold_seconds=0)
        # First call: risk-on market
        r1 = router.classify({"vix": 14, "spy_return_20d": 0.05, "breadth_pct": 0.7})
        assert r1.risk_on_uptrend > 0.4  # should be risk-on

        # Second call: suddenly risk-off
        r2 = router.classify({"vix": 32, "spy_return_20d": -0.05, "breadth_pct": 0.25})
        # EMA should smooth this — risk_off shouldn't immediately dominate
        # The EMA of (old risk_on + new risk_off) creates a blended state
        assert r2.risk_off_downtrend < 0.8  # dampened, not 100% risk-off

    def test_minimum_hold_time_prevents_whipsaw(self):
        """Regime should not flip if min_hold_seconds hasn't elapsed."""
        from src.engines.regime_router import RegimeRouter

        router = RegimeRouter(ema_alpha=1.0, min_hold_seconds=600)
        # First call establishes a regime
        r1 = router.classify({"vix": 14, "spy_return_20d": 0.05, "breadth_pct": 0.7})
        first_regime = r1.regime

        # Immediately call with opposite data — should NOT flip (hold time)
        r2 = router.classify({"vix": 32, "spy_return_20d": -0.05, "breadth_pct": 0.25})
        assert r2.regime == first_regime  # held due to min_hold

    def test_crisis_overrides_hold_time(self):
        """VIX crisis should override the minimum hold time."""
        from src.engines.regime_router import RegimeRouter

        router = RegimeRouter(ema_alpha=1.0, min_hold_seconds=600)
        # Establish risk-on
        r1 = router.classify({"vix": 14, "spy_return_20d": 0.05, "breadth_pct": 0.7})
        # Crisis VIX — should flip immediately despite hold time
        r2 = router.classify({"vix": 40, "spy_return_20d": -0.08, "breadth_pct": 0.20})
        assert r2.should_trade is False  # crisis override


class TestStaleDataDetection:
    """Verify stale data detection helper."""

    def test_check_data_freshness_exists(self):
        from src.api.main import _check_data_freshness

        assert callable(_check_data_freshness)

    def test_fresh_data_returns_true(self):
        import time

        from src.api.main import _check_data_freshness

        result = _check_data_freshness(time.time() - 10, "test")
        assert result["fresh"] is True
        assert result["warning"] is None

    def test_stale_data_returns_warning(self):
        import time

        from src.api.main import _check_data_freshness

        result = _check_data_freshness(time.time() - 100000, "test")
        assert result["fresh"] is False
        assert result["warning"] is not None
        assert (
            "stale" in result["warning"].lower() or "old" in result["warning"].lower()
        )

    def test_none_timestamp_returns_unknown(self):
        from src.api.main import _check_data_freshness

        result = _check_data_freshness(None, "test")
        assert result["fresh"] is False
        assert "unknown" in result["warning"].lower()

    def test_dashboard_has_stale_banner(self):
        """Dashboard should render a stale data warning banner."""
        src = (
            Path(__file__).parent.parent / "src" / "api" / "templates" / "index.html"
        ).read_text()
        assert "data_freshness" in src
        assert "DATA MAY BE STALE" in src

    def test_recommendations_endpoint_includes_freshness(self):
        """The recommendations endpoint should include data_freshness."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert '"data_freshness"' in src or "'data_freshness'" in src
