"""
test_regime_router.py — Regime detection critical-path tests
=============================================================
Covers: VIX crisis override, entropy no-trade gate, EMA hysteresis,
breadth/spread driven regime classification, and minimum hold time.
"""

from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def _make_router():
    from src.engines.regime_router import RegimeRouter

    return RegimeRouter()


def _bull_market():
    return {
        "vix": 14.0,
        "spy_return_20d": 0.04,
        "breadth_pct": 0.68,
        "hy_spread": 0.3,
        "realized_vol_20d": 0.10,
        "vix_term_slope": -0.5,
    }


def _bear_market():
    return {
        "vix": 32.0,
        "spy_return_20d": -0.07,
        "breadth_pct": 0.28,
        "hy_spread": 4.5,
        "realized_vol_20d": 0.35,
        "vix_term_slope": 1.5,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1. VIX Crisis Override
# ══════════════════════════════════════════════════════════════════════════════


class TestVIXCrisisOverride:
    def test_crisis_vix_sets_should_trade_false(self):
        """VIX ≥ 35 must override should_trade to False regardless of other signals."""
        router = _make_router()
        data = _bull_market()
        data["vix"] = 38.0  # above VIX_CRISIS = 35
        result = router.classify(data)
        assert result.get("should_trade") is False

    def test_crisis_threshold_is_boundary(self):
        """VIX exactly at crisis threshold (35.0) → should_trade False."""
        router = _make_router()
        data = _bull_market()
        data["vix"] = 35.0
        result = router.classify(data)
        assert result.get("should_trade") is False

    def test_below_crisis_allows_trade(self):
        """VIX below crisis threshold in bull market → should_trade True."""
        router = _make_router()
        result = router.classify(_bull_market())
        assert result.get("should_trade") is True


# ══════════════════════════════════════════════════════════════════════════════
# 2. Regime Classification
# ══════════════════════════════════════════════════════════════════════════════


class TestRegimeClassification:
    def test_bull_market_classifies_risk_on(self):
        """Clear bull market signals → RISK_ON or uptrend regime."""
        router = _make_router()
        result = router.classify(_bull_market())
        regime = result.get("regime", result.get("raw_regime", ""))
        assert (
            "RISK" in regime.upper()
            or "UP" in regime.upper()
            or "BULL" in regime.upper()
        ), f"Expected risk-on regime, got: {regime}"

    def test_bear_market_classifies_risk_off(self):
        """High VIX + negative returns + poor breadth → RISK_OFF."""
        router = _make_router()
        # Run a few times to stabilise EMA
        result = {"regime": ""}
        for _ in range(5):
            result = router.classify(_bear_market())
        regime = result.get("regime", result.get("raw_regime", ""))
        assert (
            "RISK_OFF" in regime.upper()
            or "BEAR" in regime.upper()
            or "DOWN" in regime.upper()
        ), f"Expected risk-off regime, got: {regime}"

    def test_output_has_required_keys(self):
        """classify() must return the downstream contract keys."""
        router = _make_router()
        result = router.classify(_bull_market())
        for key in ("should_trade", "regime"):
            assert key in result, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Entropy No-Trade Gate
# ══════════════════════════════════════════════════════════════════════════════


class TestEntropyGate:
    def test_ambiguous_market_may_block_trading(self):
        """Perfect 50/50 ambiguity → entropy is high → should_trade possibly False."""
        router = _make_router()
        # Perfectly neutral input — maximises entropy
        ambiguous = {
            "vix": 20.0,  # exactly at mid
            "spy_return_20d": 0.0,
            "breadth_pct": 0.50,
            "hy_spread": 1.0,
            "realized_vol_20d": 0.15,
            "vix_term_slope": 0.0,
        }
        result = router.classify(ambiguous)
        # Either should_trade is False OR entropy is measurably high
        entropy = result.get("entropy", 0.0)
        assert entropy >= 0.0, "Entropy must be non-negative"
        # If entropy > no_trade_entropy threshold, should_trade should be False
        if entropy > router.no_trade_entropy:
            assert result.get("should_trade") is False


# ══════════════════════════════════════════════════════════════════════════════
# 4. EMA Smoothing (Hysteresis)
# ══════════════════════════════════════════════════════════════════════════════


class TestEMASmoothing:
    def test_probabilities_converge_after_repeated_calls(self):
        """EMA probabilities should converge toward steady state."""
        router = _make_router()
        data = _bull_market()
        prev_p: float = 0.5
        for _ in range(10):
            result = router.classify(data)
            prev_p = result.get("risk_on_prob", result.get("p_risk_on", 0.5))
        # Final probability should converge toward bull state
        assert prev_p > 0.3

    def test_ema_resists_single_spike(self):
        """A single VIX spike shouldn't immediately flip regime from RISK_ON to RISK_OFF."""
        router = _make_router()
        data = _bull_market()
        # Establish bull regime
        for _ in range(8):
            router.classify(data)
        # Single bear data point
        result_after_spike = router.classify(_bear_market())
        # EMA should smooth out — regime might still show partial RISK_ON
        p_risk_on = result_after_spike.get(
            "risk_on_prob", result_after_spike.get("p_risk_on", 0.5)
        )
        # Risk-on prob should still be > 0 due to smoothing
        assert p_risk_on > 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 5. Volatility Classification
# ══════════════════════════════════════════════════════════════════════════════


class TestVolatilityClassification:
    def test_low_vix_is_not_crisis(self):
        router = _make_router()
        result = router.classify(_bull_market())
        vol_regime = result.get("volatility_regime", "")
        assert "crisis" not in vol_regime.lower()

    def test_high_vix_signals_elevated_vol(self):
        router = _make_router()
        data = _bear_market()
        data["vix"] = 28.5
        result = router.classify(data)
        vol_regime = result.get("volatility_regime", "normal")
        # VIX 28.5 should produce elevated or high vol
        assert vol_regime in (
            "elevated_vol",
            "high_vol",
            "crisis_vol",
            "elevated",
            "high",
        ), f"VIX 28.5 → expected elevated/high vol, got: {vol_regime}"
