"""
Tests for src/services/indicators.py

Risk principle: every indicator must be CAUSAL (no look-ahead bias).
Team RISK verdict: look-ahead in indicators = silent P&L fraud.
"""
import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.indicators import (
    rolling_mean,
    rolling_std,
    ema,
    _ema_fast,
    compute_indicators,
    dual_thrust_levels,
    compute_rs_vs_benchmark,
    signal_quality_features,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def price_series():
    """100 bars of deterministic price data (sin wave + trend)."""
    np.random.seed(42)
    t = np.arange(100)
    return 100.0 + 20.0 * np.sin(t * 0.2) + 0.1 * t


@pytest.fixture
def volume_series():
    np.random.seed(7)
    return np.abs(np.random.normal(1_000_000, 200_000, 100))


@pytest.fixture
def ohlcv(price_series, volume_series):
    close = price_series
    high  = close + np.random.uniform(0, 2, len(close))
    low   = close - np.random.uniform(0, 2, len(close))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return high, low, close, open_, volume_series


# ── Causal / look-ahead tests ─────────────────────────────────────

class TestCausalProperty:
    """CRITICAL: indicators must not peek at future bars."""

    def test_rolling_mean_is_right_aligned(self, price_series):
        """rolling_mean[i] must only use bars 0..i."""
        arr = price_series
        result = rolling_mean(arr, 5)
        # The value at index 4 must equal the mean of indices 0-4
        expected = float(np.mean(arr[:5]))
        assert abs(result[4] - expected) < 1e-9, (
            f"rolling_mean[4]={result[4]:.4f} != mean(arr[0:5])={expected:.4f}"
        )

    def test_rolling_mean_changes_when_we_drop_future(self, price_series):
        """Confirm rolling_mean on truncated series gives same result at shared horizon."""
        arr = price_series
        full = rolling_mean(arr, 10)
        trunc = rolling_mean(arr[:50], 10)
        # At index 20 (well within both series), values must match
        assert abs(full[20] - trunc[20]) < 1e-9, "Look-ahead detected in rolling_mean"

    def test_ema_is_right_aligned(self, price_series):
        """ema[i] must only use bars 0..i — changing future bars must not affect past."""
        arr = price_series.copy()
        result1 = ema(arr, 20)
        # Perturb future bars
        arr[80:] *= 2.0
        result2 = ema(arr, 20)
        # Past ema values (up to 79) must be identical
        assert np.allclose(result1[:60], result2[:60], atol=1e-9), (
            "ema is sensitive to future bars — look-ahead bias detected!"
        )

    def test_rolling_std_no_lookahead(self, price_series):
        arr = price_series
        full = rolling_std(arr, 20)
        trunc = rolling_std(arr[:40], 20)
        assert abs(full[35] - trunc[35]) < 1e-9, "Look-ahead in rolling_std"


# ── Rolling mean ──────────────────────────────────────────────────

class TestRollingMean:
    def test_constant_series(self):
        arr = np.full(50, 5.0)
        result = rolling_mean(arr, 10)
        assert np.allclose(result[9:], 5.0), "rolling_mean of constant must be constant"

    def test_window_1_is_identity(self, price_series):
        result = rolling_mean(price_series, 1)
        assert np.allclose(result, price_series)

    def test_no_nan_expanding_warmup(self, price_series):
        """rolling_mean uses expanding mean for early bars — no NaN prefix."""
        window = 20
        result = rolling_mean(price_series, window)
        assert not np.any(np.isnan(result)), "rolling_mean uses expanding warmup — no NaN expected"

    def test_full_window_correct(self, price_series):
        """Once full window is available, value equals simple mean of last window bars."""
        window = 5
        result = rolling_mean(price_series, window)
        expected = np.mean(price_series[:window])
        assert result[window - 1] == pytest.approx(expected, rel=1e-6)


# ── compute_indicators ────────────────────────────────────────────

class TestComputeIndicators:
    def test_returns_dict(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        assert isinstance(ind, dict)

    def test_required_keys_present(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        required = [
            "sma20", "sma50", "rsi14", "vol_ratio",
            "macd_line", "macd_signal", "macd_hist",
            "bb_upper", "bb_mid", "bb_lower", "bb_pct_b",
        ]
        for key in required:
            assert key in ind, f"Missing indicator key: {key}"

    def test_rsi_bounded_0_to_100(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        rsi = np.array(ind["rsi14"])
        valid = rsi[~np.isnan(rsi)]
        assert np.all(valid >= 0) and np.all(valid <= 100), (
            "RSI must be in [0, 100]"
        )

    def test_bb_band_ordering(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        upper = np.array(ind["bb_upper"])
        mid   = np.array(ind["bb_mid"])
        lower = np.array(ind["bb_lower"])
        valid = ~(np.isnan(upper) | np.isnan(mid) | np.isnan(lower))
        assert np.all(upper[valid] >= mid[valid]), "BB upper must >= mid"
        assert np.all(mid[valid]   >= lower[valid]), "BB mid must >= lower"

    def test_macd_hist_is_diff(self, price_series, volume_series):
        """macd_hist = macd_line - macd_signal."""
        ind = compute_indicators(price_series, volume_series)
        line   = np.array(ind["macd_line"])
        signal = np.array(ind["macd_signal"])
        hist   = np.array(ind["macd_hist"])
        valid  = ~(np.isnan(line) | np.isnan(signal) | np.isnan(hist))
        assert np.allclose(hist[valid], (line - signal)[valid], atol=1e-9)

    def test_vol_ratio_positive(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        vr = np.array(ind["vol_ratio"])
        valid = vr[~np.isnan(vr)]
        assert np.all(valid >= 0), "vol_ratio must be non-negative"


# ── Dual Thrust ───────────────────────────────────────────────────

class TestDualThrust:
    def test_upper_above_lower(self, ohlcv):
        high, low, close, open_, _ = ohlcv
        upper, lower = dual_thrust_levels(high, low, close, open_, k1=0.5, k2=0.5, lookback=5)
        valid = ~(np.isnan(upper) | np.isnan(lower))
        assert np.all(upper[valid] >= lower[valid]), (
            "Dual Thrust upper must be >= lower"
        )

    def test_output_length_matches_input(self, ohlcv):
        high, low, close, open_, _ = ohlcv
        upper, lower = dual_thrust_levels(high, low, close, open_, k1=0.5, k2=0.5, lookback=10)
        assert len(upper) == len(close)
        assert len(lower) == len(close)

    def test_nan_in_warmup(self, ohlcv):
        high, low, close, open_, _ = ohlcv
        lookback = 10
        upper, _ = dual_thrust_levels(high, low, close, open_, lookback=lookback)
        assert np.all(np.isnan(upper[:lookback - 1]))


# ── RS vs Benchmark ───────────────────────────────────────────────

class TestRsVsBenchmark:
    def _make_series(self, n=252, trend=0.001):
        np.random.seed(99)
        noise = np.random.normal(0, 0.01, n)
        return 100.0 * np.cumprod(1 + noise + trend)

    def test_returns_dict(self):
        stock = self._make_series(trend=0.003)
        bench = self._make_series(trend=0.001)
        result = compute_rs_vs_benchmark(stock, bench)
        assert isinstance(result, dict)

    def test_leader_when_outperforming(self):
        """Strongly outperforming stock → LEADER or STRONG status."""
        stock = self._make_series(trend=0.005)   # strong uptrend
        bench = self._make_series(trend=0.0001)  # flat benchmark
        result = compute_rs_vs_benchmark(stock, bench)
        assert result["rs_status"] in ("LEADER", "STRONG"), (
            f"Expected LEADER/STRONG for outperformer, got {result['rs_status']}"
        )

    def test_laggard_when_underperforming(self):
        """Strongly underperforming stock → LAGGARD or WEAK status."""
        stock = self._make_series(trend=-0.003)  # downtrend
        bench = self._make_series(trend=0.003)   # uptrend benchmark
        result = compute_rs_vs_benchmark(stock, bench)
        assert result["rs_status"] in ("LAGGARD", "WEAK"), (
            f"Expected LAGGARD/WEAK for underperformer, got {result['rs_status']}"
        )

    def test_rs_keys_present(self):
        stock = self._make_series()
        bench = self._make_series()
        result = compute_rs_vs_benchmark(stock, bench)
        for key in ("rs_1m", "rs_3m", "rs_6m", "rs_composite", "rs_status"):
            assert key in result, f"Missing RS key: {key}"


# ── Signal quality features ───────────────────────────────────────

class TestSignalQualityFeatures:
    def test_returns_dict(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        q = signal_quality_features(price_series, volume_series, ind)
        assert isinstance(q, dict)

    def test_rsi_regime_valid_values(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        q = signal_quality_features(price_series, volume_series, ind)
        valid = {"OVERSOLD", "NEUTRAL", "MOMENTUM", "OVERBOUGHT", "EXTREME_OVERSOLD"}
        assert q.get("rsi_regime") in valid, (
            f"Unexpected rsi_regime: {q.get('rsi_regime')}"
        )

    def test_macd_momentum_boolean(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        q = signal_quality_features(price_series, volume_series, ind)
        assert isinstance(q.get("macd_momentum"), bool)

    def test_bb_contracted_boolean(self, price_series, volume_series):
        ind = compute_indicators(price_series, volume_series)
        q = signal_quality_features(price_series, volume_series, ind)
        assert isinstance(q.get("bb_contracted"), bool)
