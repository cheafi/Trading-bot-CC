"""Regression tests for src/engines/strategy_evidence.py.

Guards the EVIDENCE BEFORE EXECUTION rule. The defects these tests pin:

* a strategy with no losing trades must never report an *infinite* profit
  factor (false confidence — same class as the market_cap=inf universe gate);
* a small sample must never be promoted to an actionable grade;
* a win rate must never be presented as the probability that the next trade
  succeeds — only an interval, graded on its lower bound.
"""

from __future__ import annotations

import math

import pytest

from src.engines.strategy_evidence import (
    MAX_DRAWDOWN_PCT,
    MIN_SAMPLE_PRELIMINARY,
    MIN_SAMPLE_VALIDATED,
    EvidenceGrade,
    TradeRecord,
    grade_strategy_evidence,
    profit_factor,
    wilson_interval,
)


def _trades(rs, *, oos: bool = False, sid: str = "s"):
    return [TradeRecord(r_multiple=r, strategy_id=sid, out_of_sample=oos) for r in rs]


def _alternating(
    pairs: int, win_r: float = 2.0, loss_r: float = -1.0, oos: bool = True
):
    """pairs * 2 trades, interleaved so the equity curve trends up."""
    out = []
    for _ in range(pairs):
        out.append(TradeRecord(win_r, "s", oos))
        out.append(TradeRecord(loss_r, "s", oos))
    return out


# ── profit_factor ───────────────────────────────────────────────────────────


class TestProfitFactor:
    def test_no_losses_is_undefined_not_infinite(self):
        pf = profit_factor(1000.0, 0.0)
        assert pf is None
        assert pf != float("inf")

    def test_negative_gross_loss_is_undefined(self):
        assert profit_factor(10.0, -5.0) is None

    def test_no_profit_is_zero(self):
        assert profit_factor(0.0, 10.0) == 0.0

    def test_normal_ratio(self):
        assert profit_factor(150.0, 100.0) == pytest.approx(1.5)


# ── wilson_interval ─────────────────────────────────────────────────────────


class TestWilsonInterval:
    def test_zero_trials_is_degenerate_not_a_crash(self):
        assert wilson_interval(0, 0) == (0.0, 0.0)

    def test_small_sample_70pct_lower_bound_is_near_coinflip(self):
        """7/10 looks like a 70% edge; the pessimistic bound says ~40%."""
        low, high = wilson_interval(7, 10)
        assert low == pytest.approx(0.3968, abs=1e-3)
        assert high == pytest.approx(0.8922, abs=1e-3)
        assert low < 0.50

    def test_interval_narrows_as_sample_grows(self):
        small = wilson_interval(7, 10)
        large = wilson_interval(700, 1000)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_bounds_stay_inside_unit_interval(self):
        for s, n in ((0, 5), (5, 5), (1, 3), (99, 100)):
            low, high = wilson_interval(s, n)
            assert 0.0 <= low <= high <= 1.0


# ── grading: absent / unusable input ────────────────────────────────────────


class TestNoBacktest:
    @pytest.mark.parametrize("value", [None, [], ()])
    def test_absent_history_is_no_backtest_not_a_default(self, value):
        r = grade_strategy_evidence(value, strategy_id="x")
        assert r.grade is EvidenceGrade.NO_BACKTEST
        assert r.reason_codes == ["NO_TRADE_HISTORY"]
        assert r.is_actionable is False
        assert r.win_rate is None
        assert r.profit_factor is None

    def test_nan_and_inf_r_multiples_are_discarded(self):
        bad = _trades([float("nan"), float("inf"), float("-inf")])
        assert grade_strategy_evidence(bad).grade is EvidenceGrade.NO_BACKTEST

    def test_nan_does_not_poison_a_valid_sample(self):
        rs = [1.0] * 40 + [float("nan")]
        r = grade_strategy_evidence(_trades(rs))
        assert r.sample_size == 40
        assert not math.isnan(r.expectancy_r)


# ── grading: sample size ────────────────────────────────────────────────────


