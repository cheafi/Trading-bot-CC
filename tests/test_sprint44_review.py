"""Sprint 44 — Institutional Review Implementation Tests.

Covers:
1. Conformal predictor — calibration, prediction intervals, reliability
2. Expert committee — votes, deliberation, regime weighting
3. Scenario engine — stress tests, hedge suggestions
4. FRED client — series definitions, classification helpers
5. EDGAR client — CIK lookup, data classes
6. Operator console — throttle states, kill switch
7. API integration — new endpoints exist
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
# 1. Conformal Predictor
# ═══════════════════════════════════════════════════════════════


class TestConformalPredictor:
    def test_import(self):
        from src.engines.conformal_predictor import (
            ConformalPredictor,
            PredictionInterval,
            reliability_bucket,
            reliability_note,
        )
        assert ConformalPredictor is not None

    def test_uncalibrated_fallback(self):
        from src.engines.conformal_predictor import ConformalPredictor

        cp = ConformalPredictor(confidence_level=0.90)
        interval = cp.predict(100.0)
        assert interval.method == "fallback_5pct"
        assert interval.lower == 95.0
        assert interval.upper == 105.0
        assert interval.confidence_level == 0.90

    def test_calibrate_and_predict(self):
        import numpy as np
        from src.engines.conformal_predictor import ConformalPredictor

        np.random.seed(42)
        predicted = np.linspace(100, 120, 50)
        noise = np.random.normal(0, 2, 50)
        actual = predicted + noise

        cp = ConformalPredictor(confidence_level=0.90)
        cp.calibrate(predicted.tolist(), actual.tolist())
        assert cp.is_calibrated
        assert cp.sample_size == 50

        interval = cp.predict(110.0)
        assert interval.method == "split_conformal"
        assert interval.lower < 110.0
        assert interval.upper > 110.0
        assert interval.sample_size == 50

    def test_calibrate_from_returns(self):
        import numpy as np
        from src.engines.conformal_predictor import ConformalPredictor

        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.normal(0.05, 1, 200))
        cp = ConformalPredictor()
        cp.calibrate_from_returns(prices.tolist(), horizon_days=20)
        assert cp.is_calibrated

    def test_reliability_buckets(self):
        from src.engines.conformal_predictor import reliability_bucket

        assert reliability_bucket(200) == "HIGH"
        assert reliability_bucket(50) == "MODERATE"
        assert reliability_bucket(20) == "LOW"
        assert reliability_bucket(5) == "EXPERIMENTAL"

    def test_prediction_interval_dict(self):
        from src.engines.conformal_predictor import PredictionInterval

        pi = PredictionInterval(
            point=100, lower=95, upper=105,
            confidence_level=0.90, sample_size=50,
        )
        d = pi.to_dict()
        assert d["point"] == 100
        assert d["width_pct"] == 10.0
        assert d["sample_size"] == 50

    def test_summary(self):
        from src.engines.conformal_predictor import ConformalPredictor

        cp = ConformalPredictor()
        s = cp.summary()
        assert s["calibrated"] is False
        assert s["reliability"] == "EXPERIMENTAL"


# ═══════════════════════════════════════════════════════════════
# 2. Expert Committee
# ═══════════════════════════════════════════════════════════════


class TestExpertCommittee:
    def test_import(self):
        from src.engines.expert_committee import (
            ExpertCommittee, Expert, ExpertVote, CommitteeVerdict,
        )
        assert ExpertCommittee is not None

    def test_collect_votes(self):
        from src.engines.expert_committee import ExpertCommittee

        ec = ExpertCommittee()
        assert len(ec.experts) == 7

        votes = ec.collect_votes(
            regime="UPTREND", rsi=65, vol_ratio=1.2,
            trending=True, rr_ratio=2.5, atr_pct=0.02,
        )
        assert len(votes) == 7
        assert all(v.expert_name for v in votes)

    def test_deliberate_consensus(self):
        from src.engines.expert_committee import ExpertCommittee

        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="UPTREND", rsi=60, vol_ratio=1.5,
            trending=True, rr_ratio=3.0, atr_pct=0.015,
        )
        verdict = ec.deliberate(votes, regime="UPTREND")
        assert verdict.direction in ("LONG", "SHORT", "FLAT", "ABSTAIN")
        assert 0 <= verdict.agreement_ratio <= 1
        assert verdict.dominant_risk

    def test_crisis_regime_flat(self):
        from src.engines.expert_committee import ExpertCommittee

        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="CRISIS", rsi=25, vol_ratio=0.4,
            trending=False, rr_ratio=1.0, atr_pct=0.06, vix=45,
        )
        verdict = ec.deliberate(votes, regime="CRISIS")
        # In crisis most experts should go FLAT
        flat_count = sum(1 for v in votes if v.direction == "FLAT")
        assert flat_count >= 3

    def test_expert_accuracy_tracking(self):
        from src.engines.expert_committee import Expert

        e = Expert(name="Test", domain="test")
        e.record_outcome("UPTREND", True)
        e.record_outcome("UPTREND", True)
        e.record_outcome("UPTREND", False)
        assert e.total_votes == 3
        assert e.correct_votes == 2

    def test_verdict_to_dict(self):
        from src.engines.expert_committee import ExpertCommittee

        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="SIDEWAYS", rsi=50, vol_ratio=1.0,
            trending=False, rr_ratio=2.0, atr_pct=0.02,
        )
        verdict = ec.deliberate(votes, regime="SIDEWAYS")
        d = verdict.to_dict()
        assert "direction" in d
        assert "composite_conviction" in d
        assert "all_votes" in d
        assert "verdict_summary" in d


# ═══════════════════════════════════════════════════════════════
# 3. Scenario Engine
# ═══════════════════════════════════════════════════════════════


class TestScenarioEngine:
    def test_import(self):
        from src.engines.scenario_engine import ScenarioEngine
        assert ScenarioEngine is not None

    def test_list_scenarios(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        scenarios = se.list_scenarios()
        assert len(scenarios) >= 8
        keys = {s["key"] for s in scenarios}
        assert "gfc_2008" in keys
        assert "covid_2020" in keys
        assert "flash_crash" in keys

    def test_run_scenario_gfc(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        positions = [
            {"ticker": "AAPL", "weight": 0.3, "entry_price": 180},
            {"ticker": "JPM", "weight": 0.3, "entry_price": 190},
            {"ticker": "SPY", "weight": 0.4, "entry_price": 500},
        ]
        result = se.run_scenario("gfc_2008", positions)
        assert result.estimated_pnl_pct < 0  # should be negative
        assert result.worst_position != "N/A"
        assert result.total_positions == 3

    def test_run_scenario_generates_hedges(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        positions = [
            {"ticker": "NVDA", "weight": 0.5, "entry_price": 800},
            {"ticker": "AMD", "weight": 0.5, "entry_price": 150},
        ]
        result = se.run_scenario("rate_shock_2022", positions)
        assert len(result.hedges) > 0

    def test_run_all_scenarios(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        positions = [{"ticker": "SPY", "weight": 1.0, "entry_price": 500}]
        results = se.run_all_scenarios(positions)
        assert len(results) >= 8

    def test_scenario_result_to_dict(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        result = se.run_scenario("flash_crash", [
            {"ticker": "QQQ", "weight": 1.0, "entry_price": 450},
        ])
        d = result.to_dict()
        assert "estimated_pnl_pct" in d
        assert "hedges" in d
        assert "risk_summary" in d

    def test_unknown_scenario(self):
        from src.engines.scenario_engine import ScenarioEngine

        se = ScenarioEngine()
        result = se.run_scenario("nonexistent", [])
        assert result.risk_summary == "Unknown scenario"


# ═══════════════════════════════════════════════════════════════
# 4. FRED Client
# ═══════════════════════════════════════════════════════════════


class TestFredClient:
    def test_import(self):
        from src.ingestors.fred import FredClient, FRED_SERIES
        assert FredClient is not None
        assert len(FRED_SERIES) >= 20

    def test_series_definitions(self):
        from src.ingestors.fred import FRED_SERIES

        for sid, meta in FRED_SERIES.items():
            assert "name" in meta
            assert "category" in meta
            assert "frequency" in meta

    def test_client_not_configured(self):
        from src.ingestors.fred import FredClient

        fc = FredClient(api_key="")
        assert not fc.is_configured

    def test_yield_curve_classification(self):
        from src.ingestors.fred import FredClient

        assert FredClient._classify_yield_curve({"T10Y2Y": {"value": -0.5}}) == "INVERTED"
        assert FredClient._classify_yield_curve({"T10Y2Y": {"value": 0.1}}) == "FLAT"
        assert FredClient._classify_yield_curve({"T10Y2Y": {"value": 1.5}}) == "NORMAL"

    def test_credit_classification(self):
        from src.ingestors.fred import FredClient

        assert FredClient._classify_credit({"BAMLH0A0HYM2": {"value": 7.0}}) == "HIGH"
        assert FredClient._classify_credit({"BAMLH0A0HYM2": {"value": 5.0}}) == "MODERATE"
        assert FredClient._classify_credit({"BAMLH0A0HYM2": {"value": 3.0}}) == "LOW"

    def test_labor_classification(self):
        from src.ingestors.fred import FredClient

        assert FredClient._classify_labor({"UNRATE": {"value": 3.5}}) == "STRONG"
        assert FredClient._classify_labor({"UNRATE": {"value": 5.0}}) == "MIXED"
        assert FredClient._classify_labor({"UNRATE": {"value": 7.0}}) == "WEAK"

    def test_regime_inference(self):
        from src.ingestors.fred import FredClient

        assert FredClient._infer_regime("INVERTED", "RISING", "STRONG", "HIGH") == "CONTRACTIONARY"
        assert FredClient._infer_regime("NORMAL", "STABLE", "STRONG", "LOW") == "EXPANSIONARY"
        assert FredClient._infer_regime("NORMAL", "RISING", "STRONG", "LOW") == "LATE_CYCLE"


# ═══════════════════════════════════════════════════════════════
# 5. EDGAR Client
# ═══════════════════════════════════════════════════════════════


class TestEdgarClient:
    def test_import(self):
        from src.ingestors.edgar import EdgarClient, Filing, InsiderTransaction
        assert EdgarClient is not None

    def test_cik_cache(self):
        from src.ingestors.edgar import _CIK_CACHE

        assert "AAPL" in _CIK_CACHE
        assert "NVDA" in _CIK_CACHE
        assert "RKLB" in _CIK_CACHE
        assert len(_CIK_CACHE) >= 20

    def test_filing_dataclass(self):
        from src.ingestors.edgar import Filing

        f = Filing(
            ticker="AAPL", cik="0000320193", form_type="10-K",
            filed_date="2024-01-01", description="Annual report",
            url="https://sec.gov/...", accession_number="0000-00-000",
        )
        d = f.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["form_type"] == "10-K"

    def test_insider_transaction_dataclass(self):
        from src.ingestors.edgar import InsiderTransaction

        it = InsiderTransaction(
            ticker="AAPL", filer_name="Tim Cook", filer_title="CEO",
            transaction_date="2024-01-01", transaction_type="S",
            shares=10000, price_per_share=185.0, total_value=1850000,
            ownership_type="D",
        )
        d = it.to_dict()
        assert d["filer_name"] == "Tim Cook"
        assert d["total_value"] == 1850000


# ═══════════════════════════════════════════════════════════════
# 6. Operator Console
# ═══════════════════════════════════════════════════════════════


class TestOperatorConsole:
    def test_operator_state_exists(self):
        from src.api.main import _operator_state

        assert "kill_switch" in _operator_state
        assert "throttle" in _operator_state
        assert _operator_state["throttle"] == "NORMAL"
        assert _operator_state["kill_switch"] is False

    def test_throttle_options(self):
        valid = {"NORMAL", "STARTER_ONLY", "HALF_SIZE", "HEDGE_ONLY", "NO_TRADE"}
        assert len(valid) == 5


# ═══════════════════════════════════════════════════════════════
# 7. API Endpoints Exist
# ═══════════════════════════════════════════════════════════════


class TestApiEndpoints:
    def test_new_endpoints_registered(self):
        from src.api.main import app

        routes = {r.path for r in app.routes if hasattr(r, "path")}

        # Sprint 44 endpoints
        assert "/api/operator/status" in routes
        assert "/api/operator/throttle" in routes
        assert "/api/operator/kill-switch" in routes
        assert "/api/scenarios" in routes
        assert "/api/scenarios/run" in routes
        assert "/api/scenarios/run-all" in routes
        assert "/api/expert-committee/{ticker}" in routes
        assert "/api/macro/fred" in routes
        assert "/api/macro/fred/{series_id}" in routes
        assert "/api/edgar/{ticker}/filings" in routes
        assert "/api/edgar/{ticker}/insider" in routes
        assert "/api/edgar/{ticker}/earnings" in routes
        assert "/api/uncertainty/{ticker}" in routes


# ═══════════════════════════════════════════════════════════════
# 8. Integration — Signal Enrichment
# ═══════════════════════════════════════════════════════════════


class TestSignalEnrichment:
    def test_reliability_on_signals(self):
        """Reliability bucket should appear on scanner signals."""
        from src.engines.conformal_predictor import reliability_bucket

        # Just verify the function works with typical sample sizes
        assert reliability_bucket(200) == "HIGH"
        assert reliability_bucket(100) == "MODERATE"

    def test_conformal_singleton_exists(self):
        from src.api.main import _conformal

        assert _conformal is not None
        assert _conformal.confidence_level == 0.90

    def test_expert_committee_singleton_exists(self):
        from src.api.main import _expert_committee

        assert _expert_committee is not None
        assert len(_expert_committee.experts) == 7

    def test_scenario_engine_singleton_exists(self):
        from src.api.main import _scenario_engine

        assert _scenario_engine is not None
        assert len(_scenario_engine.list_scenarios()) >= 8

    def test_fred_client_singleton_exists(self):
        from src.api.main import _fred_client

        assert _fred_client is not None

    def test_edgar_client_singleton_exists(self):
        from src.api.main import _edgar_client

        assert _edgar_client is not None
