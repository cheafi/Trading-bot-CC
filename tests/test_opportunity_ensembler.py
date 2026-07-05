"""
Tests for src/engines/opportunity_ensembler.py

Focus: net expectancy math, suppression gates, regime-conditional weights.

Team RISK mandate: the ensembler is the last defence before broker execution.
Every gate must be tested explicitly.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engines.opportunity_ensembler import (
    OpportunityEnsembler,
    DEFAULT_WEIGHTS,
    MIN_COMPOSITE_SCORE,
    MIN_RISK_REWARD,
    MIN_WIN_PROBABILITY,
)


# ── Minimal stub for TradeRecommendation ─────────────────────────

class FakeRec:
    """Minimal TradeRecommendation stub for unit tests.

    The ensembler only reads attribute fields — no DB, no network.
    """
    def __init__(
        self,
        ticker="AAPL",
        direction="LONG",
        strategy_id="momentum",
        signal_confidence=70.0,
        risk_reward_ratio=3.0,
        edge_p_t1=0.0,
        ml_win_probability=0.0,
        strategy_health=0.6,
        regime_fit=0.7,
        timing_score=0.6,
        action_state="TRADE",
        metadata=None,
    ):
        self.ticker              = ticker
        self.direction           = direction
        self.strategy_id         = strategy_id
        self.signal_confidence   = signal_confidence
        self.risk_reward_ratio   = risk_reward_ratio
        self.edge_p_t1           = edge_p_t1
        self.ml_win_probability  = ml_win_probability
        self.strategy_health     = strategy_health
        self.regime_fit          = regime_fit
        self.timing_score        = timing_score
        self.action_state        = action_state
        self.metadata            = metadata or {}
        # Fields set by ensembler
        self.composite_score     = 0.0
        self.trade_decision      = False
        self.suppression_reason  = ""
        self.why_not_trade       = ""
        self.components: dict    = {}


def normal_regime():
    return {
        "should_trade":        True,
        "entropy":             0.3,
        "risk_on_uptrend":     0.7,
        "neutral_range":       0.2,
        "risk_off_downtrend":  0.1,
        "no_trade_reason":     "",
    }


def no_trade_regime(reason="VIX spike"):
    r = normal_regime()
    r["should_trade"] = False
    r["no_trade_reason"] = reason
    return r


def high_entropy_regime():
    r = normal_regime()
    r["entropy"] = 0.95
    return r


# ── Initialisation ────────────────────────────────────────────────

class TestInit:
    def test_default_weights_sum_to_1(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"DEFAULT_WEIGHTS sum={total:.4f}"

    def test_custom_weights_normalised(self):
        bad_weights = {"net_expectancy": 2.0, "momentum": 2.0,
                       "timing": 2.0, "regime_fit": 2.0,
                       "rs_rank": 2.0, "health": 2.0}
        e = OpportunityEnsembler(weights=bad_weights)
        total = sum(e.weights.values())
        assert abs(total - 1.0) < 1e-9, "Weights not normalised"

    def test_empty_recommendations(self):
        e = OpportunityEnsembler()
        assert e.rank_opportunities([], normal_regime()) == []


# ── Net expectancy math ───────────────────────────────────────────

class TestNetExpectancy:
    """Core quant principle: only take positive-EV trades."""

    def test_positive_ev_produces_higher_score(self):
        e = OpportunityEnsembler()
        # High pwin, high RR → should score better than low pwin, low RR
        good = FakeRec(signal_confidence=75.0, risk_reward_ratio=4.0)
        bad  = FakeRec(signal_confidence=45.0, risk_reward_ratio=1.5)
        g = e._score_one(good, normal_regime(), {})
        b = e._score_one(bad,  normal_regime(), {})
        assert g.composite_score > b.composite_score, (
            f"Good EV trade scored {g.composite_score:.3f} <= bad {b.composite_score:.3f}"
        )

    def test_net_exp_component_positive_for_good_trade(self):
        e = OpportunityEnsembler()
        rec = FakeRec(signal_confidence=70.0, risk_reward_ratio=3.0)
        scored = e._score_one(rec, normal_regime(), {})
        net_exp_R = scored.components["net_exp_raw_R"]
        pwin      = scored.components["pwin"]
        rr        = scored.components["rr"]
        # Verify the formula manually
        expected = pwin * rr - (1 - pwin) * 1.0
        assert abs(net_exp_R - expected) < 1e-9, (
            f"net_exp_raw_R={net_exp_R:.4f} != formula {expected:.4f}"
        )

    def test_edge_p_t1_preferred_over_confidence(self):
        """edge_p_t1 (calibrated) must override raw signal_confidence."""
        e = OpportunityEnsembler()
        rec = FakeRec(signal_confidence=40.0, edge_p_t1=0.75)
        scored = e._score_one(rec, normal_regime(), {})
        assert scored.components["pwin"] == pytest.approx(0.75, abs=1e-9)

    def test_ml_win_prob_used_when_no_edge_p_t1(self):
        e = OpportunityEnsembler()
        rec = FakeRec(signal_confidence=40.0, ml_win_probability=0.68, edge_p_t1=0.0)
        scored = e._score_one(rec, normal_regime(), {})
        assert scored.components["pwin"] == pytest.approx(0.68, abs=1e-9)

    def test_composite_bounded_0_to_1(self):
        e = OpportunityEnsembler()
        for _ in range(50):
            rec = FakeRec(signal_confidence=100.0, risk_reward_ratio=10.0)
            scored = e._score_one(rec, normal_regime(), {})
            assert 0.0 <= scored.composite_score <= 1.0


# ── Suppression gates ─────────────────────────────────────────────

class TestSuppressionGates:
    """Every gate must suppress the trade and set the correct reason."""

    def test_regime_no_trade_gate(self):
        e = OpportunityEnsembler()
        rec = FakeRec()
        result = e.rank_opportunities([rec], no_trade_regime("VIX > 40"))
        assert not result[0].trade_decision
        assert result[0].suppression_reason == "regime_no_trade"
        assert "VIX > 40" in result[0].why_not_trade

    def test_high_entropy_gate(self):
        e = OpportunityEnsembler()
        rec = FakeRec()
        result = e.rank_opportunities([rec], high_entropy_regime())
        assert not result[0].trade_decision
        assert result[0].suppression_reason == "high_entropy"

    def test_negative_expectancy_gate(self):
        """p(win)=0.3, RR=1.0 → net_exp = 0.3*1 - 0.7*1 = -0.4 → suppress."""
        e = OpportunityEnsembler()
        rec = FakeRec(signal_confidence=30.0, risk_reward_ratio=1.0)
        result = e.rank_opportunities([rec], normal_regime())
        assert not result[0].trade_decision
        assert result[0].suppression_reason == "negative_expectancy"

    def test_below_min_score_gate(self):
        # Ensure score is just below threshold by setting very low confidence
        e = OpportunityEnsembler(min_score=0.80)  # very high bar
        rec = FakeRec(signal_confidence=50.0, risk_reward_ratio=2.0)
        result = e.rank_opportunities([rec], normal_regime())
        # With min_score=0.80 a mediocre rec should fail
        assert not result[0].trade_decision

    def test_low_pwin_gate(self):
        e = OpportunityEnsembler(min_pwin=0.55)
        rec = FakeRec(signal_confidence=45.0, risk_reward_ratio=5.0)  # high RR, low pwin
        result = e.rank_opportunities([rec], normal_regime())
        # pwin = 0.45 < 0.55 minimum; net_exp = 0.45*5 - 0.55 = 1.7 > 0 so not EV gate
        assert not result[0].trade_decision
        assert result[0].suppression_reason == "low_pwin"

    def test_rr_too_low_for_trade_conviction(self):
        e = OpportunityEnsembler(min_rr=2.0)
        # High pwin so net_exp positive; score should pass other gates
        rec = FakeRec(signal_confidence=75.0, risk_reward_ratio=1.5, action_state="TRADE")
        result = e.rank_opportunities([rec], normal_regime())
        assert not result[0].trade_decision
        assert result[0].suppression_reason == "rr_too_low"

    def test_watch_conviction_not_blocked_by_rr(self):
        """WATCH conviction should not be blocked by R:R gate."""
        e = OpportunityEnsembler(min_rr=2.0)
        rec = FakeRec(signal_confidence=75.0, risk_reward_ratio=1.5, action_state="WATCH")
        result = e.rank_opportunities([rec], normal_regime())
        # Should pass (rr_too_low only applies to TRADE)
        if result[0].suppression_reason:
            assert result[0].suppression_reason != "rr_too_low", (
                "WATCH conviction should not be blocked by R:R gate"
            )

    def test_good_trade_passes_all_gates(self):
        e = OpportunityEnsembler()
        rec = FakeRec(signal_confidence=75.0, risk_reward_ratio=3.5)
        result = e.rank_opportunities([rec], normal_regime())
        assert result[0].trade_decision
        assert result[0].suppression_reason == ""


# ── Sorting ───────────────────────────────────────────────────────

class TestSorting:
    def test_tradeable_before_suppressed(self):
        e = OpportunityEnsembler()
        good = FakeRec(signal_confidence=75.0, risk_reward_ratio=3.5, ticker="AAPL")
        bad  = FakeRec(signal_confidence=30.0, risk_reward_ratio=0.5, ticker="BAD")
        result = e.rank_opportunities([bad, good], normal_regime())
        assert result[0].ticker == "AAPL", "Tradeable rec must appear first"

    def test_higher_score_first_among_tradeable(self):
        e = OpportunityEnsembler()
        strong = FakeRec(signal_confidence=85.0, risk_reward_ratio=4.0, ticker="STRONG")
        weak   = FakeRec(signal_confidence=60.0, risk_reward_ratio=2.5, ticker="WEAK")
        result = e.rank_opportunities([weak, strong], normal_regime())
        tradeable = [r for r in result if r.trade_decision]
        if len(tradeable) >= 2:
            assert tradeable[0].ticker == "STRONG"


# ── Momentum scoring ──────────────────────────────────────────────

class TestMomentumScoring:
    def test_macd_aligned_boosts_momentum(self):
        e = OpportunityEnsembler()
        aligned = FakeRec(direction="LONG", metadata={"macd_hist": 0.5})
        conflict = FakeRec(direction="LONG", metadata={"macd_hist": -0.5})
        s_a = e._score_one(aligned,  normal_regime(), {})
        s_c = e._score_one(conflict, normal_regime(), {})
        assert s_a.components["momentum"] > s_c.components["momentum"]

    def test_ha_direction_aligned_boosts_momentum(self):
        e = OpportunityEnsembler()
        aligned  = FakeRec(direction="LONG", metadata={"ha_direction": "UP"})
        conflict = FakeRec(direction="LONG", metadata={"ha_direction": "DOWN"})
        s_a = e._score_one(aligned,  normal_regime(), {})
        s_c = e._score_one(conflict, normal_regime(), {})
        assert s_a.components["momentum"] > s_c.components["momentum"]

    def test_both_aligned_gives_max_momentum(self):
        e = OpportunityEnsembler()
        rec = FakeRec(direction="LONG", metadata={"macd_hist": 1.0, "ha_direction": "UP"})
        scored = e._score_one(rec, normal_regime(), {})
        assert scored.components["momentum"] == pytest.approx(1.0, abs=1e-9)


# ── Timing scoring (BB + Dual Thrust) ────────────────────────────

class TestTimingScoring:
    def test_bb_contracted_adds_bonus(self):
        e = OpportunityEnsembler()
        coiled    = FakeRec(metadata={"bb_pct_b": 0.5, "bb_contracted": True})
        not_coiled = FakeRec(metadata={"bb_pct_b": 0.5, "bb_contracted": False})
        t_c = e._score_one(coiled,     normal_regime(), {}).components["timing"]
        t_n = e._score_one(not_coiled, normal_regime(), {}).components["timing"]
        assert t_c > t_n, "BB contracted (coil) should boost timing score"

    def test_dual_thrust_break_adds_bonus(self):
        e = OpportunityEnsembler()
        breakout  = FakeRec(metadata={"bb_pct_b": 0.5, "dual_thrust_upper_break": True})
        no_break  = FakeRec(metadata={"bb_pct_b": 0.5, "dual_thrust_upper_break": False})
        t_b = e._score_one(breakout, normal_regime(), {}).components["timing"]
        t_n = e._score_one(no_break, normal_regime(), {}).components["timing"]
        assert t_b > t_n, "Dual Thrust breakout should boost timing score"

    def test_timing_bounded_0_to_1(self):
        e = OpportunityEnsembler()
        rec = FakeRec(metadata={"bb_pct_b": 0.1, "bb_contracted": True,
                                "dual_thrust_upper_break": True})
        scored = e._score_one(rec, normal_regime(), {})
        assert 0.0 <= scored.components["timing"] <= 1.0


# ── RS rank scoring ───────────────────────────────────────────────

class TestRsRankScoring:
    def test_leader_gets_highest_score(self):
        e = OpportunityEnsembler()
        leader  = FakeRec(metadata={"rs_status": "LEADER"})
        laggard = FakeRec(metadata={"rs_status": "LAGGARD"})
        sl = e._score_one(leader,  normal_regime(), {}).components["rs_rank"]
        sla = e._score_one(laggard, normal_regime(), {}).components["rs_rank"]
        assert sl > sla

    def test_known_statuses_mapped_correctly(self):
        e = OpportunityEnsembler()
        expected = {"LEADER": 1.00, "STRONG": 0.75,
                    "NEUTRAL": 0.50, "WEAK": 0.25, "LAGGARD": 0.10}
        for status, score in expected.items():
            rec = FakeRec(metadata={"rs_status": status})
            s = e._score_one(rec, normal_regime(), {}).components["rs_rank"]
            assert s == pytest.approx(score, abs=1e-9), (
                f"rs_status={status}: expected {score}, got {s}"
            )


# ── Regime fit scoring ────────────────────────────────────────────

class TestRegimeFit:
    def test_momentum_strategy_scores_best_in_risk_on(self):
        e = OpportunityEnsembler()
        risk_on = {**normal_regime(),
                   "risk_on_uptrend": 0.95, "neutral_range": 0.04, "risk_off_downtrend": 0.01}
        risk_off = {**normal_regime(),
                    "risk_on_uptrend": 0.01, "neutral_range": 0.04, "risk_off_downtrend": 0.95}
        rec_on  = FakeRec(strategy_id="momentum")
        rec_off = FakeRec(strategy_id="momentum")
        fit_on  = e._score_one(rec_on,  risk_on,  {}).components["regime_fit"]
        fit_off = e._score_one(rec_off, risk_off, {}).components["regime_fit"]
        assert fit_on > fit_off, (
            f"Momentum strategy regime fit: risk_on={fit_on:.3f}, risk_off={fit_off:.3f}"
        )

    def test_defensive_strategy_scores_best_in_risk_off(self):
        e = OpportunityEnsembler()
        risk_on  = {**normal_regime(), "risk_on_uptrend": 0.95, "neutral_range": 0.04, "risk_off_downtrend": 0.01}
        risk_off = {**normal_regime(), "risk_on_uptrend": 0.01, "neutral_range": 0.04, "risk_off_downtrend": 0.95}
        rec_on  = FakeRec(strategy_id="defensive")
        rec_off = FakeRec(strategy_id="defensive")
        fit_on  = e._score_one(rec_on,  risk_on,  {}).components["regime_fit"]
        fit_off = e._score_one(rec_off, risk_off, {}).components["regime_fit"]
        assert fit_off > fit_on, (
            f"Defensive strategy regime fit: risk_on={fit_on:.3f}, risk_off={fit_off:.3f}"
        )

    def test_unknown_strategy_returns_fallback(self):
        e = OpportunityEnsembler()
        rec = FakeRec(strategy_id="totally_unknown_xyz")
        scored = e._score_one(rec, normal_regime(), {})
        assert scored.components["regime_fit"] > 0


# ── Components dict integrity ─────────────────────────────────────

class TestComponentsDict:
    def test_all_components_present(self):
        e = OpportunityEnsembler()
        rec = FakeRec()
        scored = e._score_one(rec, normal_regime(), {})
        for key in ("net_expectancy", "net_exp_raw_R", "pwin", "rr",
                    "momentum", "timing", "regime_fit", "rs_rank", "health"):
            assert key in scored.components, f"Missing component: {key}"

    def test_net_exp_norm_bounded(self):
        e = OpportunityEnsembler()
        for conf in [10, 30, 50, 70, 90]:
            rec = FakeRec(signal_confidence=float(conf), risk_reward_ratio=3.0)
            scored = e._score_one(rec, normal_regime(), {})
            assert 0.0 <= scored.components["net_expectancy"] <= 1.0
