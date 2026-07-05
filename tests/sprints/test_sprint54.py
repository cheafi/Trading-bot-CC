"""Sprint 54 tests — APIRouter extraction, token optimization."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


class TestRouterExtraction:
    """Verify main.py was split correctly and routers work."""

    def test_main_py_reduced(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            lines = len(f.readlines())
        assert lines < 10000, f"main.py should be <10K lines, got {lines}"

    def test_intel_router_exists(self):
        path = os.path.join(
            os.path.dirname(__file__), "src", "api", "routers", "intel.py"
        )
        assert os.path.exists(path)

    def test_routers_init_exists(self):
        path = os.path.join(
            os.path.dirname(__file__), "src", "api", "routers", "__init__.py"
        )
        assert os.path.exists(path)

    def test_intel_router_imports(self):
        from src.api.routers.intel import router

        assert router is not None

    def test_intel_router_has_routes(self):
        from src.api.routers.intel import router

        assert len(router.routes) > 20

    def test_main_includes_intel_router(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v6/expert-tracker" in paths
        assert "/api/v6/signal-decay" in paths
        assert "/api/v6/position-size" in paths

    def test_no_duplicate_routes(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        # Check key endpoints aren't duplicated
        for ep in ["/api/v6/expert-tracker", "/api/v6/signal-decay"]:
            count = paths.count(ep)
            assert count == 1, f"{ep} appears {count} times"


class TestNoRegressions:
    """Ensure nothing broke during extraction."""

    def test_health_endpoint_still_in_main(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in paths

    def test_scoreboard_endpoint_still_in_main(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v6/scoreboard" in paths

    def test_regime_endpoint_still_in_main(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/regime" in paths

    def test_total_route_count(self):
        from src.api.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        # Should have 100+ routes
        assert len(paths) >= 100, f"Only {len(paths)} routes found"


class TestTokenOptimization:
    """Verify the token-optimization goals are met."""

    def test_no_rng_in_main(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "rng." not in code

    def test_no_p1_todo(self):
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            code = f.read()
        assert "(P1 TODO)" not in code

    def test_engines_in_router_not_main(self):
        """Sprint 49-53 engine imports should be in router, not main."""
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
        ) as f:
            main_code = f.read()
        # Import statements should NOT be in main.py anymore
        for engine in [
            "from src.engines.expert_tracker",
            "from src.engines.regime_filter",
            "from src.engines.cross_asset_monitor",
            "from src.engines.confidence_calibrator",
            "from src.engines.position_sizer",
            "from src.engines.trade_gate",
        ]:
            assert engine not in main_code, f"{engine} should be in router, not main"

    def test_engines_in_router(self):
        """Sprint 49-53 engines should be imported in router."""
        with open(
            os.path.join(os.path.dirname(__file__), "src", "api", "routers", "intel.py")
        ) as f:
            router_code = f.read()
        for engine in [
            "ExpertTracker",
            "RegimeFilter",
            "CrossAssetMonitor",
            "ConfidenceCalibrator",
            "PositionSizer",
            "TradeGate",
        ]:
            assert engine in router_code


class TestEngineInstances:
    """Verify all engine singletons are accessible."""

    def test_expert_tracker(self):
        from src.api.routers.intel import _expert_tracker

        assert _expert_tracker is not None

    def test_regime_filter(self):
        from src.api.routers.intel import _regime_filter

        assert _regime_filter is not None

    def test_cross_asset_monitor(self):
        from src.api.routers.intel import _cross_asset_monitor

        assert _cross_asset_monitor is not None

    def test_confidence_calibrator(self):
        from src.api.routers.intel import _confidence_calibrator

        assert _confidence_calibrator is not None

    def test_position_sizer(self):
        from src.api.routers.intel import _position_sizer

        assert _position_sizer is not None

    def test_signal_decay(self):
        from src.api.routers.intel import _signal_decay

        assert _signal_decay is not None

    def test_portfolio_risk_budget(self):
        from src.api.routers.intel import _portfolio_risk_budget

        assert _portfolio_risk_budget is not None

    def test_professional_kpi(self):
        from src.api.routers.intel import _professional_kpi

        assert _professional_kpi is not None
