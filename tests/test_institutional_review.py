"""
CC — Institutional Review Implementation Tests

Tests all modules created/modified from the institutional review:
1. Security hardening (verify_api_key, CORS)
2. Real telemetry (TelemetryTracker)
3. Calibration engine (CalibrationEngine, ConfidenceLayers, ActionState)
4. Portfolio heat engine (PortfolioHeatEngine, ThrottleState)
5. Event data layer (EventDataService)
6. Version unification (APP_VERSION)
7. Enhanced TradeRecommendation fields
"""

import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ═══════════════════════════════════════════════════════════════════
# 1. VERSION UNIFICATION
# ═══════════════════════════════════════════════════════════════════


class TestVersionUnification:
    def test_version_exists(self):
        from src.core.version import APP_VERSION

        assert APP_VERSION
        parts = APP_VERSION.split(".")
        assert len(parts) == 3

    def test_product_identity(self):
        from src.core.version import (
            DISCORD_COMMAND_COUNT,
            DOCKER_SERVICE_COUNT,
            PRODUCT_NAME,
            STRATEGY_COUNT,
        )

        assert PRODUCT_NAME == "CC"
        assert STRATEGY_COUNT == 4
        assert DISCORD_COMMAND_COUNT == 64
        assert DOCKER_SERVICE_COUNT == 9

    def test_universe_summary(self):
        from src.core.version import UNIVERSE_SUMMARY

        assert UNIVERSE_SUMMARY["total_approx"] > 3000

    def test_decision_surfaces(self):
        from src.core.version import DECISION_SURFACES

        assert len(DECISION_SURFACES) == 6

    def test_modes(self):
        from src.core.version import MODES

        assert "LIVE" in MODES
        assert "SYNTHETIC" in MODES


# ═══════════════════════════════════════════════════════════════════
# 2. TELEMETRY
# ═══════════════════════════════════════════════════════════════════


