"""
Tests for the new intelligence engines:
  - BenchmarkPortfolioEngine
  - SymbolComparisonEngine
  - RejectionAnalysisEngine
  - SelfLearningEngine

Run: python -m pytest tests/test_intelligence_engines.py -v
"""
import numpy as np
import pytest

from src.engines.benchmark_portfolio import (
    BenchmarkPortfolioEngine,
    PositionSnapshot,
    BenchmarkAttribution,
)
from src.engines.symbol_comparison import (
    SymbolComparisonEngine,
    ComparisonResult,
)
from src.engines.rejection_analysis import (
    RejectionAnalysisEngine,
    RejectionRecord,
    ConfidenceDisagreement,
)
from src.engines.self_learning import (
    SelfLearningEngine,
    RuleAdjustment,
    TUNABLE_RULES,
)


# ── Fixtures ──────────────────────────────────────────────────────


def _make_returns(n: int = 252, seed: int = 42) -> np.ndarray:
    """Generate synthetic daily returns (%)."""
    rng = np.random.RandomState(seed)
    return rng.normal(0.05, 1.5, n)  # ~12% annualized, ~24% vol


# ── BenchmarkPortfolioEngine Tests ────────────────────────────────


class TestBenchmarkPortfolioEngine:
    def test_empty_positions(self):
        engine = BenchmarkPortfolioEngine()
        result = engine.compute_attribution([], 3.0)
        assert result.portfolio_return == 0.0
        assert result.benchmark_return == 3.0

    def test_single_position_attribution(self):
        engine = BenchmarkPortfolioEngine()
        positions = [PositionSnapshot("AAPL", 1.0, 5.0, "Technology", 1.2)]
        result = engine.compute_attribution(positions, 3.0)
        assert result.portfolio_return == 5.0
        assert result.active_return == 2.0
        assert "Technology" in result.sector_contributions

    def test_sector_contributions(self):
        engine = BenchmarkPortfolioEngine()
        positions = [
            PositionSnapshot("AAPL", 0.6, 5.0, "Technology"),
            PositionSnapshot("JNJ", 0.4, 2.0, "Healthcare"),
        ]
        result = engine.compute_attribution(positions, 3.0)
        assert "Technology" in result.sector_contributions
        assert "Healthcare" in result.sector_contributions
        assert abs(result.portfolio_return - 4.2) < 0.01

    def test_factor_exposures(self):
        engine = BenchmarkPortfolioEngine()
        positions = [PositionSnapshot("NVDA", 1.0, 10.0, "Technology", 1.5)]
        result = engine.compute_attribution(positions, 3.0)
        assert "momentum" in result.factor_exposures
        assert "growth" in result.factor_exposures
        assert result.factor_exposures["growth"] > 0  # tech = high growth

    def test_sharpe_ratio(self):
        engine = BenchmarkPortfolioEngine()
        port_returns = _make_returns(100, seed=1)
        bench_returns = _make_returns(100, seed=2)
        positions = [PositionSnapshot("AAPL", 1.0, 5.0, "Technology")]
        result = engine.compute_attribution(
            positions, 3.0,
            benchmark_returns_series=bench_returns.tolist(),
            portfolio_returns_series=port_returns.tolist(),
        )
        assert isinstance(result.portfolio_sharpe, float)
        assert isinstance(result.beta, float)

    def test_to_dict(self):
        engine = BenchmarkPortfolioEngine()
        result = engine.compute_attribution([], 0.0)
        d = result.to_dict()
        assert "portfolio_return" in d
        assert "sector_contributions" in d
        assert "factor_exposures" in d


# ── SymbolComparisonEngine Tests ──────────────────────────────────


class TestSymbolComparisonEngine:
    def test_outperforming_stock(self):
        engine = SymbolComparisonEngine()
        ticker = _make_returns(100, seed=1) + 0.1  # slight outperformance
        benchmark = _make_returns(100, seed=2)
        result = engine.compare_vs_benchmark(ticker, benchmark, "AAPL", "SPY", "index")
        assert result.rs_composite > 100  # outperforming
        assert result.verdict in ("LEADER", "STRONG")

    def test_underperforming_stock(self):
        engine = SymbolComparisonEngine()
        ticker = _make_returns(100, seed=1) - 0.3  # underperformance
        benchmark = _make_returns(100, seed=2)
        result = engine.compare_vs_benchmark(ticker, benchmark, "AAPL", "SPY", "index")
        assert result.rs_composite < 100
        assert result.verdict in ("WEAK", "LAGGARD")

    def test_peer_comparison(self):
        engine = SymbolComparisonEngine()
        ticker_returns = _make_returns(100, seed=1)
        peer_returns = {
            "MSFT": _make_returns(100, seed=2),
            "GOOGL": _make_returns(100, seed=3),
        }
        result = engine.compare_vs_peers(ticker_returns, peer_returns, "AAPL")
        assert result.momentum_rank > 0
        assert 0 <= result.momentum_percentile <= 100

    def test_insufficient_data(self):
        engine = SymbolComparisonEngine()
        result = engine.compare_vs_benchmark(
            np.array([0.1, 0.2]), np.array([0.1, 0.2]), "X", "Y", "index"
        )
        assert result.verdict == "NEUTRAL"
        assert "Insufficient" in result.summary

    def test_to_dict(self):
        engine = SymbolComparisonEngine()
        result = engine.compare_vs_benchmark(
            _make_returns(50), _make_returns(50), "A", "B", "index"
        )
        d = result.to_dict()
        assert "rs_composite" in d
        assert "verdict" in d


