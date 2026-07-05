"""
VNext P1 Review Fixes — Tests
===============================

Tests for P1 review items:
  - P1-1: _get_regime() await fix in strategy-portfolio-lab
  - P1-2: Deterministic synthetic options (hashlib vs hash)
  - P1-3: Performance Lab gross/net/benchmark clarity
  - P1-4: Portfolio Brief analyst-note upgrade
  - P1-5: Trust strip presence in HTML templates
"""

import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytest_plugins = ("anyio",)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ════════════════════════════════════════════════════════════════
# P1-1 — _get_regime() await bug
# ════════════════════════════════════════════════════════════════


class TestAwaitRegimeFix:
    """Verify _get_regime is awaited in strategy-portfolio-lab."""

    def test_source_code_has_await_get_regime_in_portfolio_lab(self):
        """The strategy-portfolio-lab endpoint must await _get_regime()."""
        main_path = Path(__file__).parent.parent / "src" / "api" / "main.py"
        src = main_path.read_text()

        # Find the strategy_portfolio_lab_data function
        idx = src.find("async def strategy_portfolio_lab_data")
        assert idx > 0, "strategy_portfolio_lab_data endpoint not found"

        # Get the function body (next 100 lines worth)
        func_body = src[idx : idx + 3000]

        # Must contain 'await _get_regime()' — not bare '_get_regime()'
        assert "await _get_regime()" in func_body, (
            "strategy_portfolio_lab_data must use 'await _get_regime()' "
            "— missing await causes RuntimeWarning"
        )


# ════════════════════════════════════════════════════════════════
# P1-2 — Deterministic synthetic options
# ════════════════════════════════════════════════════════════════


class TestDeterministicOptionsHash:
    """Verify options_mapper uses hashlib instead of hash()."""

    def test_options_mapper_no_bare_hash(self):
        """options_mapper.py must not use hash(ticker) for seeding."""
        mapper_path = (
            Path(__file__).parent.parent
            / "src"
            / "services"
            / "options"
            / "options_mapper.py"
        )
        src = mapper_path.read_text()
        # Must NOT contain hash(ticker)
        assert "hash(ticker)" not in src, (
            "options_mapper.py still uses hash(ticker) which is "
            "non-deterministic across Python restarts"
        )

    def test_options_mapper_uses_hashlib(self):
        """options_mapper.py must use hashlib for stable seed."""
        mapper_path = (
            Path(__file__).parent.parent
            / "src"
            / "services"
            / "options"
            / "options_mapper.py"
        )
        src = mapper_path.read_text()
        assert (
            "hashlib" in src
        ), "options_mapper.py should use hashlib for deterministic seeding"

    def test_hashlib_md5_is_stable_across_calls(self):
        """hashlib.md5 produces the same seed for the same ticker."""
        ticker = "AAPL"
        seed1 = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 2**31
        seed2 = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 2**31
        assert seed1 == seed2
        assert seed1 > 0

    def test_different_tickers_get_different_seeds(self):
        """Different tickers must produce different seeds."""
        s1 = int(hashlib.md5(b"AAPL").hexdigest(), 16) % 2**31
        s2 = int(hashlib.md5(b"MSFT").hexdigest(), 16) % 2**31
        assert s1 != s2


# ════════════════════════════════════════════════════════════════
# P1-3 — Performance Lab gross/net/benchmark
# ════════════════════════════════════════════════════════════════


