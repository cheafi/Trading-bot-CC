"""
Sprint 56 – Router extraction + Delta Scoreboard wiring
=========================================================
1. Portfolio/operator/admin extracted into routers/portfolio.py
2. main.py reduced from 9614 → ~9350 lines
3. DeltaTracker + ScoreboardBuilder wired as /api/v6/delta-scoreboard
4. All endpoints still functional via router
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent / "src"
MAIN_SRC = (SRC / "api" / "main.py").read_text()
PORTFOLIO_ROUTER = SRC / "api" / "routers" / "portfolio.py"
PORTFOLIO_SRC = PORTFOLIO_ROUTER.read_text()


# ── 1. Router extraction verification ───────────────────────────────


class TestRouterExtraction:
    """Portfolio/operator/admin endpoints moved out of main.py."""

    def test_portfolio_router_exists(self):
        assert PORTFOLIO_ROUTER.exists()

    def test_portfolio_router_parses(self):
        ast.parse(PORTFOLIO_SRC)

    def test_no_portfolio_endpoints_in_main(self):
        assert "async def portfolio_import(" not in MAIN_SRC
        assert "async def portfolio_holdings(" not in MAIN_SRC
        assert "async def portfolio_from_futu(" not in MAIN_SRC
        assert "async def portfolio_advise(" not in MAIN_SRC

    def test_no_operator_endpoints_in_main(self):
        assert "async def operator_status(" not in MAIN_SRC
        assert "async def operator_set_throttle(" not in MAIN_SRC
        assert "async def operator_kill_switch(" not in MAIN_SRC

    def test_no_admin_endpoints_in_main(self):
        assert "async def trigger_job(" not in MAIN_SRC
        assert "async def list_jobs(" not in MAIN_SRC

    def test_portfolio_endpoints_in_router(self):
        assert "async def portfolio_import(" in PORTFOLIO_SRC
        assert "async def portfolio_holdings(" in PORTFOLIO_SRC
        assert "async def portfolio_from_futu(" in PORTFOLIO_SRC
        assert "async def portfolio_advise(" in PORTFOLIO_SRC

    def test_operator_endpoints_in_router(self):
        assert "async def operator_status(" in PORTFOLIO_SRC
        assert "async def operator_set_throttle(" in PORTFOLIO_SRC
        assert "async def operator_kill_switch(" in PORTFOLIO_SRC

    def test_admin_endpoints_in_router(self):
        assert "async def trigger_job(" in PORTFOLIO_SRC
        assert "async def list_jobs(" in PORTFOLIO_SRC

    def test_router_included_in_main(self):
        assert "portfolio_router" in MAIN_SRC

    def test_main_py_under_9400_lines(self):
        assert MAIN_SRC.count("\n") < 9400


# ── 2. Delta Scoreboard wiring ──────────────────────────────────────


class TestDeltaScoreboard:
    """DeltaTracker + ScoreboardBuilder wired as endpoint."""

    def test_delta_endpoint_in_router(self):
        assert "/api/v6/delta-scoreboard" in PORTFOLIO_SRC

    def test_delta_tracker_imported(self):
        assert "DeltaTracker" in PORTFOLIO_SRC

    def test_scoreboard_builder_imported(self):
        assert "ScoreboardBuilder" in PORTFOLIO_SRC

    def test_market_regime_constructed(self):
        assert "MarketRegime(" in PORTFOLIO_SRC

    def test_regime_enums_used(self):
        assert "VolatilityRegime" in PORTFOLIO_SRC
        assert "TrendRegime" in PORTFOLIO_SRC
        assert "RiskRegime" in PORTFOLIO_SRC


# ── 3. Server smoke tests ───────────────────────────────────────────


class TestServerEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        import sys

        sys.path.insert(0, str(SRC.parent))
        from starlette.testclient import TestClient

        from src.api.main import app

        return TestClient(app)

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_portfolio_holdings(self, client):
        r = client.get("/api/portfolio/holdings")
        assert r.status_code == 200
        assert "holdings" in r.json()

    def test_operator_status(self, client):
        r = client.get("/api/operator/status")
        assert r.status_code == 200
        data = r.json()
        assert "state" in data
        assert "throttle_options" in data

    def test_operator_throttle(self, client):
        r = client.post("/api/operator/throttle?throttle=HALF_SIZE&reason=test")
        assert r.status_code == 200
        assert r.json()["state"]["throttle"] == "HALF_SIZE"

    def test_operator_kill_switch(self, client):
        r = client.post("/api/operator/kill-switch?enabled=true&reason=test")
        assert r.status_code == 200
        assert r.json()["kill_switch"] is True

    def test_admin_trigger_job(self, client):
        r = client.post("/admin/trigger-job/test_job")
        assert r.status_code == 200
        assert r.json()["job"] == "test_job"

    def test_admin_list_jobs(self, client):
        r = client.get("/admin/jobs")
        assert r.status_code == 200
        assert len(r.json()["jobs"]) >= 5

    def test_delta_scoreboard(self, client):
        r = client.get("/api/v6/delta-scoreboard")
        assert r.status_code == 200
        data = r.json()
        assert "delta" in data
        assert "scoreboard" in data
        assert "scoreboard_text" in data
        assert "generated_at" in data

    def test_delta_scoreboard_has_regime_fields(self, client):
        r = client.get("/api/v6/delta-scoreboard")
        data = r.json()
        sb = data["scoreboard"]
        assert "regime_label" in sb
        assert "trend_state" in sb
        assert "strategies_on" in sb

    def test_portfolio_advise_no_holdings(self, client):
        r = client.post("/api/portfolio/advise")
        assert r.status_code == 400


# ── 4. Regression checks ────────────────────────────────────────────


class TestRegression:
    @pytest.fixture(scope="class")
    def client(self):
        import sys

        sys.path.insert(0, str(SRC.parent))
        from starlette.testclient import TestClient

        from src.api.main import app

        return TestClient(app)

    def test_intel_router_still_works(self, client):
        r = client.get("/api/v6/signal-decay")
        assert r.status_code == 200

    def test_screener_still_works(self, client):
        r = client.get("/scan/patterns")
        assert r.status_code in (200, 422)  # may need params

    def test_main_py_compiles(self):
        import py_compile

        py_compile.compile(str(SRC / "api" / "main.py"), doraise=True)

    def test_all_routers_compile(self):
        import py_compile

        for f in (SRC / "api" / "routers").glob("*.py"):
            py_compile.compile(str(f), doraise=True)
