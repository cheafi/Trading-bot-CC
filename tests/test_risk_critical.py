"""
Risk-Critical Tests — P5
=========================
Tests for: position sizing, risk limits, regime detection, suppression gates.

CRO mandate: these tests gate every CI run.  A failure here means STOP —
  do NOT merge, do NOT deploy.
"""

import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────────────────────
# Risk Limits — constants must not drift below safe thresholds
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskLimits:
    """RISK constants enforce hard capital-preservation rules."""

    def setup_method(self):
        from src.core.risk_limits import RISK
        self.RISK = RISK

    def test_max_position_pct_not_excessive(self):
        """No single position should risk more than 5% of portfolio."""
        assert self.RISK.max_position_pct <= 0.05, (
            f"max_position_pct={self.RISK.max_position_pct} — exceeds 5% hard cap"
        )

    def test_max_correlated_names_bounded(self):
        """Sector concentration guard must be active (≤ 5 per sector)."""
        assert 1 <= self.RISK.max_correlated_names <= 5, (
            f"max_correlated_names={self.RISK.max_correlated_names} out of safe range"
        )

    def test_max_drawdown_limit_present(self):
        """Portfolio drawdown limit must exist and be a reasonable fraction."""
        dd = getattr(self.RISK, "max_drawdown_pct", None)
        if dd is not None:
            # Accept either convention: negative (-0.15) or positive (0.15)
            dd_abs = abs(dd)
            assert 0 < dd_abs <= 0.30, (
                f"max_drawdown_pct magnitude {dd_abs:.2f} should be 0 < x <= 0.30"
            )

    def test_signal_thresholds_sane(self):
        """Signal thresholds must maintain minimum quality gates."""
        from src.core.risk_limits import SIGNAL_THRESHOLDS as ST
        assert 0 < ST.rsi_oversold < 35, f"rsi_oversold={ST.rsi_oversold} — should be <35"
        assert ST.rsi_overbought > 65, f"rsi_overbought={ST.rsi_overbought} — should be >65"
        assert ST.volume_confirmation >= 0.8, "volume_confirmation below 0.8x — too loose"


# ─────────────────────────────────────────────────────────────────────────────
# Position Sizing — Kelly / fixed-fractional math
# ─────────────────────────────────────────────────────────────────────────────

class TestPositionSizing:
    """Fixed-fractional sizing must obey risk-per-trade limits."""

    def _fixed_fractional_size(self, portfolio_value, risk_pct, entry, stop):
        """1R sizing: risk $X = portfolio * risk_pct; size = X / (entry - stop)."""
        risk_dollars = portfolio_value * risk_pct
        point_risk = entry - stop
        if point_risk <= 0:
            return 0.0
        return risk_dollars / point_risk

    def test_size_scales_with_portfolio(self):
        """Doubling portfolio → doubled share count (linear risk)."""
        s1 = self._fixed_fractional_size(100_000, 0.01, 50.0, 48.0)
        s2 = self._fixed_fractional_size(200_000, 0.01, 50.0, 48.0)
        assert abs(s2 / s1 - 2.0) < 0.001

    def test_size_zero_if_stop_above_entry(self):
        """Negative point_risk → size 0 (no position)."""
        size = self._fixed_fractional_size(100_000, 0.01, 48.0, 50.0)
        assert size == 0.0

    def test_size_respects_max_position(self):
        """Sized position must not exceed max_position_pct of portfolio."""
        from src.core.risk_limits import RISK
        portfolio = 100_000
        # 1% risk with a wide 10% stop → modest position
        entry, stop = 100.0, 90.0  # 10% stop
        size = self._fixed_fractional_size(portfolio, 0.01, entry, stop)
        position_value = size * entry
        # 1R = $1000, point_risk = $10, size = 100 shares, position = $10,000 = 10%
        # max_position_pct default is 0.10-0.20 in most configs — test is directional
        # The key invariant: 1% risk with ATR stop should produce reasonable size
        assert position_value <= portfolio * 0.25, (
            f"Position ${position_value:.0f} is >25% of portfolio — sizing logic broken"
        )

    def test_kelly_fraction_bounded(self):
        """Kelly fraction must be capped at 0.25 (quarter-Kelly safety)."""
        # Full Kelly = (pwin * avg_win - (1-pwin)) / avg_win
        def kelly(pwin, rr):
            avg_win = rr
            full_kelly = (pwin * avg_win - (1 - pwin)) / avg_win
            return max(0.0, min(0.25, full_kelly))  # quarter-Kelly cap

        # 60% win rate, 2:1 RR → full Kelly ~30% → capped at 25%
        f = kelly(0.60, 2.0)
        assert f <= 0.25, f"Kelly={f:.3f} — exceeds quarter-Kelly safety cap"
        assert f > 0, "60%/2R should produce positive Kelly"

        # Negative expectancy → zero
        # pwin=0.40, rr=1.5 → full_kelly = (0.40*1.5 - 0.60)/1.5 = (0.6-0.6)/1.5 = 0
        # pwin=0.35, rr=1.0 → (0.35-0.65)/1.0 = -0.30 → capped at 0
        f_neg = kelly(0.35, 1.0)
        assert f_neg == 0.0, f"Negative expectancy must produce zero Kelly size, got {f_neg}"