class TestSampleGates:
    def test_below_30_is_insufficient_even_when_profitable(self):
        r = grade_strategy_evidence(_alternating(10))  # 20 trades, pf 2.0
        assert r.grade is EvidenceGrade.INSUFFICIENT_SAMPLE
        assert r.reason_codes == [f"SAMPLE_BELOW_{MIN_SAMPLE_PRELIMINARY}"]
        assert r.is_actionable is False

    def test_between_30_and_100_is_at_best_preliminary(self):
        r = grade_strategy_evidence(_alternating(20))  # 40 trades
        assert r.grade is EvidenceGrade.PRELIMINARY
        assert f"SAMPLE_BELOW_{MIN_SAMPLE_VALIDATED}" in r.reason_codes
        assert r.is_actionable is False

    def test_a_perfect_record_is_still_not_validated(self):
        """50 wins, zero losses. Undefined PF, not a flawless strategy."""
        r = grade_strategy_evidence(_trades([1.0] * 50, oos=True))
        assert r.profit_factor is None
        assert "PROFIT_FACTOR_UNDEFINED_NO_LOSSES" in r.reason_codes
        assert r.is_actionable is False


# ── grading: disqualifiers ──────────────────────────────────────────────────


class TestFailedValidation:
    def test_negative_expectancy_fails(self):
        r = grade_strategy_evidence(_alternating(60, 1.0, -1.5))
        assert r.grade is EvidenceGrade.FAILED_VALIDATION
        assert "NEGATIVE_EXPECTANCY" in r.reason_codes
        assert r.is_actionable is False

    def test_thin_profit_factor_fails(self):
        # 60 x +1.05R, 60 x -1.0R -> pf 1.05 < 1.20
        r = grade_strategy_evidence(_alternating(60, 1.05, -1.0))
        assert r.grade is EvidenceGrade.FAILED_VALIDATION
        assert "PROFIT_FACTOR_BELOW_MIN" in r.reason_codes

    def test_unholdable_drawdown_fails(self):
        # Build equity to +50R, then give back far more than MAX_DRAWDOWN_PCT.
        rs = [1.0] * 50 + [-1.0] * 30 + [0.1] * 40
        r = grade_strategy_evidence(_trades(rs, oos=True))
        assert r.max_drawdown_pct > MAX_DRAWDOWN_PCT
        assert r.grade is EvidenceGrade.FAILED_VALIDATION
        assert "DRAWDOWN_EXCEEDS_MAX" in r.reason_codes


# ── grading: the validated path ─────────────────────────────────────────────


class TestValidated:
    def _good(self):
        return _alternating(60, 2.0, -1.0, oos=True)  # 120 trades, pf 2.0

    def test_large_profitable_out_of_sample_sample_is_validated(self):
        r = grade_strategy_evidence(self._good())
        assert r.grade is EvidenceGrade.VALIDATED
        assert r.is_actionable is True
        assert r.reason_codes == []
        assert r.sample_size == 120
        assert r.profit_factor == pytest.approx(2.0)
        assert r.expectancy_r == pytest.approx(0.5)

    def test_in_sample_only_cannot_be_validated(self):
        in_sample = _alternating(60, 2.0, -1.0, oos=False)
        r = grade_strategy_evidence(in_sample, require_out_of_sample=True)
        assert r.grade is EvidenceGrade.PRELIMINARY
        assert "NO_OUT_OF_SAMPLE_TRADES" in r.reason_codes
        assert r.is_actionable is False

    def test_out_of_sample_requirement_can_be_relaxed_for_research(self):
        in_sample = _alternating(60, 2.0, -1.0, oos=False)
        r = grade_strategy_evidence(in_sample, require_out_of_sample=False)
        assert r.grade is EvidenceGrade.VALIDATED

    def test_marginal_edge_with_coinflip_interval_is_not_validated(self):
        # pf 1.3 (>= min) but < 1.5, and the win-rate CI spans 0.50.
        r = grade_strategy_evidence(_alternating(60, 1.3, -1.0, oos=True))
        assert r.win_rate_ci_low <= 0.50
        assert r.grade is EvidenceGrade.PRELIMINARY
        assert "WIN_RATE_CI_SPANS_COINFLIP" in r.reason_codes


# ── reporting contract ──────────────────────────────────────────────────────


class TestReportContract:
    def test_only_validated_is_actionable(self):
        for g in EvidenceGrade:
            assert g.is_actionable is (g is EvidenceGrade.VALIDATED)

    def test_headline_never_claims_an_untested_edge(self):
        r = grade_strategy_evidence(None)
        assert r.headline == "NO BACKTEST"
        small = grade_strategy_evidence(_alternating(5))
        assert "INSUFFICIENT EVIDENCE" in small.headline

    def test_to_dict_is_json_safe(self):
        import json

        for trades in (None, _alternating(5), _alternating(60, 2.0, -1.0, oos=True)):
            payload = grade_strategy_evidence(trades).to_dict()
            text = json.dumps(payload)  # raises on inf/nan-free violation
            assert "Infinity" not in text
            assert "NaN" not in text
            assert isinstance(payload["actionable"], bool)
