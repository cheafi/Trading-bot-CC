"""Deterministic trade-plan engine: levels, overrides, fail-closed states."""

from __future__ import annotations

import math

import pytest

from src.engines.strategy_evidence import EvidenceGrade
from src.engines.trade_levels import (
    MIN_BARS,
    STOP_NOTE,
    atr,
    classify_setup_action,
    compute_trade_plan,
    detect_support_resistance,
)


def _bars_from_closes(closes, spread=1.0):
    return [
        {"time": i, "high": c + spread, "low": c - spread, "close": c}
        for i, c in enumerate(closes)
    ]


def _oscillating(n=90, base=100.0, amp=10.0, period=20, drift=0.0):
    return [
        base + drift * i + amp * math.sin(2 * math.pi * i / period) for i in range(n)
    ]


class TestAtr:
    def test_constant_range(self):
        bars = _bars_from_closes([100.0] * 40, spread=1.0)
        h = [b["high"] for b in bars]
        lo = [b["low"] for b in bars]
        c = [b["close"] for b in bars]
        assert atr(h, lo, c) == pytest.approx(2.0)

    def test_insufficient_bars(self):
        assert atr([1.0] * 5, [1.0] * 5, [1.0] * 5) is None


class TestSupportResistance:
    def test_oscillation_yields_levels_on_both_sides(self):
        closes = _oscillating()
        bars = _bars_from_closes(closes)
        sup, res = detect_support_resistance(
            [b["high"] for b in bars],
            [b["low"] for b in bars],
            closes,
            reference_price=100.0,
        )
        assert sup and res
        assert all(lv.price < 100.0 for lv in sup)
        assert all(lv.price > 100.0 for lv in res)
        # Repeated swings must cluster into multi-touch levels.
        assert max(lv.touches for lv in sup + res) >= 2
        # Nearest-first ordering.
        assert sup == sorted(sup, key=lambda lv: 100.0 - lv.price)

    def test_monotonic_series_has_no_resistance_above(self):
        closes = [100.0 + i for i in range(60)]
        bars = _bars_from_closes(closes, spread=0.5)
        _, res = detect_support_resistance(
            [b["high"] for b in bars], [b["low"] for b in bars], closes
        )
        assert res == []

    def test_deterministic(self):
        closes = _oscillating()
        bars = _bars_from_closes(closes)
        args = ([b["high"] for b in bars], [b["low"] for b in bars], closes)
        assert detect_support_resistance(*args) == detect_support_resistance(*args)


class TestPlanFailClosed:
    def test_short_history(self):
        plan = compute_trade_plan(_bars_from_closes([100.0] * (MIN_BARS - 1)))
        assert plan["status"] == "INSUFFICIENT_HISTORY"
        assert plan["entry"] is None and plan["stop"] is None
        assert plan["targets"] == []

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -5.0, None])
    def test_bad_price_never_produces_levels(self, bad):
        bars = _bars_from_closes(_oscillating())
        bars[-5]["close"] = bad
        plan = compute_trade_plan(bars)
        assert plan["status"] == "INVALID_DATA"
        assert plan["entry"] is None and plan["stop"] is None

    def test_missing_field(self):
        bars = _bars_from_closes(_oscillating())
        del bars[10]["low"]
        assert compute_trade_plan(bars)["status"] == "INVALID_DATA"

    def test_nan_override_rejected(self):
        plan = compute_trade_plan(_bars_from_closes(_oscillating()), stop=float("nan"))
        assert plan["status"] == "INVALID_OVERRIDE"
        assert plan["reason_codes"] == ["STOP_PRICE_NAN"]

    def test_stop_above_long_entry_rejected(self):
        plan = compute_trade_plan(
            _bars_from_closes(_oscillating()), entry=100.0, stop=105.0
        )
        assert plan["status"] == "INVALID_STOP"
        assert plan["reason_codes"] == ["STOP_WRONG_SIDE_LONG"]
        assert plan["reward_risk"] is None


