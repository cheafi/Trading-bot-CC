"""
Sprint 40b – Remaining TODO items: shadow tracker, symbol dossier,
calibration extensions, backtester enhancements, new API endpoints,
expert weighting, congress provider, spread/slippage kill switches.
"""
import pytest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))


class TestShadowTracker:
    def test_import(self):
        from src.engines.shadow_tracker import ShadowTracker, shadow_tracker
        assert shadow_tracker is not None

    def test_record_prediction(self):
        from src.engines.shadow_tracker import ShadowTracker
        t = ShadowTracker()
        pid = t.record_prediction(
            ticker="AAPL", direction="LONG",
            forecast_probability=0.75,
            strategy="momentum", regime="bull",
        )
        assert pid is not None
        report = t.shadow_report()
        assert report["total_predictions"] == 1
        assert report["pending"] == 1

    def test_record_outcome(self):
        from src.engines.shadow_tracker import ShadowTracker
        t = ShadowTracker()
        pid = t.record_prediction(
            ticker="AAPL", direction="LONG",
            forecast_probability=0.8,
            strategy="mean_reversion", regime="bull",
        )
        t.record_outcome(pid, realized_pnl_pct=0.03, hit_target=True)
        report = t.shadow_report()
        assert report["realized"] == 1
        assert report["hit_rate"] == 1.0

    def test_confidence_vs_hitrate(self):
        from src.engines.shadow_tracker import ShadowTracker
        t = ShadowTracker()
        for i in range(5):
            pid = t.record_prediction(
                ticker="TSLA", direction="LONG",
                forecast_probability=0.6 + i * 0.05,
                strategy="trend", regime="bull",
            )
            t.record_outcome(
                pid, realized_pnl_pct=0.01, hit_target=(i % 2 == 0)
            )
        buckets = t.confidence_vs_hitrate()
        assert isinstance(buckets, list)


class TestSymbolDossier:
    def test_import(self):
        from src.engines.symbol_dossier import SymbolDossier, Verdict
        assert Verdict.BUY is not None

    def test_build(self):
        from src.engines.symbol_dossier import SymbolDossier
        d = SymbolDossier()
        result = d.build("AAPL")
        assert "verdict" in result
        assert "evidence" in result
        assert "scenarios" in result
        assert "event_calendar" in result


class TestCalibrationExtensions:
    def test_horizon_calibration(self):
        from src.engines.calibration_engine import HorizonCalibration
        hc = HorizonCalibration()
        assert "1D" in hc._engines

    def test_sklearn_wrapper(self):
        from src.engines.calibration_engine import SklearnCalibrationWrapper
        w = SklearnCalibrationWrapper(method="isotonic")
        assert w.method == "isotonic"

    def test_conformal_predictor(self):
        from src.engines.calibration_engine import ConformalPredictor
        cp = ConformalPredictor()
        lo, hi = cp.prediction_interval(0.65)
        assert lo <= hi


class TestBacktesterEnhancements:
    def test_partial_fill_rate(self):
        from src.backtest.backtester import Backtester
        b = Backtester(partial_fill_rate=0.7)
        assert b.partial_fill_rate == 0.7

    def test_borrow_cost(self):
        from src.backtest.backtester import Backtester
        b = Backtester(borrow_cost_annual_pct=2.5)
        assert b.borrow_cost_annual_pct == 2.5

    def test_defaults(self):
        from src.backtest.backtester import Backtester
        b = Backtester()
        assert b.partial_fill_rate == 1.0
        assert b.borrow_cost_annual_pct == 0.0


class TestPortfolioHeatKillSwitches:
    def test_spread_kill_switch(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine
        m = PortfolioHeatEngine(spread_kill_switch_bps=50)
        assert m.spread_kill_switch_bps == 50

    def test_slippage_ceiling(self):
        from src.engines.portfolio_heat import PortfolioHeatEngine
        m = PortfolioHeatEngine(slippage_ceiling_bps=30)
        assert m.slippage_ceiling_bps == 30


class TestCongressProvider:
    def test_import(self):
        from src.services.event_data import CongressDisclosureProvider
        p = CongressDisclosureProvider()
        assert p is not None


class TestExpertWeighting:
    def test_weight_function(self):
        from src.api.main import _get_expert_weight
        w = _get_expert_weight("test_expert")
        assert 0.5 <= w <= 1.5

    def test_accuracy_weighted_avg(self):
        from src.api.main import _accuracy_weighted_avg
        council = [
            {"role": "technical", "score": 80},
            {"role": "fundamental", "score": 60},
        ]
        avg = _accuracy_weighted_avg(council)
        assert isinstance(avg, float)


class TestNewAPIEndpoints:
    def test_shadow_report(self):
        import asyncio
        from src.api.main import shadow_report
        result = asyncio.get_event_loop().run_until_complete(shadow_report())
        assert "total_predictions" in result

    def test_dossier(self):
        import asyncio
        from src.api.main import symbol_dossier
        result = asyncio.get_event_loop().run_until_complete(symbol_dossier("AAPL"))
        assert "verdict" in result

    def test_circuit_breaker(self):
        import asyncio
        from src.api.main import circuit_breaker_state
        result = asyncio.get_event_loop().run_until_complete(circuit_breaker_state())
        assert "throttle_state" in result

    def test_pnl_by_regime(self):
        import asyncio
        from src.api.main import pnl_by_regime
        result = asyncio.get_event_loop().run_until_complete(pnl_by_regime())
        assert "regime_pnl" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
