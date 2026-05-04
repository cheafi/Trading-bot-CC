"""Sprint 73 — Decision Object · Peer Comparison · Portfolio Brain · Keep/Discard."""

from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# 1. DecisionObject + Pipeline
# ═══════════════════════════════════════════════════════════════════════════


class TestDecisionObject:
    def test_importable(self):
        from src.engines.decision_object import DecisionObject, DecisionPipeline

        assert DecisionObject is not None
        assert DecisionPipeline is not None

    def test_defaults(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(ticker="NVDA")
        assert d.ticker == "NVDA"
        assert d.action == "WAIT"
        assert d.macro_regime == "UNKNOWN"
        assert d.final_confidence == 50
        assert d.contradictions == []
        assert d.synthetic is False

    def test_compute_final_confidence(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(
            thesis_confidence=80,
            timing_confidence=60,
            execution_confidence=70,
            data_confidence=40,
        )
        fc = d.compute_final_confidence()
        expected = int(0.35 * 80 + 0.25 * 60 + 0.25 * 70 + 0.15 * 40)
        assert fc == expected
        assert d.final_confidence == expected

    def test_derive_action_risk_off(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(macro_regime="RISK_OFF", final_confidence=90)
        assert d.derive_action() == "NO_TRADE"

    def test_derive_action_vix_risk_off(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(vix_regime="RISK_OFF", final_confidence=90)
        assert d.derive_action() == "NO_TRADE"

    def test_derive_action_trade(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(
            final_confidence=80,
            rs_state="CONFIRMED_LEADER",
            macro_regime="RISK_ON",
        )
        assert d.derive_action() == "TRADE"

    def test_derive_action_watch(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(final_confidence=65, rs_state="NEUTRAL")
        assert d.derive_action() == "WATCH"

    def test_derive_action_reject(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(final_confidence=20)
        assert d.derive_action() == "REJECT"

    def test_to_dict_has_key_fields(self):
        from src.engines.decision_object import DecisionObject

        d = DecisionObject(ticker="AAPL")
        d.compute_final_confidence()
        d.derive_action()
        out = d.to_dict()
        for key in (
            "ticker",
            "macro_regime",
            "action",
            "final_confidence",
            "why_now",
            "contradictions",
            "peer_comparison",
            "portfolio_fit",
            "synthetic",
        ):
            assert key in out, f"Missing key: {key}"

    def test_pipeline_importable(self):
        from src.engines.decision_object import DecisionPipeline

        p = DecisionPipeline()
        assert hasattr(p, "build")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Peer Comparison
# ═══════════════════════════════════════════════════════════════════════════


class TestPeerComparison:
    def test_importable(self):
        from src.engines.peer_comparison import PeerEngine, PEER_GROUPS

        assert PeerEngine is not None
        assert isinstance(PEER_GROUPS, dict)

    def test_peer_groups_populated(self):
        from src.engines.peer_comparison import PEER_GROUPS

        assert "NVDA" in PEER_GROUPS
        assert "AMD" in PEER_GROUPS["NVDA"]
        assert len(PEER_GROUPS) >= 20

    def test_get_sector_peers_known(self):
        from src.engines.peer_comparison import PeerEngine

        pe = PeerEngine()
        peers = pe.get_sector_peers("NVDA")
        assert isinstance(peers, list)
        assert len(peers) > 0
        assert "NVDA" not in peers  # self excluded

    def test_get_sector_peers_unknown(self):
        from src.engines.peer_comparison import PeerEngine

        pe = PeerEngine()
        peers = pe.get_sector_peers("ZZZZZ")
        assert isinstance(peers, list)  # empty or fallback

    def test_get_behavior_peers(self):
        from src.engines.peer_comparison import PeerEngine

        pe = PeerEngine()
        peers = pe.get_behavior_peers("NVDA", rs_composite=120.0, rs_slope=0.5)
        assert isinstance(peers, list)

    def test_compare_vs_peers_structure(self):
        from src.engines.peer_comparison import PeerEngine

        pe = PeerEngine()
        report = pe.compare_vs_peers("NVDA")
        assert isinstance(report, dict)
        assert "ticker" in report
        assert "sector_peers" in report


# ═══════════════════════════════════════════════════════════════════════════
# 3. Portfolio Brain
# ═══════════════════════════════════════════════════════════════════════════


class TestPortfolioBrain:
    def test_importable(self):
        from src.engines.portfolio_brain import (
            PortfolioPolicy,
            Holding,
            PortfolioRun,
            PortfolioReview,
            PortfolioBrain,
            TREND_LEADERS_POLICY,
        )

        assert PortfolioPolicy is not None
        assert TREND_LEADERS_POLICY.archetype == "TREND_LEADERS"

    def test_policy_defaults(self):
        from src.engines.portfolio_brain import PortfolioPolicy

        p = PortfolioPolicy(name="test", archetype="TEST")
        assert p.max_positions == 10
        assert p.correlation_cap == 0.70
        assert p.sizing_policy == "EQUAL"

    def test_policy_to_dict(self):
        from src.engines.portfolio_brain import TREND_LEADERS_POLICY

        d = TREND_LEADERS_POLICY.to_dict()
        assert d["archetype"] == "TREND_LEADERS"
        assert d["benchmark"] == "SPY"
        assert d["stop_policy"] == "TRAILING_1R"

    def test_holding_pnl(self):
        from src.engines.portfolio_brain import Holding

        h = Holding(
            ticker="AAPL",
            entry_price=150.0,
            shares=100,
            sector="Tech",
            current_price=165.0,
            stop=135.0,
        )
        h.update_pnl()
        assert h.pnl_pct == pytest.approx(10.0)
        assert h.r_multiple == pytest.approx(1.0)

    def test_portfolio_run_add_close(self):
        from src.engines.portfolio_brain import (
            PortfolioRun,
            Holding,
            TREND_LEADERS_POLICY,
        )

        run = PortfolioRun(policy=TREND_LEADERS_POLICY)
        h = Holding(ticker="NVDA", entry_price=800.0, shares=10, sector="Semis")
        run.add_holding(h)
        assert len(run.open_positions()) == 1
        assert run.holdings[0].ticker == "NVDA"
        run.close_holding("NVDA", exit_price=900.0, reason="TARGET_HIT")
        assert len(run.open_positions()) == 0
        assert len(run.closed_positions()) == 1

    def test_portfolio_run_can_add_gate(self):
        from src.engines.portfolio_brain import (
            PortfolioRun,
            Holding,
            TREND_LEADERS_POLICY,
        )

        run = PortfolioRun(policy=TREND_LEADERS_POLICY)
        ok, reason = run.can_add(ticker="NVDA", sector="Tech")
        assert ok is True
        # Duplicate check
        h = Holding(ticker="NVDA", entry_price=800.0, shares=10, sector="Tech")
        run.add_holding(h)
        ok2, reason2 = run.can_add(ticker="NVDA", sector="Tech")
        assert ok2 is False

    def test_portfolio_brain_three_archetypes(self):
        from src.engines.portfolio_brain import PortfolioBrain

        brain = PortfolioBrain()
        summaries = brain.all_summaries()
        assert len(summaries) == 3
        names = {s["archetype"] for s in summaries}
        assert names == {"TREND_LEADERS", "DEFENSIVE", "TACTICAL"}

    def test_generate_review(self):
        from src.engines.portfolio_brain import (
            generate_review,
            PortfolioRun,
            PortfolioReview,
            TREND_LEADERS_POLICY,
        )

        run = PortfolioRun(policy=TREND_LEADERS_POLICY)
        result = generate_review(run)
        assert isinstance(result, PortfolioReview)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Keep / Discard
# ═══════════════════════════════════════════════════════════════════════════


class TestKeepDiscard:
    def test_importable(self):
        from src.engines.keep_discard import (
            StrategyVariant,
            StrategyEvaluator,
            ExperimentLog,
        )

        assert StrategyVariant is not None
        assert StrategyEvaluator is not None

    def test_variant_weights_sum(self):
        from src.engines.keep_discard import StrategyVariant

        v = StrategyVariant()
        total = (
            v.w_rs_quality
            + v.w_trend
            + v.w_sector
            + v.w_setup
            + v.w_liquidity
            + v.w_tradeability
        )
        assert total == pytest.approx(1.0)

    def test_evaluator_locked_weights(self):
        from src.engines.keep_discard import StrategyEvaluator

        ev = StrategyEvaluator()
        total = (
            ev.W_OUTPERFORMANCE
            + ev.W_SHARPE
            + ev.W_DRAWDOWN
            + ev.W_TURNOVER
            + ev.W_STABILITY
        )
        assert total == pytest.approx(1.0)

    def test_evaluate_score(self):
        from src.engines.keep_discard import StrategyEvaluator, StrategyVariant

        ev = StrategyEvaluator()
        v = StrategyVariant(name="test")
        result = ev.evaluate(
            variant=v,
            total_return=15.0,
            benchmark_return=10.0,
            sharpe=1.5,
            max_drawdown=-0.10,
            turnover=0.5,
            stability=80.0,
        )
        assert hasattr(result, "score")
        assert isinstance(result.score, float)

    def test_compare_keep(self):
        from src.engines.keep_discard import StrategyEvaluator, StrategyVariant

        ev = StrategyEvaluator()
        v1 = StrategyVariant(name="baseline")
        v2 = StrategyVariant(name="improved")
        baseline = ev.evaluate(
            variant=v1,
            total_return=10.0,
            benchmark_return=10.0,
            sharpe=0.5,
            max_drawdown=-0.30,
            turnover=0.8,
            stability=40.0,
        )
        candidate = ev.evaluate(
            variant=v2,
            total_return=20.0,
            benchmark_return=10.0,
            sharpe=2.0,
            max_drawdown=-0.05,
            turnover=0.3,
            stability=90.0,
        )
        result = ev.compare(baseline, candidate)
        assert result.verdict == "KEEP"

    def test_compare_discard(self):
        from src.engines.keep_discard import StrategyEvaluator, StrategyVariant

        ev = StrategyEvaluator()
        v1 = StrategyVariant(name="baseline")
        v2 = StrategyVariant(name="similar")
        baseline = ev.evaluate(
            variant=v1,
            total_return=12.0,
            benchmark_return=10.0,
            sharpe=1.0,
            max_drawdown=-0.15,
            turnover=0.5,
            stability=60.0,
        )
        candidate = ev.evaluate(
            variant=v2,
            total_return=12.5,
            benchmark_return=10.0,
            sharpe=1.05,
            max_drawdown=-0.14,
            turnover=0.5,
            stability=61.0,
        )
        result = ev.compare(baseline, candidate)
        assert result.verdict == "DISCARD"

    def test_experiment_log_persistence(self, tmp_path):
        from src.engines.keep_discard import (
            ExperimentLog,
            ExperimentResult,
            StrategyVariant,
        )

        log_path = tmp_path / "test_log.json"
        log = ExperimentLog(path=log_path)
        result = ExperimentResult(
            variant_name="v2",
            variant_version=1,
            total_return_pct=15.0,
            benchmark_return_pct=10.0,
            outperformance=5.0,
            sharpe=1.5,
            max_drawdown_pct=-0.10,
            turnover=0.5,
            stability=80.0,
            score=75.0,
            verdict="KEEP",
            reason="test",
        )
        log.record(StrategyVariant(name="v2"), result)
        assert len(log.entries) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. Decision Pipeline Router
# ═══════════════════════════════════════════════════════════════════════════


class TestDecisionPipelineRouter:
    def test_router_importable(self):
        from src.api.routers.decision_pipeline import router

        paths = [r.path for r in router.routes]
        assert "/api/decide/{ticker}" in paths
        assert "/api/decide/batch" in paths
        assert "/api/decide/peers/{ticker}" in paths
        assert "/api/portfolio" in paths
        assert "/api/experiments" in paths

    def test_portfolio_archetype_route_exists(self):
        from src.api.routers.decision_pipeline import router

        paths = [r.path for r in router.routes]
        assert "/api/portfolio/{archetype}" in paths
        assert "/api/portfolio/review" in paths
        assert "/api/experiments/best" in paths