# ── RejectionAnalysisEngine Tests ─────────────────────────────────


class TestRejectionAnalysisEngine:
    def test_empty_analysis(self):
        engine = RejectionAnalysisEngine()
        result = engine.analyze()
        assert result.total_rejections == 0
        assert len(result.rule_recommendations) > 0

    def test_categorization(self):
        engine = RejectionAnalysisEngine()
        engine.record_rejection(RejectionRecord(
            "AAPL", "momentum", "LONG", 72,
            rejection_reasons=["timing: extended, overbought"],
        ))
        engine.record_rejection(RejectionRecord(
            "TSLA", "breakout", "LONG", 65,
            rejection_reasons=["earnings in 1 day"],
        ))
        result = engine.analyze()
        assert result.total_rejections == 2
        assert "timing" in result.rejection_categories
        assert "earnings" in result.rejection_categories

    def test_false_negative_detection(self):
        engine = RejectionAnalysisEngine()
        engine.record_rejection(RejectionRecord(
            "AAPL", "momentum", "LONG", 72,
            rejection_reasons=["weak setup"],
            actual_return_5d=5.0,
            was_false_negative=True,
        ))
        result = engine.analyze()
        assert result.false_negative_rate == 100.0
        assert result.false_negative_cost == 5.0

    def test_confidence_disagreement(self):
        engine = RejectionAnalysisEngine()
        engine.record_disagreement(ConfidenceDisagreement(
            "AAPL", 85, 62, explanation="strategy overconfident"
        ))
        result = engine.analyze()
        assert len(result.confidence_disagreements) == 1

    def test_high_fn_rate_recommendation(self):
        engine = RejectionAnalysisEngine()
        for i in range(15):
            engine.record_rejection(RejectionRecord(
                f"T{i}", "momentum", "LONG", 70,
                rejection_reasons=["weak"],
                was_false_negative=True,
                actual_return_5d=3.0,
            ))
        result = engine.analyze()
        assert any("FALSE NEGATIVE" in r for r in result.rule_recommendations)


# ── SelfLearningEngine Tests ──────────────────────────────────────


class TestSelfLearningEngine:
    def test_insufficient_data(self):
        engine = SelfLearningEngine()
        outcomes = [{"pnl_pct": 1.0, "exit_reason": "target_hit"}] * 10
        rules = {"stop_loss_pct": 0.03}
        recs = engine.analyze_and_recommend(outcomes, rules)
        assert len(recs) == 0  # below min_sample_size

    def test_premature_stop_adjustment(self):
        engine = SelfLearningEngine()
        engine.state.min_sample_size = 5  # lower for testing
        outcomes = [
            {"pnl_pct": -1.0, "exit_reason": "stop_hit", "would_have_recovered": True}
            for _ in range(8)
        ] + [
            {"pnl_pct": 2.0, "exit_reason": "target_hit", "would_have_recovered": False}
            for _ in range(5)
        ]
        rules = {"stop_loss_pct": 0.03}
        recs = engine.analyze_and_recommend(outcomes, rules)
        # Should recommend widening stops
        stop_recs = [r for r in recs if r.parameter == "stop_loss_pct"]
        assert len(stop_recs) == 1
        assert stop_recs[0].new_value > stop_recs[0].old_value

    def test_guardrails_clamp(self):
        engine = SelfLearningEngine()
        engine.state.max_adjustment_pct = 0.05  # 5% max
        adj = RuleAdjustment(
            rule_name="test", parameter="stop_loss_pct",
            old_value=0.03, new_value=0.10,  # 233% change
            reason="test", confidence=0.5, sample_size=50,
        )
        approved = engine._apply_guardrails([adj])
        if approved:
            # Should be clamped to 0.03 * 1.05 = 0.0315
            assert approved[0].new_value <= 0.03 * 1.05 + 0.001

    def test_disable_enable(self):
        engine = SelfLearningEngine()
        engine.disable()
        assert not engine.state.enabled
        recs = engine.analyze_and_recommend(
            [{"pnl_pct": 1}] * 50, {"stop_loss_pct": 0.03}
        )
        assert len(recs) == 0  # disabled
        engine.enable()
        assert engine.state.enabled

    def test_audit_trail(self):
        engine = SelfLearningEngine()
        adj = RuleAdjustment(
            rule_name="test", parameter="stop_loss_pct",
            old_value=0.03, new_value=0.035,
            reason="test", confidence=0.5, sample_size=30,
        )
        applied = engine.apply_adjustments([adj])
        assert len(applied) == 1
        assert applied[0].applied
        assert engine.state.total_adjustments == 1
        assert len(engine.state.audit_log) == 1

    def test_tunable_rules_bounds(self):
        for name, rule in TUNABLE_RULES.items():
            assert rule["min"] < rule["max"], f"{name}: min >= max"
            assert rule["min"] <= rule["default"] <= rule["max"], f"{name}: default out of bounds"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
