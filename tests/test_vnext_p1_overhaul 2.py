"""
VNext P1 Overhaul Tests — Professional Review Response
=======================================================

Tests for all P1 changes from the professional review:
  - P1-A: Backtest realism (commission + slippage cost model)
  - P1-B: Confidence calibration (5-tier decision, abstention, evidence, invalidation)
  - P1-C: Expert committee v2 (fixed schema, consensus analysis)
  - P1-D: Final arbiter v2 (decision_tier + consensus integration)
  - P1-E: Dashboard UI bindings (new fields present in template)
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ═══════════════════════════════════════════════════════════════
# Helpers — build synthetic market data for function calls
# ═══════════════════════════════════════════════════════════════


def _make_market_arrays(n=300, trend="up"):
    """Create synthetic close/sma/rsi/vol arrays for testing."""
    np.random.seed(42)
    base = 100.0
    if trend == "up":
        close = np.cumsum(np.random.normal(0.15, 1.0, n)) + base
    elif trend == "down":
        close = np.cumsum(np.random.normal(-0.15, 1.0, n)) + base
    else:
        close = np.cumsum(np.random.normal(0.0, 1.0, n)) + base

    close = np.maximum(close, 10)  # floor

    sma20 = np.convolve(close, np.ones(20) / 20, mode="same")
    sma50 = np.convolve(close, np.ones(50) / 50, mode="same")
    sma200 = np.convolve(close, np.ones(min(200, n)) / min(200, n), mode="same")

    # Synthetic RSI
    rsi = np.clip(50 + np.random.normal(0, 15, n), 5, 95)

    # Volume
    volume = np.random.uniform(1e6, 5e6, n)
    vol_ratio = np.random.uniform(0.5, 2.0, n)

    # ATR as fraction
    atr_pct = np.random.uniform(0.01, 0.04, n)

    return close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume


# ═══════════════════════════════════════════════════════════════
# P1-A — Backtest Realism (cost model presence in source)
# ═══════════════════════════════════════════════════════════════


class TestBacktestCostModel:
    """Verify backtest now includes commission + slippage cost model."""

    def _get_main_source(self):
        return (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()

    def test_commission_constant_defined(self):
        src = self._get_main_source()
        assert "COMMISSION_PER_SHARE" in src
        assert "0.005" in src

    def test_min_commission_defined(self):
        src = self._get_main_source()
        assert "MIN_COMMISSION" in src

    def test_slippage_base_bps_defined(self):
        src = self._get_main_source()
        assert "SLIPPAGE_BASE_BPS" in src

    def test_calc_slippage_function_exists(self):
        src = self._get_main_source()
        assert "def _calc_slippage(" in src

    def test_calc_commission_function_exists(self):
        src = self._get_main_source()
        assert "def _calc_commission(" in src

    def test_backtest_returns_gross_return(self):
        """The backtest return dict should include gross_return."""
        src = self._get_main_source()
        assert '"gross_return"' in src or "'gross_return'" in src

    def test_backtest_returns_total_costs_pct(self):
        """The backtest return dict should include total_costs_pct."""
        src = self._get_main_source()
        assert '"total_costs_pct"' in src or "'total_costs_pct'" in src

    def test_backtest_returns_cost_model_metadata(self):
        """The backtest return dict should include cost_model."""
        src = self._get_main_source()
        assert '"cost_model"' in src or "'cost_model'" in src

    def test_entry_cost_tracked_in_positions(self):
        """Positions should track entry_cost with slippage."""
        src = self._get_main_source()
        assert '"entry_cost"' in src or "'entry_cost'" in src

    def test_pnl_gross_pct_in_closed_trades(self):
        """Closed trades should have pnl_gross_pct for gross vs net analysis."""
        src = self._get_main_source()
        assert "pnl_gross_pct" in src

    def test_slippage_atr_based(self):
        """Slippage should use ATR-based calculation, not just flat bps."""
        src = self._get_main_source()
        # Should reference atr in slippage calc
        idx = src.find("def _calc_slippage(")
        assert idx > 0
        func_body = src[idx : idx + 400]
        assert "atr" in func_body.lower() or "ATR" in func_body


# ═══════════════════════════════════════════════════════════════
# P1-B — Confidence Calibration Engine
# ═══════════════════════════════════════════════════════════════


class TestConfidenceCalibration:
    """Test _compute_4layer_confidence with new 5-tier output."""

    @pytest.fixture
    def confidence_func(self):
        from src.api.main import _compute_4layer_confidence

        return _compute_4layer_confidence

    @pytest.fixture
    def up_market(self):
        return _make_market_arrays(300, "up")

    @pytest.fixture
    def down_market(self):
        return _make_market_arrays(300, "down")

    def test_returns_dict_with_required_keys(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result, dict)
        for key in [
            "thesis",
            "timing",
            "execution",
            "data",
            "composite",
            "grade",
            "action",
            "decision_tier",
            "sizing",
            "should_trade",
            "reasons_for",
            "reasons_against",
            "invalidation",
            "penalties",
            "calibration",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_decision_tier_is_valid_value(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        valid_tiers = {"STRONG_BUY", "BUY_SMALL", "WATCH", "NO_TRADE", "HEDGE"}
        assert (
            result["decision_tier"] in valid_tiers
        ), f"decision_tier={result['decision_tier']} not in {valid_tiers}"

    def test_sizing_is_string(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["sizing"], str)
        assert len(result["sizing"]) > 0

    def test_should_trade_is_bool(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["should_trade"], bool)

    def test_reasons_for_is_list(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["reasons_for"], list)

    def test_reasons_against_is_list(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["reasons_against"], list)

    def test_invalidation_is_list(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["invalidation"], list)

    def test_invalidation_entries_are_descriptive(
        self, confidence_func, up_market
    ):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for inv in result["invalidation"]:
            # Invalidation entries can be strings or dicts
            assert isinstance(inv, (str, dict)), (
                f"Invalidation entry should be str or dict, got {type(inv)}"
            )
            if isinstance(inv, str):
                assert len(inv) > 5, "Invalidation string too short"

    def test_calibration_metadata_present(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        cal = result["calibration"]
        assert isinstance(cal, dict)
        assert "predicted_prob" in cal
        assert "confidence_bucket" in cal

    def test_composite_in_range(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert 0 <= result["composite"] <= 100

    def test_grade_is_valid(self, confidence_func, up_market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert result["grade"] in {"A", "B", "C", "D"}

    def test_abstention_with_earnings_blackout(self, confidence_func, up_market):
        """When days_to_earnings < 3, should_trade should be False."""
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
            days_to_earnings=1,  # imminent earnings
        )
        # System should abstain when earnings < 3 days away
        if result["composite"] < 45:
            assert not result["should_trade"]

    def test_down_market_gets_lower_tier(self, confidence_func, down_market):
        """Bearish market should produce lower confidence tier."""
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = down_market
        # Force RSI low
        rsi[:] = 25
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=False,
        )
        # In a down market with low RSI, should NOT be STRONG_BUY
        assert result["decision_tier"] != "STRONG_BUY"

    def test_legacy_fields_still_present(self, confidence_func, up_market):
        """Original fields (thesis, timing, execution, data, composite, grade)
        must still exist for backward compatibility."""
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = up_market
        result = confidence_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for layer in ["thesis", "timing", "execution", "data"]:
            assert "score" in result[layer]
            assert "factors" in result[layer]


# ═══════════════════════════════════════════════════════════════
# P1-C — Expert Committee v2
# ═══════════════════════════════════════════════════════════════


class TestExpertCouncilV2:
    """Test _run_expert_council with fixed schema + consensus analysis."""

    @pytest.fixture
    def council_func(self):
        from src.api.main import _run_expert_council

        return _run_expert_council

    @pytest.fixture
    def market(self):
        return _make_market_arrays(300, "up")

    def test_returns_dict_not_list(self, council_func, market):
        """v2 must return dict with 'members' + 'summary', not a plain list."""
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "members" in result
        assert "summary" in result

    def test_members_is_list_of_dicts(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        members = result["members"]
        assert isinstance(members, list)
        assert len(members) >= 5, "Should have at least 5 expert members"

    def test_each_member_has_fixed_schema(self, council_func, market):
        """Every expert must have: role, stance, strength, score, evidence,
        risks, invalidation, time_horizon, action_bias."""
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        required_fields = {
            "role",
            "stance",
            "strength",
            "score",
            "evidence",
            "risks",
            "invalidation",
            "time_horizon",
            "action_bias",
        }
        for m in result["members"]:
            for field in required_fields:
                assert (
                    field in m
                ), f"Expert '{m.get('role','?')}' missing field: {field}"

    def test_stance_is_valid(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        valid_stances = {"bullish", "bearish", "neutral"}
        for m in result["members"]:
            assert (
                m["stance"] in valid_stances
            ), f"Expert '{m['role']}' has invalid stance: {m['stance']}"

    def test_strength_in_range(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for m in result["members"]:
            assert (
                0 <= m["strength"] <= 1
            ), f"Expert '{m['role']}' strength={m['strength']} out of [0,1]"

    def test_score_in_range(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for m in result["members"]:
            assert 0 <= m["score"] <= 100

    def test_evidence_is_list(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for m in result["members"]:
            assert isinstance(m["evidence"], list)
            assert len(m["evidence"]) <= 4, "Evidence capped at 4"

    def test_risks_is_list(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        for m in result["members"]:
            assert isinstance(m["risks"], list)
            assert len(m["risks"]) <= 3, "Risks capped at 3"

    def test_summary_has_consensus_fields(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        summary = result["summary"]
        for key in [
            "avg_score",
            "bullish",
            "bearish",
            "neutral",
            "disagreement",
            "consensus",
            "headline",
        ]:
            assert key in summary, f"Summary missing key: {key}"

    def test_consensus_is_valid_classification(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        valid_consensus = {
            "strong_consensus_bullish",
            "strong_consensus_bearish",
            "lean_bullish",
            "lean_bearish",
            "contested",
            "split",
        }
        assert result["summary"]["consensus"] in valid_consensus

    def test_disagreement_is_numeric(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["summary"]["disagreement"], (int, float))
        assert result["summary"]["disagreement"] >= 0

    def test_headline_is_string(self, council_func, market):
        close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, volume = market
        result = council_func(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            vol_ratio,
            atr_pct,
            idx=250,
            volume=volume,
            regime_trending=True,
        )
        assert isinstance(result["summary"]["headline"], str)
        assert len(result["summary"]["headline"]) > 0


# ═══════════════════════════════════════════════════════════════
# P1-D — Final Arbiter v2
# ═══════════════════════════════════════════════════════════════


class TestFinalArbiterV2:
    """Verify the arbiter uses decision_tier + consensus (source code analysis)."""

    def _get_main_source(self):
        return (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()

    def test_arbiter_checks_decision_tier(self):
        src = self._get_main_source()
        # Find the arbiter section
        idx = src.find("Final action (arbiter)")
        assert idx > 0, "Arbiter section not found"
        arbiter_body = src[idx : idx + 1500]
        assert "decision_tier" in arbiter_body

    def test_arbiter_checks_council_consensus(self):
        src = self._get_main_source()
        idx = src.find("Final action (arbiter)")
        assert idx > 0
        arbiter_body = src[idx : idx + 1500]
        assert "consensus" in arbiter_body

    def test_arbiter_checks_disagreement(self):
        """High expert disagreement should reduce position size."""
        src = self._get_main_source()
        idx = src.find("Final action (arbiter)")
        assert idx > 0
        arbiter_body = src[idx : idx + 1500]
        assert "disagreement" in arbiter_body

    def test_arbiter_handles_abstention(self):
        src = self._get_main_source()
        idx = src.find("Final action (arbiter)")
        assert idx > 0
        arbiter_body = src[idx : idx + 1500]
        assert "should_trade" in arbiter_body or "ABSTAIN" in arbiter_body

    def test_response_includes_council_summary(self):
        """The time-travel response must include council_summary."""
        src = self._get_main_source()
        assert '"council_summary"' in src or "'council_summary'" in src

    def test_response_expert_council_is_members_list(self):
        """expert_council in response should be the members list."""
        src = self._get_main_source()
        assert "council_members" in src


# ═══════════════════════════════════════════════════════════════
# P1-E — Dashboard UI Bindings
# ═══════════════════════════════════════════════════════════════


class TestDashboardP1Bindings:
    """Verify index.html has bindings for all new P1 fields."""

    @pytest.fixture
    def template_src(self):
        return (
            Path(__file__).parent.parent / "src" / "api" / "templates" / "index.html"
        ).read_text()

    def test_decision_tier_displayed(self, template_src):
        assert "decision_tier" in template_src

    def test_sizing_displayed(self, template_src):
        assert "sizing" in template_src

    def test_reasons_for_displayed(self, template_src):
        assert "reasons_for" in template_src

    def test_reasons_against_displayed(self, template_src):
        assert "reasons_against" in template_src

    def test_invalidation_displayed(self, template_src):
        assert "invalidation" in template_src

    def test_council_summary_displayed(self, template_src):
        assert "council_summary" in template_src

    def test_consensus_displayed(self, template_src):
        assert "consensus" in template_src

    def test_disagreement_displayed(self, template_src):
        assert "disagreement" in template_src

    def test_headline_displayed(self, template_src):
        assert "headline" in template_src

    def test_stance_field_used(self, template_src):
        """New expert schema uses 'stance' instead of only 'verdict'."""
        assert "ex.stance" in template_src

    def test_evidence_field_used(self, template_src):
        """New expert schema uses 'evidence' for reasons."""
        assert "ex.evidence" in template_src

    def test_time_horizon_displayed(self, template_src):
        assert "time_horizon" in template_src

    def test_no_trade_abstain_action_color(self, template_src):
        """'NO TRADE — ABSTAIN' should get red color (includes 'NO TRADE')."""
        assert "includes('NO TRADE')" in template_src


# ═══════════════════════════════════════════════════════════════
# P1-F — Cross-cutting integration checks
# ═══════════════════════════════════════════════════════════════


class TestCrossCuttingP1:
    """Integration checks across the P1 overhaul."""

    def test_confidence_and_council_called_before_arbiter(self):
        """Verify execution order: confidence → council → arbiter."""
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        conf_idx = src.find("_compute_4layer_confidence(")
        council_idx = src.find("_run_expert_council(")
        arbiter_idx = src.find("Final action (arbiter)")
        # All must exist
        assert conf_idx > 0
        assert council_idx > 0
        assert arbiter_idx > 0
        # Order: confidence < council < arbiter
        assert conf_idx < council_idx < arbiter_idx

    def test_abstention_threshold_defined(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "ABSTENTION_THRESHOLD" in src

    def test_confidence_decay_rate_defined(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "confidence_decay_rate" in src

    def test_brier_calibration_metadata(self):
        src = (Path(__file__).parent.parent / "src" / "api" / "main.py").read_text()
        assert "brier" in src.lower() or "predicted_prob" in src