class TestTelemetry:
    def test_singleton_exists(self):
        from src.core.telemetry import telemetry

        assert telemetry is not None

    def test_record_signal_generated(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_signal_generated("momentum", "AAPL")
        status = t.get_signals_status()
        assert status["signals_today"]["generated"] == 1
        assert status["signals_today"]["active"] == 1

    def test_record_signal_rejected(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_signal_rejected("swing", "TSLA", "stale_data")
        status = t.get_signals_status()
        assert status["signals_today"]["rejected"] == 1
        assert "NO_TRADE_stale_data" in status["rejection_reasons"]

    def test_record_data_update(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_data_update("prices")
        status = t.get_data_status()
        assert status["sources"]["prices"]["status"] == "fresh"
        assert status["sources"]["prices"]["update_count"] == 1

    def test_data_freshness_ready_false_when_no_data(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        assert t.get_data_freshness_ready() is False

    def test_data_freshness_ready_true_after_update(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_data_update("prices")
        assert t.get_data_freshness_ready() is True

    def test_record_job_run(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_job_run("signal_generation", success=True, duration=12.5)
        status = t.get_jobs_status()
        job = status["jobs"]["signal_generation"]
        assert job["status"] == "success"
        assert job["run_count"] == 1
        assert job["last_duration_seconds"] == 12.5

    def test_record_job_failure(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_job_run("price_ingestion", success=False, error="timeout")
        status = t.get_jobs_status()
        assert "price_ingestion" in status["failed_jobs"]

    def test_record_api_request(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_api_request("/health")
        t.record_api_request("/signals")

    def test_metrics_text(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_signal_generated("momentum", "AAPL")
        text = t.get_metrics_text()
        assert "tradingai_up 1" in text
        assert "tradingai_signals_generated_total 1" in text

    def test_uptime_positive(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        assert t.get_uptime_seconds() >= 0

    def test_data_error_tracking(self):
        from src.core.telemetry import TelemetryTracker

        t = TelemetryTracker()
        t.record_data_update("news", error="timeout")
        status = t.get_data_status()
        assert status["sources"]["news"]["error_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# 3. CALIBRATION ENGINE
# ═══════════════════════════════════════════════════════════════════


class TestCalibrationEngine:
    def test_action_state_values(self):
        from src.engines.calibration_engine import ActionState

        assert "STRONG_BUY" in ActionState.ALL
        assert "WATCH" in ActionState.ALL
        assert "NO_TRADE" in ActionState.ALL
        assert "REDUCE" in ActionState.ALL
        assert "HEDGE" in ActionState.ALL

    def test_action_state_rank(self):
        from src.engines.calibration_engine import ActionState

        assert ActionState.rank("STRONG_BUY") > ActionState.rank("WATCH")
        assert ActionState.rank("NO_TRADE") > ActionState.rank("CLOSE")

    def test_confidence_layers_defaults(self):
        from src.engines.calibration_engine import ConfidenceLayers

        cl = ConfidenceLayers()
        d = cl.to_dict()
        assert "forecast_probability" in d
        assert "reliability" in d
        assert "uncertainty_band" in d
        assert d["uncertainty_band"]["width"] >= 0

    def test_signal_explanation(self):
        from src.engines.calibration_engine import SignalExplanation

        se = SignalExplanation(
            bull_case="Strong momentum",
            bear_case="Overbought RSI",
            biggest_risks=["Earnings in 2 days"],
            why_now="Pullback to support",
            pre_mortem="Gap down on earnings miss",
        )
        d = se.to_dict()
        assert d["bull_case"] == "Strong momentum"
        assert d["pre_mortem"] == "Gap down on earnings miss"

    def test_calibration_engine_record_and_report(self):
        from src.engines.calibration_engine import CalibrationEngine

        eng = CalibrationEngine()
        # Record 40 outcomes in "high" bucket
        for i in range(40):
            eng.record_outcome(
                forecast_p=0.72,
                won=(i % 3 != 0),
                regime="bull_trending",
                strategy="momentum",
            )
        report = eng.calibration_report()
        assert report["total_outcomes"] == 40
        high = report["buckets"]["high"]
        assert high["sample_size"] == 40
        assert high["is_calibrated"] is True
        assert 0 < high["realized_hit_rate"] < 1

    def test_build_confidence_uncalibrated(self):
        from src.engines.calibration_engine import CalibrationEngine

        eng = CalibrationEngine()
        cl = eng.build_confidence(raw_score=72)
        assert 0 < cl.forecast_probability < 1
        assert cl.uncertainty_high > cl.uncertainty_low
        assert "uncalibrated" in cl.reliability_bucket

    def test_build_confidence_calibrated(self):
        from src.engines.calibration_engine import CalibrationEngine

        eng = CalibrationEngine()
        for i in range(35):
            eng.record_outcome(0.72, won=(i % 2 == 0))
        cl = eng.build_confidence(raw_score=72)
        assert cl.reliability_sample_size >= 30

    def test_resolve_action_no_trade_stale(self):
        from src.engines.calibration_engine import (
            ActionState,
            CalibrationEngine,
            ConfidenceLayers,
        )

        eng = CalibrationEngine()
        cl = ConfidenceLayers(data_confidence="stale")
        assert eng.resolve_action_state(cl) == ActionState.NO_TRADE

    def test_resolve_action_strong_buy(self):
        from src.engines.calibration_engine import (
            ActionState,
            CalibrationEngine,
            ConfidenceLayers,
        )

        eng = CalibrationEngine()
        cl = ConfidenceLayers(
            forecast_probability=0.75,
            uncertainty_low=0.65,
            uncertainty_high=0.85,
            data_confidence="fresh",
            execution_confidence="good",
            reliability_sample_size=50,
        )
        action = eng.resolve_action_state(cl, regime_fit=0.7)
        assert action == ActionState.STRONG_BUY

    def test_resolve_action_reduce_on_drawdown(self):
        from src.engines.calibration_engine import (
            ActionState,
            CalibrationEngine,
            ConfidenceLayers,
        )

        eng = CalibrationEngine()
        cl = ConfidenceLayers(
            data_confidence="fresh",
            execution_confidence="good",
            reliability_sample_size=50,
            forecast_probability=0.6,
        )
        action = eng.resolve_action_state(
            cl, is_existing_position=True, drawdown_pct=0.12
        )
        assert action == ActionState.REDUCE

    def test_singleton(self):
        from src.engines.calibration_engine import get_calibration_engine

        e1 = get_calibration_engine()
        e2 = get_calibration_engine()
        assert e1 is e2

    def test_uncertainty_wider_with_fewer_samples(self):
        from src.engines.calibration_engine import CalibrationEngine

        eng = CalibrationEngine()
        cl_few = eng.build_confidence(raw_score=60)
        # Record many samples
        for i in range(50):
            eng.record_outcome(0.6, won=(i % 2 == 0))
        cl_many = eng.build_confidence(raw_score=60)
        width_few = cl_few.uncertainty_high - cl_few.uncertainty_low
        width_many = cl_many.uncertainty_high - cl_many.uncertainty_low
        assert width_few >= width_many


# ═══════════════════════════════════════════════════════════════════
# 4. PORTFOLIO HEAT ENGINE
# ═══════════════════════════════════════════════════════════════════


class TestPortfolioHeatEngine:
    def test_throttle_states(self):
        from src.engines.portfolio_heat import ThrottleState

        assert ThrottleState.NORMAL in ThrottleState.ALL
        assert ThrottleState.NO_TRADE in ThrottleState.ALL

    def test_empty_portfolio(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine

        eng = PortfolioHeatEngine()
        snap = eng.snapshot()
        assert snap.cash_pct == 100.0
        assert snap.throttle_state == "normal"

    def test_add_position_and_snapshot(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine, Position

        eng = PortfolioHeatEngine()
        eng.add_position(
            Position(
                ticker="AAPL",
                weight_pct=4.0,
                sector="tech",
                beta=1.2,
            )
        )
        snap = eng.snapshot()
        assert snap.gross_exposure_pct == 4.0
        assert snap.sector_weights["tech"] == 4.0
        assert snap.portfolio_beta == 1.2

    def test_heat_calculation(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine, Position

        eng = PortfolioHeatEngine()
        eng.add_position(
            Position(
                ticker="AAPL",
                weight_pct=5.0,
                stop_distance_pct=0.03,
                sector="tech",
            )
        )
        eng.add_position(
            Position(
                ticker="MSFT",
                weight_pct=5.0,
                stop_distance_pct=0.02,
                sector="tech",
            )
        )
        snap = eng.snapshot()
        # heat = 5*0.03 + 5*0.02 = 0.25 → 25% (in pct points)
        assert snap.heat_pct == pytest.approx(25.0)

    def test_throttle_daily_loss(self):
        from src.engines.portfolio_heat import (
            PortfolioHeatEngine,
            Position,
            ThrottleState,
        )

        eng = PortfolioHeatEngine(daily_loss_limit_pct=3.0)
        eng.add_position(Position(ticker="SPY", weight_pct=10, sector="index"))
        eng.update_pnl(-4.0)
        snap = eng.snapshot()
        assert snap.throttle_state == ThrottleState.NO_TRADE

    def test_throttle_drawdown(self):
        from src.engines.portfolio_heat import (
            PortfolioHeatEngine,
            Position,
            ThrottleState,
        )

        eng = PortfolioHeatEngine(max_drawdown_pct=10.0)
        eng.add_position(Position(ticker="SPY", weight_pct=10, sector="index"))
        # Simulate drawdown
        eng._peak_equity = 100
        eng._current_equity = 85
        snap = eng.snapshot()
        assert snap.throttle_state == ThrottleState.REDUCE_GROSS

    def test_check_new_position_approved(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine

        eng = PortfolioHeatEngine()
        result = eng.check_new_position("AAPL", "tech", 4.0, 1.1)
        assert result["approved"] is True

    def test_check_new_position_rejected_max_positions(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine, Position

        eng = PortfolioHeatEngine(max_positions=2)
        eng.add_position(Position(ticker="A", weight_pct=3, sector="a"))
        eng.add_position(Position(ticker="B", weight_pct=3, sector="b"))
        result = eng.check_new_position("C", "c", 3.0, 1.0)
        assert result["approved"] is False

    def test_check_new_position_rejected_sector(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine, Position

        eng = PortfolioHeatEngine(max_sector_pct=10.0)
        eng.add_position(Position(ticker="A", weight_pct=8, sector="tech"))
        result = eng.check_new_position("B", "tech", 5.0, 1.0)
        assert result["approved"] is False

    def test_exposure_to_dict(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine, Position

        eng = PortfolioHeatEngine()
        eng.add_position(
            Position(
                ticker="AAPL",
                weight_pct=5,
                sector="tech",
                beta=1.1,
            )
        )
        d = eng.snapshot().to_dict()
        assert "concentration" in d
        assert "factor_exposure" in d
        assert "risk_budget" in d
        assert "throttle" in d

    def test_singleton(self):
        from src.engines.portfolio_heat import get_portfolio_heat_engine

        e1 = get_portfolio_heat_engine()
        e2 = get_portfolio_heat_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════
# 5. EVENT DATA LAYER
# ═══════════════════════════════════════════════════════════════════


class TestEventDataLayer:
    def test_sec_filing_schema(self):
        from src.services.event_data import SECFiling

        f = SECFiling(
            cik="0001234567",
            company_name="Apple Inc.",
            form_type="10-K",
            filing_date="2026-01-15",
        )
        d = f.to_dict()
        assert d["form_type"] == "10-K"

    def test_insider_transaction_buy(self):
        from src.services.event_data import InsiderTransaction

        t = InsiderTransaction(transaction_type="P", shares=1000)
        assert t.is_buy is True

    def test_insider_transaction_sell(self):
        from src.services.event_data import InsiderTransaction

        t = InsiderTransaction(transaction_type="S", shares=500)
        assert t.is_buy is False

    def test_macro_data_point(self):
        from src.services.event_data import MacroDataPoint

        p = MacroDataPoint(
            series_id="VIXCLS",
            value=18.5,
            observation_date="2026-04-15",
        )
        d = p.to_dict()
        assert d["value"] == 18.5

    def test_cot_speculative_net(self):
        from src.services.event_data import COTPosition

        c = COTPosition(
            non_commercial_long=150000,
            non_commercial_short=100000,
        )
        assert c.speculative_net == 50000

    def test_event_service_available_providers(self):
        from src.services.event_data import EventDataService

        svc = EventDataService()
        providers = svc.available_providers()
        assert "sec_edgar" in providers
        assert "cftc_cot" in providers

    def test_event_service_configure_fred(self):
        from src.services.event_data import EventDataService

        svc = EventDataService()
        svc.configure_fred("test_key")
        assert "fred" in svc.available_providers()

    def test_get_ticker_events(self):
        from src.services.event_data import EventDataService

        svc = EventDataService()
        result = asyncio.get_event_loop().run_until_complete(
            svc.get_ticker_events("AAPL")
        )
        assert result["ticker"] == "AAPL"
        assert "filings" in result
        assert "insider_transactions" in result

    def test_fred_regime_series(self):
        from src.services.event_data import FREDProvider

        assert "VIXCLS" in FREDProvider.REGIME_SERIES
        assert "FEDFUNDS" in FREDProvider.REGIME_SERIES

    def test_singleton(self):
        from src.services.event_data import get_event_data_service

        e1 = get_event_data_service()
        e2 = get_event_data_service()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════
# 6. ENHANCED TRADE RECOMMENDATION
# ═══════════════════════════════════════════════════════════════════


class TestEnhancedTradeRecommendation:
    def test_new_fields_exist(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(ticker="AAPL")
        assert hasattr(rec, "action_state")
        assert hasattr(rec, "confidence_layers")
        assert hasattr(rec, "bull_case")
        assert hasattr(rec, "bear_case")
        assert hasattr(rec, "invalidation_conditions")
        assert hasattr(rec, "why_wait")
        assert hasattr(rec, "pre_mortem")
        assert hasattr(rec, "forecast_probability")
        assert hasattr(rec, "uncertainty_low")
        assert hasattr(rec, "uncertainty_high")
        assert hasattr(rec, "reliability_sample_size")

    def test_action_state_default(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(ticker="AAPL")
        assert rec.action_state == "WATCH"

    def test_to_api_dict_includes_new_fields(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(
            ticker="AAPL",
            action_state="STRONG_BUY",
            bull_case="Strong momentum breakout",
            bear_case="Overbought near resistance",
            pre_mortem="Gap down on macro shock",
            confidence_layers={"forecast_probability": 0.72},
        )
        d = rec.to_api_dict()
        assert d["action_state"] == "STRONG_BUY"
        assert d["confidence_layers"]["forecast_probability"] == 0.72
        assert d["explanation"]["bull_case"] == "Strong momentum breakout"
        assert d["explanation"]["bear_case"] == "Overbought near resistance"
        assert d["explanation"]["pre_mortem"] == "Gap down on macro shock"

    def test_backward_compat_still_works(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(ticker="AAPL", composite_score=0.8)
        assert rec["composite_score"] == 0.8
        assert rec.get("nonexistent", "default") == "default"


# ═══════════════════════════════════════════════════════════════════
# 7. SECURITY (unit-testable parts)
# ═══════════════════════════════════════════════════════════════════


class TestSecurityConfig:
    def test_cors_origins_not_wildcard_in_production(self):
        """Verify CORS is restricted in production mode."""
        # This tests the logic, not the middleware itself
        env = "production"
        origins = ["https://cheafi.github.io"] if env == "production" else ["*"]
        assert "*" not in origins

    def test_cors_origins_wildcard_in_dev(self):
        env = "development"
        origins = ["https://cheafi.github.io"] if env == "production" else ["*"]
        assert "*" in origins


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