class TestPlanLevels:
    def test_long_plan_uses_structure(self):
        plan = compute_trade_plan(_bars_from_closes(_oscillating()), entry=100.0)
        assert plan["status"] == "OK"
        assert plan["entry"] == {"price": 100.0, "method": "USER"}
        assert plan["stop"]["price"] < 100.0
        assert plan["stop"]["method"].startswith("SUPPORT_BUFFER")
        assert plan["targets"][0]["method"] == "STRUCTURE"
        assert plan["targets"][0]["price"] > 100.0
        assert plan["stop_note"] == STOP_NOTE

    def test_no_structure_falls_back_to_atr_stop_and_r_projection(self):
        closes = [100.0 + i for i in range(60)]
        plan = compute_trade_plan(_bars_from_closes(closes, spread=0.5))
        assert plan["status"] == "OK"
        assert plan["targets"][0]["method"] == "2R_PROJECTION"
        assert plan["reward_risk"] == pytest.approx(2.0)

    def test_user_overrides_recalculate_risk(self):
        bars = _bars_from_closes(_oscillating())
        plan = compute_trade_plan(bars, entry=100.0, stop=95.0, targets=[115.0, 120.0])
        assert plan["risk_per_share"] == pytest.approx(5.0)
        assert [t["reward_risk"] for t in plan["targets"]] == [3.0, 4.0]
        assert plan["reward_risk"] == 3.0
        assert plan["overrides"] == {"entry": True, "stop": True, "targets": True}

    def test_target_on_wrong_side(self):
        plan = compute_trade_plan(
            _bars_from_closes(_oscillating()), entry=100.0, stop=95.0, targets=[90.0]
        )
        assert plan["status"] == "INVALID_TARGET"

    def test_short_plan_mirrors(self):
        plan = compute_trade_plan(
            _bars_from_closes(_oscillating()), direction="short", entry=100.0
        )
        assert plan["status"] == "OK"
        assert plan["stop"]["price"] > 100.0
        assert plan["targets"][0]["price"] < 100.0


class TestClassifyAction:
    @pytest.fixture
    def good_plan(self):
        plan = compute_trade_plan(
            _bars_from_closes(_oscillating()), entry=100.0, stop=95.0, targets=[115.0]
        )
        assert plan["status"] == "OK"
        return plan

    def test_buy_setup_requires_validated_evidence(self, good_plan):
        out = classify_setup_action(
            good_plan, evidence_grade=EvidenceGrade.VALIDATED, regime_allowed=True
        )
        assert out["action"] == "BUY SETUP"
        assert out["reasons"] == ["REQUIRES_OPERATOR_APPROVAL"]

    @pytest.mark.parametrize(
        "grade",
        ["PRELIMINARY", "INSUFFICIENT_SAMPLE", "NO_BACKTEST", "FAILED_VALIDATION", None, "bogus"],
    )
    def test_weaker_evidence_caps_at_watch(self, good_plan, grade):
        out = classify_setup_action(good_plan, evidence_grade=grade, regime_allowed=True)
        assert out["action"] == "WATCH"

    def test_regime_blocked_is_no_trade(self, good_plan):
        out = classify_setup_action(
            good_plan, evidence_grade="VALIDATED", regime_allowed=False
        )
        assert out["action"] == "NO TRADE"

    def test_unverified_regime_waits(self, good_plan):
        out = classify_setup_action(
            good_plan, evidence_grade="VALIDATED", regime_allowed=None
        )
        assert out["action"] == "WAIT"
        assert "REGIME_UNVERIFIED" in out["reasons"]

    def test_low_rr_waits(self):
        plan = compute_trade_plan(
            _bars_from_closes(_oscillating()), entry=100.0, stop=95.0, targets=[105.0]
        )
        out = classify_setup_action(plan, evidence_grade="VALIDATED", regime_allowed=True)
        assert out["action"] == "WAIT"

    def test_invalid_plan_is_no_trade(self):
        plan = compute_trade_plan(_bars_from_closes([100.0] * 5))
        out = classify_setup_action(plan, evidence_grade="VALIDATED", regime_allowed=True)
        assert out["action"] == "NO TRADE"