class TestPerformanceLabAdapter:
    """Verify performance lab has gross/net clarity and benchmark info."""

    @pytest.mark.anyio
    async def test_perf_lab_response_has_gross_and_net_returns(self):
        """Response summary must include annual_return_net and annual_return_gross."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/performance-lab?source=synthetic")
            assert r.status_code == 200
            data = r.json()
            s = data["summary"]
            assert "annual_return_net" in s
            assert "annual_return_gross" in s
            # Gross should be >= net (fees add back)
            assert s["annual_return_gross"] >= s["annual_return_net"]

    @pytest.mark.anyio
    async def test_perf_lab_trust_has_benchmark_fields(self):
        """Trust block must identify the benchmark used."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/performance-lab?source=synthetic")
            data = r.json()
            trust = data["trust"]
            assert "benchmark" in trust
            assert trust["benchmark"] == "SPY"
            assert "benchmark_source" in trust
            assert trust["benchmark_source"] in ("LIVE", "SYNTHETIC")

    @pytest.mark.anyio
    async def test_perf_lab_assumptions_have_total_cost(self):
        """Assumptions must include total_cost_bps."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/performance-lab?source=synthetic")
            data = r.json()
            a = data["trust"]["assumptions"]
            assert "total_cost_bps" in a
            assert a["total_cost_bps"] == 8  # 5 fees + 3 slippage
            assert "benchmark" in a
            assert a["benchmark"] == "SPY (S&P 500 ETF)"


# ════════════════════════════════════════════════════════════════
# P1-4 — Portfolio Brief analyst-note upgrade
# ════════════════════════════════════════════════════════════════


class TestPortfolioBriefUpgrade:
    """Verify portfolio brief has actionable/watch/what-changed structure."""

    @pytest.mark.anyio
    async def test_brief_has_actionable_review_watch(self):
        """Response must include actionable, review, watch arrays."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/portfolio-brief")
            assert r.status_code == 200
            data = r.json()
            # New analyst-note fields
            assert "actionable" in data
            assert "review" in data
            assert "watch" in data
            assert isinstance(data["actionable"], list)
            assert isinstance(data["review"], list)
            assert isinstance(data["watch"], list)

    @pytest.mark.anyio
    async def test_brief_has_what_changed(self):
        """Response must include what_changed array."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/portfolio-brief")
            data = r.json()
            assert "what_changed" in data
            assert isinstance(data["what_changed"], list)

    @pytest.mark.anyio
    async def test_brief_holdings_have_action_field(self):
        """Each holding in signals list must have an action field."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/portfolio-brief")
            data = r.json()
            for h in data.get("holdings_with_signals", []):
                assert "action" in h
                assert h["action"] in ("ACTIONABLE", "REVIEW")

    @pytest.mark.anyio
    async def test_brief_trust_has_sample_size(self):
        """Trust block must include sample_size."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/portfolio-brief")
            data = r.json()
            assert "sample_size" in data["trust"]
            assert data["trust"]["sample_size"] > 0

    @pytest.mark.anyio
    async def test_brief_backward_compat(self):
        """Response must still include legacy fields for backward compat."""
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v7/portfolio-brief")
            data = r.json()
            # Legacy fields preserved
            assert "holdings_with_signals" in data
            assert "holdings_no_signal" in data
            assert "headline" in data
            assert "portfolio_story" in data

    def test_sector_map_covers_big_tech(self):
        """Sector map in brief should cover Big Tech, not just semis."""
        main_path = Path(__file__).parent.parent / "src" / "api" / "main.py"
        src = main_path.read_text()
        # Find portfolio_brief_data function body
        idx = src.find("async def portfolio_brief_data")
        func_body = src[idx : idx + 8000]
        assert '"Big Tech"' in func_body
        assert '"Software / AI"' in func_body or '"Software"' in func_body
        assert '"Semiconductor"' in func_body


# ════════════════════════════════════════════════════════════════
# P1-5 — Trust strip on every HTML template
# ════════════════════════════════════════════════════════════════


class TestTrustStripTemplates:
    """Every HTML template must contain a trust strip banner."""

    TEMPLATE_DIR = Path(__file__).parent.parent / "src" / "api" / "templates"

    TEMPLATES = [
        "performance_lab.html",
        "portfolio_brief.html",
        "options_lab.html",
        "compare.html",
        "regime_screener.html",
        "signal_explorer.html",
        "macro_intel.html",
        "index.html",
    ]

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_template_has_trust_strip(self, template):
        """Each template must contain a Trust Strip comment/section."""
        path = self.TEMPLATE_DIR / template
        assert path.exists(), f"Template {template} not found"
        content = path.read_text()
        assert "Trust Strip" in content, f"{template} is missing the Trust Strip banner"

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_template_has_trust_mode_binding(self, template):
        """Each template must bind to trust.mode or trust.data_source."""
        path = self.TEMPLATE_DIR / template
        content = path.read_text()
        has_mode = "trust.mode" in content or "trust?.mode" in content
        has_source = "trust.data_source" in content or "trust?.data_source" in content
        assert (
            has_mode or has_source
        ), f"{template} must bind to trust.mode or trust.data_source"
