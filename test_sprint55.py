"""
Sprint 55 – Bug-fix & cleanup verification
============================================
1. Duplicate portfolio block removed (171 lines)
2. datetime.utcnow() → datetime.now(timezone.utc) everywhere
3. No remaining # TODO: in main.py
4. All src/ files compile
5. Server healthy, portfolio endpoints work
"""

import ast
import os
import pathlib
import py_compile
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parent / "src"
MAIN = SRC / "api" / "main.py"
MAIN_SRC = MAIN.read_text()
ALL_ROUTER_SRC = ""
for rf in (SRC / "api" / "routers").glob("*.py"):
    ALL_ROUTER_SRC += rf.read_text()


# ── 1. Duplicate removal ────────────────────────────────────────────


class TestDuplicateRemoval:
    """Portfolio functions should be defined exactly once (main or router)."""

    def test_portfolio_import_defined_once(self):
        combined = MAIN_SRC + ALL_ROUTER_SRC
        matches = re.findall(r"async def portfolio_import\(", combined)
        assert len(matches) == 1

    def test_portfolio_holdings_defined_once(self):
        combined = MAIN_SRC + ALL_ROUTER_SRC
        matches = re.findall(r"async def portfolio_holdings\(", combined)
        assert len(matches) == 1

    def test_portfolio_from_futu_defined_once(self):
        combined = MAIN_SRC + ALL_ROUTER_SRC
        matches = re.findall(r"async def portfolio_from_futu\(", combined)
        assert len(matches) == 1

    def test_portfolio_advise_defined_once(self):
        combined = MAIN_SRC + ALL_ROUTER_SRC
        matches = re.findall(r"async def portfolio_advise\(", combined)
        assert len(matches) == 1

    def test_main_py_line_count_reduced(self):
        lines = MAIN_SRC.count("\n")
        assert lines < 9700


# ── 2. utcnow() deprecation fix ─────────────────────────────────────


class TestUtcnowRemoval:
    """All datetime.utcnow() calls replaced with datetime.now(timezone.utc)."""

    def test_no_utcnow_in_main(self):
        hits = [
            i + 1
            for i, ln in enumerate(MAIN_SRC.splitlines())
            if "datetime.utcnow()" in ln
        ]
        assert not hits, f"datetime.utcnow() on lines {hits}"

    def test_no_utcnow_in_engines(self):
        bad = []
        for f in (SRC / "engines").glob("*.py"):
            if "datetime.utcnow()" in f.read_text():
                bad.append(f.name)
        assert not bad, f"datetime.utcnow() still in: {bad}"

    def test_no_utcnow_in_routers(self):
        for f in (SRC / "api" / "routers").glob("*.py"):
            assert "datetime.utcnow()" not in f.read_text()

    def test_timezone_imported_in_main(self):
        assert "from datetime import" in MAIN_SRC
        for line in MAIN_SRC.splitlines():
            if line.startswith("from datetime import"):
                assert "timezone" in line
                break


# ── 3. TODO cleanup ─────────────────────────────────────────────────


class TestTodoCleanup:
    def test_no_todo_comments_in_main(self):
        hits = [
            i + 1
            for i, ln in enumerate(MAIN_SRC.splitlines())
            if "# TODO:" in ln
        ]
        assert not hits, f"# TODO: on lines {hits}"


# ── 4. All files compile ────────────────────────────────────────────


class TestCompilation:
    def test_all_src_files_compile(self):
        fails = []
        for root, _, fnames in os.walk(str(SRC)):
            for f in fnames:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        py_compile.compile(path, doraise=True)
                    except py_compile.PyCompileError as e:
                        fails.append(str(e))
        assert not fails, f"Compile errors: {fails}"

    def test_main_py_parses(self):
        ast.parse(MAIN_SRC)

    def test_intel_router_parses(self):
        ast.parse((SRC / "api" / "routers" / "intel.py").read_text())


# ── 5. Engine utcnow fix specific files ─────────────────────────────

FIXED_ENGINES = [
    "cross_asset_monitor",
    "decision_journal",
    "market_intel",
    "trade_gate",
    "watchlist_intel",
    "data_quality",
    "broker_reconciliation",
    "shadow_tracker",
    "signal_engine",
    "symbol_dossier",
    "post_trade_attribution",
    "gpt_validator",
]


class TestEngineFiles:
    @pytest.mark.parametrize("engine", FIXED_ENGINES)
    def test_engine_no_utcnow(self, engine):
        f = SRC / "engines" / f"{engine}.py"
        if f.exists():
            assert "datetime.utcnow()" not in f.read_text()

    @pytest.mark.parametrize("engine", FIXED_ENGINES)
    def test_engine_compiles(self, engine):
        f = SRC / "engines" / f"{engine}.py"
        if f.exists():
            py_compile.compile(str(f), doraise=True)


# ── 6. Server smoke tests (via TestClient) ──────────────────────────


class TestServerSmoke:
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
        assert r.json()["status"] == "healthy"

    def test_portfolio_holdings(self, client):
        r = client.get("/api/portfolio/holdings")
        assert r.status_code == 200
        assert "holdings" in r.json()

    def test_portfolio_advise(self, client):
        r = client.post("/api/portfolio/advise")
        assert r.status_code in (200, 400, 422)
