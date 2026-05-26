"""
Integration test for the full signal pipeline.

Tests: UniverseBuilder → FeatureEngine → SignalEngine → OpportunityEnsembler
with mock data. No broker, no GPT, no yfinance calls.

Run: python -m pytest tests/test_pipeline_integration.py -v
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import (
    Signal, Direction, Horizon, Invalidation, Target,
    StopType, MarketRegime, VolatilityRegime, TrendRegime, RiskRegime,
    TradeRecommendation,
)
from src.engines.signal_engine import (
    SignalEngine, UniverseFilter, ScoreUnifier, SignalDedup,
    SignalCooldown, RiskModel, RegimeDetector,
)
from src.engines.opportunity_ensembler import OpportunityEnsembler
from src.engines.regime_router import RegimeRouter, RegimeState
from src.scanners.universe_builder import UniverseBuilder


# ── Fixtures ──────────────────────────────────────────────────────


def _make_features_df(tickers: list, n_rows: int = 100) -> pd.DataFrame:
    """Build a synthetic features DataFrame for testing."""
    np.random.seed(42)
    rows = []
    for ticker in tickers:
        base_price = 100 + np.random.uniform(-20, 50)
        for i in range(n_rows):
            row = {
                "ticker": ticker,
                "close": base_price + np.random.randn() * 2,
                "high": base_price + abs(np.random.randn()) * 3,
                "low": base_price - abs(np.random.randn()) * 3,
                "volume": int(np.random.uniform(500_000, 5_000_000)),
                "volume_sma_20": int(np.random.uniform(500_000, 3_000_000)),
                "return_1d": np.random.uniform(-0.03, 0.03),
                "return_5d": np.random.uniform(-0.05, 0.08),
                "return_21d": np.random.uniform(-0.10, 0.15),
                "rsi_14": np.random.uniform(25, 75),
                "adx_14": np.random.uniform(10, 50),
                "atr_14": base_price * np.random.uniform(0.01, 0.04),
                "atr_pct": np.random.uniform(0.01, 0.04),
                "sma_20": base_price * (1 + np.random.uniform(-0.02, 0.02)),
                "sma_50": base_price * (1 + np.random.uniform(-0.05, 0.05)),
                "sma_200": base_price * (1 + np.random.uniform(-0.10, 0.10)),
                "dist_from_sma20": np.random.uniform(-0.05, 0.05),
                "dist_from_sma50": np.random.uniform(-0.10, 0.10),
                "dist_from_sma200": np.random.uniform(-0.15, 0.15),
                "relative_volume": np.random.uniform(0.5, 3.0),
                "bb_width": np.random.uniform(0.02, 0.10),
                "macd": np.random.uniform(-2, 2),
                "macd_signal": np.random.uniform(-2, 2),
                "macd_histogram": np.random.uniform(-1, 1),
                "momentum_score": np.random.uniform(30, 80),
                "trend_score": np.random.uniform(30, 80),
                "market_cap": np.random.uniform(1e9, 500e9),
                "dollar_volume_20d": np.random.uniform(10e6, 500e6),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def _make_market_data() -> dict:
    """Synthetic market state for testing."""
    return {
        "vix": 18.0,
        "spx_change_pct": 0.5,
        "pct_above_sma50": 55,
        "hy_spread": 350,
        "vix_term_structure": 1.02,
        "realized_vol_20d": 0.15,
        "data_fresh": True,
        "data_staleness_seconds": 60,
        "is_fomc_day": False,
        "is_quad_witching": False,
        "account_drawdown_pct": 0.0,
        "daily_pnl_pct": 0.0,
    }


def _make_regime() -> MarketRegime:
    """Synthetic regime for testing."""
    return MarketRegime(
        timestamp=datetime.now(timezone.utc),
        volatility=VolatilityRegime.NORMAL,
        trend=TrendRegime.UPTREND,
        risk=RiskRegime.RISK_ON,
        active_strategies=[
            "momentum_breakout", "trend_following", "vcp",
            "mean_reversion", "classic_swing",
        ],
        strategy_weights={
            "momentum_breakout": 0.9,
            "trend_following": 0.8,
            "vcp": 0.7,
            "mean_reversion": 0.6,
            "classic_swing": 0.7,
        },
    )


# ── Tests ─────────────────────────────────────────────────────────


class TestUniverseFilter:
    """Test the universe quality filter."""

    def test_filters_penny_stocks(self):
        uf = UniverseFilter()
        features = _make_features_df(["AAPL", "PENNY"])
        # Override PENNY to have low price
        mask = features["ticker"] == "PENNY"
        features.loc[mask, "close"] = 2.0
        features.loc[mask, "volume_sma_20"] = 1_000_000
        features.loc[mask, "market_cap"] = 1e9

        clean, rejections = uf.filter(["AAPL", "PENNY"], features)
        assert "PENNY" in rejections
        assert "AAPL" in clean

    def test_filters_low_volume(self):
        uf = UniverseFilter()
        features = _make_features_df(["AAPL", "THIN"])
        mask = features["ticker"] == "THIN"
        features.loc[mask, "volume_sma_20"] = 10_000  # below 200K threshold

        clean, rejections = uf.filter(["AAPL", "THIN"], features)
        assert "THIN" in rejections


class TestScoreUnifier:
    """Test score unification."""

    def test_unify_high_score(self):
        result = ScoreUnifier.unify(85)
        assert result["signal_score_0_100"] == 85
        assert result["confidence_bucket"] == "HIGH"
        assert result["ai_score_0_10"] == 8.5

    def test_unify_low_score(self):
        result = ScoreUnifier.unify(30)
        assert result["confidence_bucket"] == "LOW"

    def test_unify_clamps(self):
        result = ScoreUnifier.unify(150)
        assert result["signal_score_0_100"] == 100


class TestSignalDedup:
    """Test signal deduplication."""

    def test_resolves_direction_conflict(self):
        dedup = SignalDedup()
        sig_a = Signal(
            ticker="AAPL", direction=Direction.LONG, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=145, stop_type=StopType.HARD),
            targets=[Target(price=160, pct_position=100)],
            entry_logic="test", catalyst="test", key_risks=["test"],
            confidence=80, rationale="test", strategy_id="momentum_breakout",
        )
        sig_b = Signal(
            ticker="AAPL", direction=Direction.SHORT, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=155, stop_type=StopType.HARD),
            targets=[Target(price=140, pct_position=100)],
            entry_logic="test", catalyst="test", key_risks=["test"],
            confidence=60, rationale="test", strategy_id="mean_reversion",
        )
        kept, resolutions = dedup.resolve_conflicts([sig_a, sig_b])
        assert len(kept) == 1
        assert kept[0].confidence == 80  # higher confidence wins
        assert len(resolutions) == 1
        assert resolutions[0]["reason"] == "direction_conflict"


class TestSignalCooldown:
    """Test cross-cycle signal cooldown."""

    def test_allows_first_signal(self):
        cd = SignalCooldown(cooldown_hours=4, anti_flip_hours=6)
        allowed, reason = cd.is_allowed("AAPL", "LONG")
        assert allowed

    def test_blocks_same_direction_within_cooldown(self):
        cd = SignalCooldown(cooldown_hours=4, anti_flip_hours=6)
        cd.record("AAPL", "LONG")
        allowed, reason = cd.is_allowed("AAPL", "LONG")
        assert not allowed
        assert "cooldown" in reason

    def test_blocks_opposite_direction_within_anti_flip(self):
        cd = SignalCooldown(cooldown_hours=4, anti_flip_hours=6)
        cd.record("AAPL", "LONG")
        allowed, reason = cd.is_allowed("AAPL", "SHORT")
        assert not allowed
        assert "anti_flip" in reason


class TestRegimeRouter:
    """Test probabilistic regime classification."""

    def test_low_vix_bullish(self):
        router = RegimeRouter()
        state = router.classify({
            "vix": 14.0,
            "spy_return_20d": 0.05,
            "breadth_pct": 0.65,
            "hy_spread": 0.0,
            "realized_vol_20d": 0.12,
            "vix_term_slope": 0.0,
        })
        assert isinstance(state, RegimeState)
        assert state.risk_on_uptrend > state.risk_off_downtrend

    def test_high_vix_bearish(self):
        router = RegimeRouter()
        state = router.classify({
            "vix": 35.0,
            "spy_return_20d": -0.08,
            "breadth_pct": 0.25,
            "hy_spread": 5.0,
            "realized_vol_20d": 0.35,
            "vix_term_slope": 0.0,
        })
        assert state.risk_off_downtrend > state.risk_on_uptrend
        assert not state.should_trade  # VIX crisis

    def test_entropy_bounded(self):
        router = RegimeRouter()
        state = router.classify({
            "vix": 20.0,
            "spy_return_20d": 0.0,
            "breadth_pct": 0.50,
            "hy_spread": 3.5,
            "realized_vol_20d": 0.15,
            "vix_term_slope": 0.0,
        })
        assert 0 <= state.entropy <= 1.2  # ln(3) ≈ 1.10


class TestOpportunityEnsembler:
    """Test ensemble scoring and suppression."""

    def test_scores_recommendation(self):
        ensembler = OpportunityEnsembler()
        rec = TradeRecommendation(
            ticker="AAPL",
            direction="LONG",
            strategy_id="momentum_breakout",
            signal_confidence=75,
            score=0.75,
            entry_price=150.0,
            stop_price=145.0,
            risk_reward_ratio=2.0,
            expected_return=0.05,
            edge_p_t1=0.60,
            edge_ev=0.03,
        )
        regime = {
            "risk_on_uptrend": 0.6,
            "neutral_range": 0.3,
            "risk_off_downtrend": 0.1,
            "entropy": 0.5,
            "should_trade": True,
        }
        scored = ensembler.rank_opportunities([rec], regime)
        assert len(scored) == 1
        assert scored[0].composite_score > 0
        assert "pwin" in scored[0].components

    def test_suppresses_when_no_trade(self):
        ensembler = OpportunityEnsembler()
        rec = TradeRecommendation(
            ticker="AAPL", direction="LONG", strategy_id="momentum",
            signal_confidence=80, score=0.80,
        )
        regime = {"should_trade": False, "no_trade_reason": "VIX crisis"}
        scored = ensembler.rank_opportunities([rec], regime)
        assert not scored[0].trade_decision
        assert scored[0].suppression_reason == "regime_no_trade"

    def test_type_safe_suppression(self):
        """Verify _apply_suppression works with TradeRecommendation objects."""
        ensembler = OpportunityEnsembler()
        rec = TradeRecommendation(
            ticker="AAPL", direction="LONG", strategy_id="momentum",
            signal_confidence=80, score=0.80,
            composite_score=0.20,  # below min_score
            components={"pwin": 0.6, "risk_reward": 0.3},
            penalties={},
        )
        regime = {"should_trade": True, "entropy": 0.5}
        result = ensembler._apply_suppression([rec], regime)
        assert not result[0].trade_decision
        assert "below" in result[0].why_not_trade


class TestRiskModel:
    """Test risk filtering and position sizing."""

    def test_filters_below_min_confidence(self):
        rm = RiskModel()
        sig = Signal(
            ticker="AAPL", direction=Direction.LONG, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=145, stop_type=StopType.HARD),
            targets=[Target(price=160, pct_position=100)],
            entry_logic="test", catalyst="test", key_risks=["test"],
            confidence=30, rationale="test",
        )
        result = rm.filter_and_size([sig])
        assert len(result) == 0  # below min_confidence (50)

    def test_deduplicates_tickers(self):
        rm = RiskModel()
        sig_a = Signal(
            ticker="AAPL", direction=Direction.LONG, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=145, stop_type=StopType.HARD),
            targets=[Target(price=160, pct_position=100)],
            entry_logic="test", catalyst="test", key_risks=["test"],
            confidence=80, rationale="test", strategy_id="momentum",
        )
        sig_b = Signal(
            ticker="AAPL", direction=Direction.LONG, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=145, stop_type=StopType.HARD),
            targets=[Target(price=160, pct_position=100)],
            entry_logic="test", catalyst="test", key_risks=["test"],
            confidence=70, rationale="test", strategy_id="mean_reversion",
        )
        result = rm.filter_and_size([sig_a, sig_b])
        assert len(result) == 1  # deduplicated


class TestFullPipeline:
    """End-to-end pipeline test with mock strategies."""

    def test_generate_signals_returns_list(self):
        """Test that SignalEngine produces signals from synthetic data."""
        features = _make_features_df(["AAPL", "MSFT", "GOOGL"])
        market_data = _make_market_data()
        regime = _make_regime()

        # Mock the regime detector to return our regime
        with patch.object(RegimeDetector, "detect", return_value=regime):
            engine = SignalEngine()
            signals = engine.generate_signals(
                universe=["AAPL", "MSFT", "GOOGL"],
                features=features,
                market_data=market_data,
            )

        # Should return a list (may be empty if no strategies fire)
        assert isinstance(signals, list)

    def test_pipeline_produces_trade_recommendations(self):
        """Test Signal → TradeRecommendation conversion."""
        sig = Signal(
            ticker="AAPL", direction=Direction.LONG, horizon=Horizon.SWING_1_5D,
            entry_price=150, invalidation=Invalidation(stop_price=145, stop_type=StopType.HARD),
            targets=[Target(price=160, pct_position=100)],
            entry_logic="Breakout above resistance", catalyst="Earnings beat",
            key_risks=["Market pullback"], confidence=75,
            rationale="Strong momentum with volume confirmation",
            strategy_id="momentum_breakout",
        )
        rec = TradeRecommendation.from_signal(sig, regime_state={"regime": "RISK_ON", "vix": 18})
        assert rec.ticker == "AAPL"
        assert rec.direction == "LONG"
        assert rec.signal_confidence == 75
        assert rec.entry_price == 150.0
        assert rec.stop_price == 145.0

    def test_ensembler_ranks_multiple_signals(self):
        """Test that ensembler correctly ranks multiple signals."""
        ensembler = OpportunityEnsembler()
        recs = [
            TradeRecommendation(
                ticker="AAPL", direction="LONG", strategy_id="momentum",
                signal_confidence=80, score=0.80, edge_p_t1=0.65,
                risk_reward_ratio=2.5, edge_ev=0.04,
            ),
            TradeRecommendation(
                ticker="MSFT", direction="LONG", strategy_id="mean_reversion",
                signal_confidence=60, score=0.60, edge_p_t1=0.55,
                risk_reward_ratio=1.8, edge_ev=0.02,
            ),
        ]
        regime = {
            "risk_on_uptrend": 0.6, "neutral_range": 0.3,
            "risk_off_downtrend": 0.1, "entropy": 0.5, "should_trade": True,
        }
        ranked = ensembler.rank_opportunities(recs, regime)
        assert len(ranked) == 2
        # Higher confidence should rank higher
        assert ranked[0].composite_score >= ranked[1].composite_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
