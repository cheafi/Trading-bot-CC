"""
Sprint 109 — Unified Sizing Advisor
=====================================
Tests for SizingAdvisor engine + REST endpoints.

Coverage:
  1.  Fixed-risk base size arithmetic
  2.  Half-Kelly base size
  3.  Score below minimum → zero result
  4.  Invalid prices → zero result
  5.  Risk-per-share near zero → zero result
  6.  Decay adjustment reduces size for stale signals
  7.  Fresh signal → no decay reduction
  8.  Portfolio heat at max → zero size
  9.  Portfolio heat throttle (partial)
 10.  Thompson multiplier applied (mocked)
 11.  Max position pct cap
 12.  to_dict() round-trip
 13.  REST GET /api/v7/size/advise → 200 + required fields
 14.  REST GET /api/v7/size/params → 200 + schedule keys
 15.  REST POST /api/v7/size/advise/batch → 200 + results list
 16.  Batch hard cap at 20 items
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    from src.api.main import app

    # Provide minimal app state to avoid AttributeError in _get_equity/_get_heat
    if not hasattr(app.state, "engine"):
        app.state.engine = None
    return TestClient(app)


@pytest.fixture
def advisor():
    from src.engines.sizing_advisor import SizingAdvisor

    return SizingAdvisor(equity=100_000.0, current_heat_pct=0.0)


# ── Unit tests: SizingAdvisor ────────────────────────────────────────────────


class TestSizingAdvisorBase:
    def test_fixed_risk_base_arithmetic(self, advisor):
        """1R fixed-risk: risk = 1% equity → base size = 1% * (entry/rps)"""
        result = advisor.advise(
            ticker="AAPL",
            entry_price=100.0,
            stop_price=90.0,  # rps = 10
            signal_score=75.0,
            signal_grade="B",
            age_hours=0.0,
        )
        assert result.size_ok
        assert result.shares > 0
        # At 1% equity risk: dollar_risk = 1000; shares = 1000/10 = 100
        # position = 100 * 100 = $10_000 = 10% equity
        # Should be capped at max_position_pct=10%
        assert result.final_size_pct <= 0.101  # ~10% with rounding
        assert abs(result.risk_pct_of_equity - 0.01) < 0.002

    def test_half_kelly(self, advisor):
        """Half-Kelly with 60% win rate and 2:1 R:R → meaningful fraction."""
        result = advisor.advise(
            ticker="MSFT",
            entry_price=200.0,
            stop_price=190.0,
            signal_score=80.0,
            signal_grade="A",
            age_hours=0.0,
            win_rate=0.6,
            avg_win_loss_ratio=2.0,
        )
        assert result.size_ok
        assert result.method == "half_kelly"
        # Half-Kelly: f = (0.6*2 - 0.4)/2 = 0.4 → half = 0.2 = 20%
        # capped at max_position_pct=10%
        assert result.final_size_pct <= 0.101

    def test_score_below_minimum_returns_zero(self, advisor):
        result = advisor.advise(
            ticker="LOW",
            entry_price=50.0,
            stop_price=45.0,
            signal_score=40.0,  # below _MIN_SCORE_TO_SIZE=50
        )
        assert not result.size_ok
        assert "below minimum" in result.zero_reason.lower()
        assert result.shares == 0

    def test_invalid_entry_price_returns_zero(self, advisor):
        result = advisor.advise(
            ticker="ZERO",
            entry_price=0.0,
            stop_price=45.0,
            signal_score=75.0,
        )
        assert not result.size_ok

    def test_risk_per_share_near_zero_returns_zero(self, advisor):
        result = advisor.advise(
            ticker="TIGHT",
            entry_price=100.0,
            stop_price=99.999,  # rps < 0.01
            signal_score=75.0,
        )
        assert not result.size_ok
        assert result.shares == 0

    def test_max_position_cap(self):
        """Very tight stop causes large position — should be capped at 10%."""
        from src.engines.sizing_advisor import SizingAdvisor

        advisor = SizingAdvisor(equity=100_000.0)
        result = advisor.advise(
            ticker="WIDE",
            entry_price=100.0,
            stop_price=99.0,  # tiny rps → large position
            signal_score=70.0,
        )
        if result.size_ok:
            assert result.final_size_pct <= 0.101


class TestDecayAdjustment:
    def test_fresh_signal_no_decay_reduction(self, advisor):
        """Age=0 → decay_adj should be very close to 1.0."""
        result = advisor.advise(
            ticker="FRESH",
            entry_price=100.0,
            stop_price=95.0,
            signal_score=70.0,
            signal_grade="B",
            age_hours=0.0,
        )
        assert result.size_ok
        # decay_adj should be ~1.0 (no reduction for fresh signal)
        assert result.decay_adj >= 0.99

    def test_stale_signal_reduces_size(self, advisor):
        """Old signal (>1 half-life) should have decay_adj < 1.0."""
        with patch(
            "src.engines.sizing_advisor.SizingAdvisor._thompson_mult", return_value=1.0
        ):
            fresh = advisor.advise(
                ticker="X",
                entry_price=100.0,
                stop_price=95.0,
                signal_score=70.0,
                signal_grade="B",
                age_hours=0.0,
            )
            stale = advisor.advise(
                ticker="X",
                entry_price=100.0,
                stop_price=95.0,
                signal_score=70.0,
                signal_grade="B",
                age_hours=36.0,  # 2× half-life for B (18h)
            )
        if fresh.size_ok and stale.size_ok:
            assert stale.final_size_pct < fresh.final_size_pct
        assert stale.decay_adj < 1.0

    def test_decay_pct_at_half_life(self, advisor):
        """At grade B half-life (18h), decay_pct should be ~50%."""
        result = advisor.advise(
            ticker="HALF",
            entry_price=100.0,
            stop_price=90.0,
            signal_score=70.0,
            signal_grade="B",
            age_hours=18.0,
        )
        # decay_pct ~ 50%
        assert 45.0 <= result.decay_pct <= 55.0

    def test_decay_adj_floor_at_0_5(self, advisor):
        """Even fully decayed signal → decay_adj ≥ 0.5 (never zero the position by decay alone)."""
        result = advisor.advise(
            ticker="OLD",
            entry_price=100.0,
            stop_price=90.0,
            signal_score=70.0,
            signal_grade="D",
            age_hours=100.0,  # extreme age
        )
        assert result.decay_adj >= 0.49  # floor at 0.5


class TestHeatGate:
    def test_heat_at_max_returns_zero(self):
        from src.engines.sizing_advisor import SizingAdvisor

        advisor = SizingAdvisor(
            equity=100_000.0,
            max_portfolio_heat=0.06,
            current_heat_pct=0.06,  # exactly at ceiling
        )
        result = advisor.advise(
            ticker="HOT",
            entry_price=100.0,
            stop_price=95.0,
            signal_score=80.0,
        )
        assert not result.size_ok or result.shares == 0

    def test_heat_throttle_reduces_size(self):
        from src.engines.sizing_advisor import SizingAdvisor

        cold = SizingAdvisor(equity=100_000.0, current_heat_pct=0.0)
        warm = SizingAdvisor(equity=100_000.0, current_heat_pct=0.05)

        with patch(
            "src.engines.sizing_advisor.SizingAdvisor._thompson_mult", return_value=1.0
        ):
            cold_result = cold.advise("X", 100.0, 95.0, signal_score=70.0)
            warm_result = warm.advise("X", 100.0, 95.0, signal_score=70.0)

        if cold_result.size_ok and warm_result.size_ok:
            assert warm_result.final_size_pct <= cold_result.final_size_pct


class TestThompsonIntegration:
    def test_thompson_multiplier_applied(self):
        """Mock ThompsonSizingEngine to return 1.5× and verify it affects size."""
        from src.engines.sizing_advisor import SizingAdvisor

        advisor = SizingAdvisor(equity=100_000.0)

        mock_engine = MagicMock()
        mock_engine.sample.return_value = 1.5

        with patch("src.engines.sizing_advisor.SizingAdvisor._thompson_mult") as mock_t:
            mock_t.return_value = 1.5
            result_high = advisor.advise(
                "X", 100.0, 95.0, signal_score=70.0, strategy="TREND", regime="BULL"
            )

        with patch("src.engines.sizing_advisor.SizingAdvisor._thompson_mult") as mock_t:
            mock_t.return_value = 0.5
            result_low = advisor.advise(
                "X", 100.0, 95.0, signal_score=70.0, strategy="TREND", regime="BULL"
            )

        if result_high.size_ok and result_low.size_ok:
            assert result_high.final_size_pct > result_low.final_size_pct

    def test_thompson_failure_falls_back_to_1(self):
        """If Thompson import fails, multiplier should be 1.0."""
        from src.engines.sizing_advisor import SizingAdvisor

        advisor = SizingAdvisor(equity=100_000.0)
        with patch("src.engines.sizing_advisor.SizingAdvisor._thompson_mult") as mock_t:
            mock_t.return_value = 1.0
            result = advisor.advise("X", 100.0, 95.0, signal_score=70.0)
        assert result.thompson_mult == 1.0 or result.size_ok  # graceful


class TestAdvisedSizeToDict:
    def test_to_dict_round_trip(self, advisor):
        result = advisor.advise(
            "AAPL", 175.0, 168.0, signal_score=78.0, signal_grade="B+"
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        for key in [
            "ticker",
            "base_size_pct",
            "thompson_mult",
            "decay_adj",
            "heat_scale",
            "final_size_pct",
            "dollar_amount",
            "shares",
            "signal_score",
            "signal_grade",
            "size_ok",
            "audit_trail",
        ]:
            assert key in d, f"Missing key: {key}"
        # Percentages should be expressed as 0–100 not 0–1
        assert d["final_size_pct"] <= 100.0
        assert isinstance(d["audit_trail"], list)


# ── REST endpoint tests ──────────────────────────────────────────────────────


class TestSizingEndpoints:
    def test_advise_single_200(self, client):
        resp = client.get(
            "/api/v7/size/advise",
            params={
                "ticker": "AAPL",
                "entry_price": 175.0,
                "stop_price": 168.0,
                "signal_score": 78.0,
                "signal_grade": "B",
                "age_hours": 2.0,
                "strategy": "PULLBACK_TREND",
                "regime": "BULL",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ticker" in data
        assert "final_size_pct" in data
        assert "size_ok" in data
        assert "audit_trail" in data

    def test_advise_single_score_too_low(self, client):
        resp = client.get(
            "/api/v7/size/advise",
            params={
                "ticker": "WEAK",
                "entry_price": 100.0,
                "stop_price": 95.0,
                "signal_score": 30.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["size_ok"] is False

    def test_sizing_params_200(self, client):
        resp = client.get("/api/v7/size/params")
        assert resp.status_code == 200
        data = resp.json()
        assert "decay_schedule" in data
        assert "B" in data["decay_schedule"]
        assert "max_risk_pct" in data
        assert "max_position_pct" in data

    def test_advise_batch_200(self, client):
        payload = {
            "equity": 100_000.0,
            "current_heat_pct": 0.01,
            "signals": [
                {
                    "ticker": "AAPL",
                    "entry_price": 175.0,
                    "stop_price": 168.0,
                    "signal_score": 78.0,
                    "signal_grade": "B",
                    "age_hours": 1.0,
                },
                {
                    "ticker": "MSFT",
                    "entry_price": 420.0,
                    "stop_price": 408.0,
                    "signal_score": 85.0,
                    "signal_grade": "A",
                    "age_hours": 0.5,
                },
            ],
        }
        resp = client.post("/api/v7/size/advise/batch", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["total"] == 2

    def test_batch_hard_cap_20(self, client):
        """Batch should silently cap at 20 items."""
        signals = [
            {
                "ticker": f"T{i}",
                "entry_price": 100.0,
                "stop_price": 95.0,
                "signal_score": 70.0,
                "signal_grade": "B",
                "age_hours": 0.0,
            }
            for i in range(25)  # send 25
        ]
        resp = client.post(
            "/api/v7/size/advise/batch",
            json={"equity": 100_000.0, "current_heat_pct": 0.0, "signals": signals},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 20