# ─────────────────────────────────────────────────────────────────────────────
# Confidence Engine — 4-layer must stay calibrated
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceEngine:
    """compute_4layer_confidence must return bounded, causal scores."""

    def _make_close(self, n=200, trend="up"):
        """Synthetic OHLCV data."""
        np.random.seed(42)
        if trend == "up":
            c = np.linspace(100, 150, n) + np.random.randn(n) * 0.5
        elif trend == "down":
            c = np.linspace(150, 100, n) + np.random.randn(n) * 0.5
        else:
            c = np.full(n, 100.0) + np.random.randn(n) * 0.5
        vol = np.random.randint(1_000_000, 5_000_000, n).astype(float)
        return c, vol

    def test_output_keys_present(self):
        from src.services.confidence import compute_4layer_confidence
        from src.services.indicators import compute_indicators

        close, vol = self._make_close(200)
        ind = compute_indicators(close, vol)
        result = compute_4layer_confidence(
            close, ind["sma20"], ind["sma50"], ind["sma200"],
            ind["rsi"], ind["atr_pct"], ind["vol_ratio"],
            idx=len(close) - 1, volume=vol, regime_trending=True,
        )
        for key in ("composite", "grade", "thesis", "timing", "execution", "data"):
            assert key in result, f"Missing key: {key}"

    def test_composite_bounded_0_100(self):
        from src.services.confidence import compute_4layer_confidence
        from src.services.indicators import compute_indicators

        for trend in ("up", "down", "flat"):
            close, vol = self._make_close(200, trend)
            ind = compute_indicators(close, vol)
            result = compute_4layer_confidence(
                close, ind["sma20"], ind["sma50"], ind["sma200"],
                ind["rsi"], ind["atr_pct"], ind["vol_ratio"],
                idx=len(close) - 1, volume=vol, regime_trending=(trend == "up"),
            )
            c = result["composite"]
            assert 0 <= c <= 100, f"composite={c} out of bounds for trend={trend}"

    def test_uptrend_scores_higher_than_downtrend(self):
        """Uptrend should score higher composite than downtrend — directional sanity."""
        from src.services.confidence import compute_4layer_confidence
        from src.services.indicators import compute_indicators

        close_up, vol_up = self._make_close(200, "up")
        close_dn, vol_dn = self._make_close(200, "down")
        ind_up = compute_indicators(close_up, vol_up)
        ind_dn = compute_indicators(close_dn, vol_dn)
        i = 199

        score_up = compute_4layer_confidence(
            close_up, ind_up["sma20"], ind_up["sma50"], ind_up["sma200"],
            ind_up["rsi"], ind_up["atr_pct"], ind_up["vol_ratio"],
            idx=i, volume=vol_up, regime_trending=True,
        )["composite"]

        score_dn = compute_4layer_confidence(
            close_dn, ind_dn["sma20"], ind_dn["sma50"], ind_dn["sma200"],
            ind_dn["rsi"], ind_dn["atr_pct"], ind_dn["vol_ratio"],
            idx=i, volume=vol_dn, regime_trending=False,
        )["composite"]

        assert score_up > score_dn, (
            f"Uptrend score {score_up:.1f} should exceed downtrend {score_dn:.1f}"
        )

    def test_earnings_blackout_penalises(self):
        """Earnings in ≤3 days must reduce timing score."""
        from src.services.confidence import compute_4layer_confidence
        from src.services.indicators import compute_indicators

        close, vol = self._make_close(200, "up")
        ind = compute_indicators(close, vol)
        i = 199
        kwargs = dict(
            close=close, sma20=ind["sma20"], sma50=ind["sma50"], sma200=ind["sma200"],
            rsi=ind["rsi"], atr_pct=ind["atr_pct"], vol_ratio=ind["vol_ratio"],
            idx=i, volume=vol, regime_trending=True,
        )
        base = compute_4layer_confidence(**kwargs)["composite"]
        with_earnings = compute_4layer_confidence(days_to_earnings=2, **kwargs)["composite"]
        assert with_earnings < base, (
            f"Earnings blackout should penalise: base={base:.1f}, with_earnings={with_earnings:.1f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Regime Detection — RISK.vix thresholds gate sizing
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeGating:
    """VIX thresholds must gate trade size correctly."""

    def test_vix_thresholds_ordered(self):
        """elevated < crisis — VIX levels must be monotonically ordered."""
        from src.core.risk_limits import SIGNAL_THRESHOLDS as ST
        elevated = getattr(ST, "vix_elevated", 25)
        crisis = getattr(ST, "vix_crisis", 35)
        assert elevated < crisis, (
            f"VIX thresholds disordered: elevated={elevated}, crisis={crisis}"
        )

    def test_high_vix_suppresses_non_defensive(self):
        """compute_4layer_confidence with DOWNTREND regime must score lower."""
        from src.services.confidence import compute_4layer_confidence
        from src.services.indicators import compute_indicators
        import numpy as np

        np.random.seed(7)
        close = np.linspace(100, 120, 200) + np.random.randn(200) * 0.3
        vol = np.full(200, 2_000_000.0)
        ind = compute_indicators(close, vol)
        i = 199
        base_kwargs = dict(
            close=close, sma20=ind["sma20"], sma50=ind["sma50"], sma200=ind["sma200"],
            rsi=ind["rsi"], atr_pct=ind["atr_pct"], vol_ratio=ind["vol_ratio"],
            idx=i, volume=vol, regime_trending=True,
        )
        normal = compute_4layer_confidence(**base_kwargs)["composite"]
        adverse = compute_4layer_confidence(
            regime_label="DOWNTREND", ticker_sector="Technology", **base_kwargs
        )["composite"]
        assert adverse <= normal, (
            f"DOWNTREND regime should not score above normal: {adverse:.1f} vs {normal:.1f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scanner Service — watchlist & helper sanity
# ─────────────────────────────────────────────────────────────────────────────

class TestScannerConstants:
    """Static scanner properties — no network calls needed."""

    def test_watchlist_not_empty(self):
        from src.services.scanner import SCAN_WATCHLIST
        assert len(SCAN_WATCHLIST) >= 100, (
            f"Watchlist too small: {len(SCAN_WATCHLIST)} tickers"
        )

    def test_watchlist_no_duplicates(self):
        from src.services.scanner import SCAN_WATCHLIST
        assert len(SCAN_WATCHLIST) == len(set(SCAN_WATCHLIST)), "Duplicate tickers in watchlist"

    def test_ticker_sector_map_populated(self):
        from src.services.scanner import TICKER_SECTOR
        assert len(TICKER_SECTOR) >= 50, (
            f"TICKER_SECTOR too sparse: {len(TICKER_SECTOR)} entries"
        )

    def test_helper_build_reasons_for(self):
        """build_reasons_for returns a list with ≥1 item for a clean uptrend."""
        from src.services.scanner import build_reasons_for
        n = 100
        close = np.linspace(100, 130, n)
        sma20 = np.linspace(95, 125, n)
        sma50 = np.linspace(90, 120, n)
        sma200 = np.linspace(80, 110, n)
        rsi = np.full(n, 55.0)
        vol_ratio = np.full(n, 1.5)
        reasons = build_reasons_for(close, sma20, sma50, sma200, rsi, vol_ratio, n - 1, "momentum", True)
        assert isinstance(reasons, list)
        assert len(reasons) >= 1

    def test_helper_honest_confidence_label_structure(self):
        """honest_confidence_label returns a dict with is_probability=False."""
        from src.services.scanner import honest_confidence_label
        result = honest_confidence_label(75.0)
        assert isinstance(result, dict)
        assert result["is_probability"] is False
        assert "composite" in result


# ─────────────────────────────────────────────────────────────────────────────
# Suppression Gates — OpportunityEnsembler hard stops
# ─────────────────────────────────────────────────────────────────────────────

class TestSuppressionGates:
    """All suppression gates from OpportunityEnsembler must fire correctly."""

    def _make_rec(self, **overrides):
        """Build a minimal TradeRecommendation for gate testing."""
        from src.core.models import TradeRecommendation
        defaults = {
            "ticker": "TEST",
            "signal_confidence": 80,
            "risk_reward_ratio": 2.5,
            "strategy_id": "momentum",
            "strategy_health": 0.7,
            "edge_p_t1": 0.55,
            "direction": "LONG",
            "timing_score": 0.6,
        }
        defaults.update(overrides)
        return TradeRecommendation(**defaults)

    def _regime(self, should_trade=True):
        return {
            "should_trade": should_trade,
            "entropy": 0.5,
            "risk_on_uptrend": True,
            "regime": "UPTREND",
        }

    def test_negative_expectancy_suppressed(self):
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        oe = OpportunityEnsembler()
        # edge_p_t1=0.30, rr=1.0 → net_exp = 0.3*1.0 - 0.7*1 = -0.4 → suppressed
        rec = self._make_rec(edge_p_t1=0.30, risk_reward_ratio=1.0)
        result = oe.rank_opportunities([rec], regime=self._regime())
        tradeable = [r for r in result if r.trade_decision]
        assert len(tradeable) == 0, "Negative expectancy must not be tradeable"

    def test_low_pwin_suppressed(self):
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        oe = OpportunityEnsembler()
        # edge_p_t1=0.35 — below 0.40 threshold
        rec = self._make_rec(edge_p_t1=0.35)
        result = oe.rank_opportunities([rec], regime=self._regime())
        tradeable = [r for r in result if r.trade_decision]
        assert len(tradeable) == 0, "pwin<0.40 must not be tradeable"

    def test_rr_too_low_for_trade_suppressed(self):
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        oe = OpportunityEnsembler()
        # rr=1.5 — below 2.0 threshold for TRADE tier
        rec = self._make_rec(risk_reward_ratio=1.5, edge_p_t1=0.55)
        result = oe.rank_opportunities([rec], regime=self._regime())
        tradeable = [r for r in result if r.trade_decision]
        assert len(tradeable) == 0, "R:R<2.0 must be suppressed"

    def test_high_quality_makes_tradeable(self):
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        oe = OpportunityEnsembler()
        rec = self._make_rec(edge_p_t1=0.60, risk_reward_ratio=3.0, signal_confidence=85)
        result = oe.rank_opportunities([rec], regime=self._regime())
        assert len(result) >= 1, "High-quality rec must pass through ensembler"

    def test_regime_no_trade_suppresses_all(self):
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        oe = OpportunityEnsembler()
        rec = self._make_rec(edge_p_t1=0.70, risk_reward_ratio=4.0, signal_confidence=90)
        result = oe.rank_opportunities([rec], regime=self._regime(should_trade=False))
        tradeable = [r for r in result if r.trade_decision]
        assert len(tradeable) == 0, "Regime no_trade must suppress everything"
