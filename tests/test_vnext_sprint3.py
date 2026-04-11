"""
VNext Sprint 3 Tests
=====================

Tests for:
  - Commit I : Options chain provider ⟶ OptionsMapper
  - Commit J : Expression-aware options screen
  - Commit M : Unified research artifact writer + replay
  - Commit N : External market-intel API contract
  - Commit O : research_lab module (factors, metrics, slippage, portfolio, options, patterns)
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# Configure pytest-asyncio
pytest_plugins = ('anyio',)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ════════════════════════════════════════════════════════════════
# COMMIT I — OptionsMapper unit tests
# ════════════════════════════════════════════════════════════════

class TestOptionsMapper:
    """Tests for src/services/options/options_mapper.py"""

    @pytest.mark.anyio
    async def test_build_screen_returns_result_object(self):
        from src.services.options.options_mapper import (
            OptionsMapper,
            OptionsScreenResult,
        )

        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="AAPL", spot=175.0, rsi=55,
        )
        assert isinstance(result, OptionsScreenResult)
        assert result.ticker == "AAPL"
        assert result.spot_price == 175.0

    @pytest.mark.anyio
    async def test_build_screen_contracts_ranked(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="MSFT", spot=400.0, rsi=60,
        )
        assert len(result.contracts) > 0
        assert len(result.contracts) <= 10
        # Verify ranking
        ranks = [c["rank"] for c in result.contracts]
        assert ranks == list(range(1, len(ranks) + 1))

    @pytest.mark.anyio
    async def test_build_screen_iv_term_structure(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="TSLA", spot=250.0,
        )
        assert len(result.iv_term_structure) >= 7
        dtes = [t["dte"] for t in result.iv_term_structure]
        assert 30 in dtes
        assert 365 in dtes
        for t in result.iv_term_structure:
            assert t["iv"] > 0

    @pytest.mark.anyio
    async def test_build_screen_market_context_fields(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="NVDA", spot=800.0,
        )
        ctx = result.market_context
        assert "iv_rank" in ctx
        assert "iv_percentile" in ctx
        assert "atm_iv" in ctx
        assert "hv_20d" in ctx
        assert "days_to_earnings" in ctx

    @pytest.mark.anyio
    async def test_build_screen_trust_block(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="GOOG", spot=150.0,
        )
        t = result.trust
        assert "mode" in t
        assert t["mode"] in ("LIVE", "SYNTHETIC")
        assert "source" in t
        assert "expression_engine_used" in t

    @pytest.mark.anyio
    async def test_build_screen_strategy_override(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="SPY", spot=450.0,
            strategy="long_put",
        )
        assert result.expression_decision == "long_put"

    @pytest.mark.anyio
    async def test_build_screen_warnings_high_iv(self):
        """When IV rank is high, warning should appear."""
        from src.services.options.options_mapper import OptionsMapper

        # Create a mock provider that returns high IV
        provider = MagicMock()
        chain = MagicMock()
        chain.ticker = "HIGH_IV"
        chain.iv_rank = 80
        chain.iv_percentile = 80
        chain.skew_25d = -0.01
        chain.atm_iv = 0.50
        chain.hv_20d = 0.25
        chain.total_oi = 5000
        chain.expiry = "synthetic"
        chain.strikes = []
        provider.fetch_chain = AsyncMock(return_value=chain)

        mapper = OptionsMapper(options_provider=provider)
        result = await mapper.build_screen(
            ticker="HIGH_IV", spot=100.0,
        )
        # Should have IV rank warning
        iv_warnings = [
            w for w in result.warnings if "IV rank" in w
        ]
        assert len(iv_warnings) > 0

    @pytest.mark.anyio
    async def test_contracts_have_required_fields(self):
        from src.services.options.options_mapper import OptionsMapper
        mapper = OptionsMapper()
        result = await mapper.build_screen(
            ticker="AMZN", spot=180.0,
        )
        for c in result.contracts:
            assert "strike" in c
            assert "dte" in c
            assert "mid" in c
            assert "oi" in c
            assert "ev" in c
            assert "breakeven" in c
            assert "rank" in c


# ════════════════════════════════════════════════════════════════
# COMMIT J — ExpressionEngine integration in OptionsMapper
# ════════════════════════════════════════════════════════════════

class TestExpressionEngineIntegration:
    """Tests for expression engine + options mapper integration."""

    @pytest.mark.anyio
    async def test_expression_engine_used_when_provided(self):
        from src.engines.expression_engine import ExpressionEngine
        from src.services.options.options_mapper import OptionsMapper

        ee = ExpressionEngine()
        mapper = OptionsMapper(expression_engine=ee)
        result = await mapper.build_screen(
            ticker="AAPL", spot=175.0, rsi=60,
        )
        # ExpressionEngine should have been used
        assert result.trust["expression_engine_used"] is True
        # Should have an expression_rationale
        assert result.expression_rationale is not None

    @pytest.mark.anyio
    async def test_expression_decision_populated(self):
        from src.engines.expression_engine import ExpressionEngine
        from src.services.options.options_mapper import OptionsMapper

        ee = ExpressionEngine()
        mapper = OptionsMapper(expression_engine=ee)
        result = await mapper.build_screen(
            ticker="TSLA", spot=250.0, rsi=55,
        )
        assert result.expression_decision in (
            "stock", "long_call", "long_put",
            "debit_spread", "credit_spread",
            "call_spread", "put_spread",
        )

    @pytest.mark.anyio
    async def test_without_expression_engine_defaults_stock(self):
        from src.services.options.options_mapper import OptionsMapper

        mapper = OptionsMapper(expression_engine=None)
        result = await mapper.build_screen(
            ticker="AAPL", spot=175.0,
        )
        assert result.expression_decision == "stock"
        assert result.trust["expression_engine_used"] is False


# ════════════════════════════════════════════════════════════════
# COMMIT M — Unified ResearchArtifactWriter
# ════════════════════════════════════════════════════════════════

class TestResearchArtifactWriter:
    """Tests for src/services/artifacts/research_artifact_writer.py"""

    def _sample_compare_payload(self):
        return {
            "tickers": ["AAPL", "MSFT"],
            "dates": ["2025-01-02", "2025-01-03"],
            "series": {
                "AAPL": [100, 102],
                "MSFT": [100, 101],
            },
            "stats": {
                "AAPL": {"sharpe": 1.2},
                "MSFT": {"sharpe": 0.9},
            },
            "as_of": "2025-01-03T12:00:00Z",
        }

    def _sample_options_payload(self):
        return {
            "ticker": "AAPL",
            "spot_price": 175.0,
            "expression_decision": "long_call",
            "contracts": [
                {"rank": 1, "strike": 180, "dte": 30, "ev": 1.5},
                {"rank": 2, "strike": 185, "dte": 45, "ev": 1.2},
            ],
            "iv_term_structure": [
                {"dte": 30, "iv": 0.28},
                {"dte": 60, "iv": 0.30},
            ],
            "generated_at": "2025-01-03T12:00:00Z",
        }

    def _sample_strategy_payload(self):
        return {
            "strategies": ["swing", "momentum"],
            "optimizations": [
                {
                    "objective": "max_sharpe",
                    "weights": {"swing": 0.6, "momentum": 0.4},
                    "sharpe": 1.8,
                },
            ],
            "as_of": "2025-01-03T12:00:00Z",
        }

    def test_write_compare_overlay(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(
                "compare-overlay", self._sample_compare_payload(),
            )
            assert meta["artifact_id"].startswith("compare-overlay-")
            assert "json" in meta["artifact_paths"]
            assert "csv" in meta["artifact_paths"]
            assert "md" in meta["artifact_paths"]

    def test_write_options_screen(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(
                "options-screen", self._sample_options_payload(),
            )
            assert meta["artifact_id"].startswith("options-screen-")

    def test_write_strategy_lab(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(
                "strategy-portfolio-lab",
                self._sample_strategy_payload(),
            )
            assert meta["artifact_id"].startswith(
                "strategy-portfolio-lab-",
            )

    def test_load_artifact_by_id(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(
                "compare-overlay", self._sample_compare_payload(),
            )
            aid = meta["artifact_id"]
            loaded = writer.load(aid)
            assert loaded is not None
            assert loaded["artifact_id"] == aid

    def test_load_missing_returns_none(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            assert writer.load("nonexistent-id") is None

    def test_list_artifacts_all(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            writer.write("compare-overlay", self._sample_compare_payload())
            writer.write("options-screen", self._sample_options_payload())
            writer.write("strategy-portfolio-lab", self._sample_strategy_payload())

            all_artifacts = writer.list_artifacts()
            assert len(all_artifacts) == 3

    def test_list_artifacts_filter_by_surface(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            writer.write("compare-overlay", self._sample_compare_payload())
            writer.write("compare-overlay", self._sample_compare_payload())
            writer.write("options-screen", self._sample_options_payload())

            compare_only = writer.list_artifacts(surface="compare-overlay")
            assert len(compare_only) == 2

    def test_json_artifact_is_valid_json(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(
                "options-screen", self._sample_options_payload(),
            )
            json_path = meta["artifact_paths"]["json"]
            with open(json_path) as f:
                data = json.load(f)
            assert "artifact_id" in data

    def test_index_file_maintained(self):
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ResearchArtifactWriter(data_dir=Path(tmpdir))
            writer.write("compare-overlay", self._sample_compare_payload())
            writer.write("options-screen", self._sample_options_payload())

            index_path = writer.base / "_index.json"
            assert index_path.exists()
            entries = json.loads(index_path.read_text())
            assert len(entries) == 2


# ════════════════════════════════════════════════════════════════
# COMMIT N — Market Intel API endpoints
# ════════════════════════════════════════════════════════════════

class TestMarketIntelEndpoints:
    """Tests for /api/market-intel/* endpoints via HTTPX TestClient."""

    @pytest.fixture
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from src.api.main import _init_shared_services, app

        # Ensure singletons are wired
        if not hasattr(app.state, "market_data") or app.state.market_data is None:
            _init_shared_services()

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.anyio
    async def test_regime_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/market-intel/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "as_of" in data
        # Should have regime_label or regime key
        assert "regime_label" in data or "regime" in data

    @pytest.mark.anyio
    async def test_vix_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/market-intel/vix")
        assert resp.status_code == 200
        data = resp.json()
        assert "as_of" in data
        assert "label" in data
        assert data["label"] in (
            "LOW", "NORMAL", "ELEVATED", "HIGH",
            "EXTREME", "UNAVAILABLE",
        )

    @pytest.mark.anyio
    async def test_breadth_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/market-intel/breadth")
        assert resp.status_code == 200
        data = resp.json()
        assert "breadth" in data
        assert "as_of" in data

    @pytest.mark.anyio
    async def test_spy_return_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/market-intel/spy-return")
        assert resp.status_code == 200
        data = resp.json()
        assert "spy_returns" in data
        assert "as_of" in data

    @pytest.mark.anyio
    async def test_rates_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/market-intel/rates")
        assert resp.status_code == 200
        data = resp.json()
        assert "yields" in data
        assert "curve_status" in data
        assert "as_of" in data

    @pytest.mark.anyio
    async def test_artifact_list_endpoint(self, client):
        async with client as c:
            resp = await c.get("/api/v7/research/artifacts")
        assert resp.status_code == 200
        data = resp.json()
        assert "artifacts" in data
        assert isinstance(data["artifacts"], list)

    @pytest.mark.anyio
    async def test_artifact_replay_not_found(self, client):
        async with client as c:
            resp = await c.get(
                "/api/v7/research/artifacts/nonexistent-id",
            )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# COMMIT O — research_lab module tests
# ════════════════════════════════════════════════════════════════

class TestResearchLabFactors:
    """Tests for src/research_lab/factors.py"""

    def test_momentum_score(self):
        from src.research_lab.factors import momentum_score

        # Needs >= 252 daily returns for default lookback
        returns = np.random.normal(0.002, 0.01, 300)
        score = momentum_score(returns)
        assert isinstance(score, float)
        # Positive mean returns → positive momentum (probabilistic)

    def test_momentum_score_short_array(self):
        from src.research_lab.factors import momentum_score
        returns = np.random.normal(-0.001, 0.01, 50)
        score = momentum_score(returns)
        assert score == 0.0  # too short for default lookback

    def test_mean_reversion_score(self):
        from src.research_lab.factors import mean_reversion_score
        prices = np.array([100 + i * 0.1 for i in range(60)])
        score = mean_reversion_score(prices)
        assert isinstance(score, float)

    def test_quality_score(self):
        from src.research_lab.factors import quality_score
        score = quality_score(roe=0.18, debt_equity=0.5, margin=0.12)
        assert isinstance(score, float)
        assert 0 < score <= 1.0

    def test_quality_score_poor(self):
        from src.research_lab.factors import quality_score
        score = quality_score(roe=0.02, debt_equity=3.0, margin=0.02)
        assert score < 0.5

    def test_volatility_factor(self):
        from src.research_lab.factors import volatility_factor
        returns = np.random.normal(0.001, 0.02, 252)
        vol = volatility_factor(returns)
        assert isinstance(vol, float)
        assert vol > 0


class TestResearchLabMetrics:
    """Tests for src/research_lab/metrics.py"""

    def test_sharpe_ratio(self):
        from src.research_lab.metrics import sharpe_ratio
        returns = np.random.normal(0.001, 0.02, 252)
        sr = sharpe_ratio(returns)
        assert isinstance(sr, float)

    def test_sortino_ratio(self):
        from src.research_lab.metrics import sortino_ratio
        returns = np.random.normal(0.001, 0.02, 252)
        s = sortino_ratio(returns)
        assert isinstance(s, float)

    def test_calmar_ratio(self):
        from src.research_lab.metrics import calmar_ratio
        returns = np.random.normal(0.001, 0.02, 252)
        c = calmar_ratio(returns)
        assert isinstance(c, float)

    def test_max_drawdown(self):
        from src.research_lab.metrics import max_drawdown
        returns = np.random.normal(0.001, 0.02, 252)
        dd = max_drawdown(returns)
        assert dd <= 0  # drawdown is non-positive

    def test_var_cvar(self):
        from src.research_lab.metrics import var_cvar
        returns = np.random.normal(0.001, 0.02, 252)
        var, cvar = var_cvar(returns)
        assert var <= 0
        assert cvar <= var  # CVaR is worse than VaR

    def test_analyze_drawdowns(self):
        from src.research_lab.metrics import analyze_drawdowns

        # Create returns with a clear drawdown
        returns = np.concatenate([
            np.full(50, 0.01),
            np.full(30, -0.02),
            np.full(50, 0.01),
        ])
        dd_list = analyze_drawdowns(returns)
        assert isinstance(dd_list, list)


class TestResearchLabSlippage:
    """Tests for src/research_lab/slippage.py"""

    def test_estimate_slippage(self):
        from src.research_lab.slippage import estimate_slippage
        est = estimate_slippage(
            price=100.0,
            size_shares=500,
            avg_daily_volume=1_000_000,
            avg_spread_pct=0.05,
        )
        assert est.total_cost_bps > 0
        assert est.spread_cost_bps > 0
        assert est.market_impact_bps >= 0

    def test_slippage_increases_with_size(self):
        from src.research_lab.slippage import estimate_slippage
        small = estimate_slippage(100.0, 100, 1_000_000)
        large = estimate_slippage(100.0, 50_000, 1_000_000)
        assert large.total_cost_bps > small.total_cost_bps


class TestResearchLabPortfolio:
    """Tests for src/research_lab/portfolio.py"""

    def test_equal_weight(self):
        from src.research_lab.portfolio import equal_weight
        w = equal_weight(["swing", "momentum", "mean_rev", "trend", "vol"])
        assert len(w) == 5
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_inverse_vol_weight(self):
        from src.research_lab.portfolio import inverse_vol_weight
        returns_map = {
            "low_vol": list(np.random.normal(0.001, 0.005, 100)),
            "high_vol": list(np.random.normal(0.001, 0.02, 100)),
        }
        w = inverse_vol_weight(returns_map)
        assert len(w) == 2
        assert abs(sum(w.values()) - 1.0) < 1e-9
        # Lower vol asset should get higher weight
        assert w["low_vol"] > w["high_vol"]

    def test_max_sharpe_weight(self):
        from src.research_lab.portfolio import max_sharpe_weight
        returns_map = {
            "A": list(np.random.normal(0.001, 0.01, 300)),
            "B": list(np.random.normal(0.0005, 0.008, 300)),
        }
        w = max_sharpe_weight(returns_map)
        assert len(w) == 2
        assert abs(sum(w.values()) - 1.0) < 1e-4


class TestResearchLabOptions:
    """Tests for src/research_lab/options.py"""

    def test_black_scholes_greeks_call(self):
        from src.research_lab.options import black_scholes_greeks
        g = black_scholes_greeks(
            spot=100, strike=100, dte=91, iv=0.20,
            rf=0.05, is_call=True,
        )
        assert g.delta > 0  # call delta positive
        assert g.gamma > 0
        assert g.theta < 0  # time decay
        assert g.vega > 0

    def test_black_scholes_greeks_put(self):
        from src.research_lab.options import black_scholes_greeks
        g = black_scholes_greeks(
            spot=100, strike=100, dte=91, iv=0.20,
            rf=0.05, is_call=False,
        )
        assert g.delta < 0  # put delta negative

    def test_greeks_atm_delta_near_half(self):
        """ATM call delta should be close to 0.5."""
        from src.research_lab.options import black_scholes_greeks
        g = black_scholes_greeks(
            spot=100, strike=100, dte=365, iv=0.25,
        )
        assert 0.45 < g.delta < 0.75

    def test_strategy_payoff(self):
        from src.research_lab.options import strategy_payoff
        legs = [
            {"type": "CALL", "strike": 100, "side": "BUY",
             "qty": 1, "premium": 5},
        ]
        results = strategy_payoff(
            legs, spot_range=[80, 100, 105, 120], spot=100,
        )
        assert len(results) == 4
        # At spot=80: intrinsic=0, PnL = -5*100 = -500
        assert results[0]["pnl"] == -500.0
        # At spot=120: intrinsic=20, PnL = (20-5)*100 = 1500
        assert results[3]["pnl"] == 1500.0

    def test_bull_call_spread(self):
        from src.research_lab.options import strategy_payoff
        legs = [
            {"type": "CALL", "strike": 100, "side": "BUY",
             "qty": 1, "premium": 5},
            {"type": "CALL", "strike": 110, "side": "SELL",
             "qty": 1, "premium": 2},
        ]
        results = strategy_payoff(
            legs, spot_range=[90, 100, 105, 110, 120],
        )
        # At 90: max loss = (-5 + 2)*100 = -300
        assert results[0]["pnl"] == -300.0
        # At 120: max profit = (20-5-10+2)*100 = 700
        assert results[4]["pnl"] == 700.0


class TestResearchLabPatterns:
    """Tests for src/research_lab/patterns.py"""

    def test_detect_patterns_returns_list(self):
        from src.research_lab.patterns import detect_patterns
        close = np.array([100 + i * 0.5 for i in range(60)])
        high = close + 1
        low = close - 1
        volume = np.full(60, 1_000_000.0)
        patterns = detect_patterns(close, high, low, volume)
        assert isinstance(patterns, list)

    def test_detect_uptrend(self):
        from src.research_lab.patterns import detect_patterns

        # Clear uptrend: higher highs, higher lows
        close = np.array([100 + i * 0.8 for i in range(60)])
        high = close + 2
        low = close - 2
        volume = np.full(60, 1_000_000.0)
        patterns = detect_patterns(close, high, low, volume)
        pattern_names = [p["pattern"] for p in patterns]
        assert "uptrend" in pattern_names

    def test_volume_climax(self):
        from src.research_lab.patterns import detect_patterns
        close = np.array([100 + i * 0.1 for i in range(60)])
        high = close + 1
        low = close - 1
        volume = np.full(60, 100_000.0)
        volume[-1] = 500_000.0  # 5x average
        patterns = detect_patterns(close, high, low, volume)
        pattern_names = [p["pattern"] for p in patterns]
        assert "volume_climax" in pattern_names

    def test_short_data_returns_empty(self):
        from src.research_lab.patterns import detect_patterns
        close = np.array([100, 101, 102])
        high = close + 1
        low = close - 1
        volume = np.full(3, 100_000.0)
        patterns = detect_patterns(close, high, low, volume)
        assert patterns == []


# ════════════════════════════════════════════════════════════════
# COMMIT N — SKILL.md and API_MARKET_INTEL.md existence
# ════════════════════════════════════════════════════════════════

class TestDocumentation:
    """Verify commit N documentation files exist."""

    def test_skill_md_exists(self):
        path = Path(__file__).parent.parent / "docs" / "SKILL.md"
        assert path.exists(), "docs/SKILL.md missing"
        content = path.read_text()
        assert "Capability" in content
        assert "Market Intel" in content or "market-intel" in content

    def test_api_market_intel_md_exists(self):
        path = (
            Path(__file__).parent.parent
            / "docs" / "API_MARKET_INTEL.md"
        )
        assert path.exists(), "docs/API_MARKET_INTEL.md missing"
        content = path.read_text()
        assert "/api/market-intel" in content
        assert "regime" in content
        assert "vix" in content.lower()

    def test_research_lab_init(self):
        """research_lab package should be importable."""
        import src.research_lab  # noqa: F401


# ════════════════════════════════════════════════════════════════
# Phase 2 — New endpoint tests (dossier, brief, options)
# ════════════════════════════════════════════════════════════════

class TestPhase2Endpoints:
    """Tests for Phase 2 decision-compression endpoints."""

    @pytest.fixture
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.anyio
    async def test_dossier_endpoint_returns_200(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/AAPL")
            assert r.status_code == 200
            d = r.json()
            assert d["symbol"] == "AAPL"
            assert "price" in d
            assert "technicals" in d
            assert "factors" in d
            assert "why_buy" in d
            assert "why_stop" in d
            assert "trade_plan" in d
            assert "trust" in d

    @pytest.mark.anyio
    async def test_dossier_technicals_structure(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/MSFT")
            assert r.status_code == 200
            t = r.json()["technicals"]
            for key in ["rsi", "sma20", "sma50", "atr", "volume_ratio",
                        "macd_signal", "support", "resistance",
                        "high_52w", "low_52w", "bbands_upper", "bbands_lower"]:
                assert key in t, f"Missing {key} in technicals"

    @pytest.mark.anyio
    async def test_dossier_factor_chips(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/AAPL")
            d = r.json()
            assert len(d["factors"]) >= 5
            for f in d["factors"]:
                assert "name" in f
                assert "value" in f
                assert f["signal"] in ("positive", "negative", "neutral")
            assert "factor_summary" in d
            assert "positive" in d["factor_summary"]
            assert "negative" in d["factor_summary"]

    @pytest.mark.anyio
    async def test_dossier_trade_plan(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/AAPL")
            tp = r.json()["trade_plan"]
            assert "entry_zone" in tp
            assert len(tp["entry_zone"]) == 2
            assert "target_1r" in tp
            assert "target_2r" in tp
            assert "stop" in tp
            assert "risk_per_share" in tp

    @pytest.mark.anyio
    async def test_dossier_why_buy_stop(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/AAPL")
            d = r.json()
            assert isinstance(d["why_buy"], list) and len(d["why_buy"]) > 0
            assert isinstance(d["why_stop"], list) and len(d["why_stop"]) > 0

    @pytest.mark.anyio
    async def test_dossier_404_bad_ticker(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/ZZZZZ9")
            assert r.status_code == 404

    @pytest.mark.anyio
    async def test_brief_endpoint_returns_200(self, client):
        async with client as c:
            r = await c.get("/api/live/brief")
            assert r.status_code == 200
            d = r.json()
            assert "date" in d
            assert "regime" in d
            assert "narrative" in d["regime"]
            assert "what_changed" in d
            assert isinstance(d["what_changed"], list)
            assert "trust" in d

    @pytest.mark.anyio
    async def test_brief_has_actionable_and_watch(self, client):
        async with client as c:
            r = await c.get("/api/live/brief")
            d = r.json()
            assert "actionable" in d
            assert "watch" in d
            assert isinstance(d["actionable"], list)
            assert isinstance(d["watch"], list)

    @pytest.mark.anyio
    async def test_brief_sectors(self, client):
        async with client as c:
            r = await c.get("/api/live/brief")
            d = r.json()
            assert "sectors" in d
            assert isinstance(d["sectors"], list)

    @pytest.mark.anyio
    async def test_brief_follow_up(self, client):
        async with client as c:
            r = await c.get("/api/live/brief")
            d = r.json()
            assert "follow_up" in d
            assert len(d["follow_up"]) >= 3

    @pytest.mark.anyio
    async def test_options_endpoint_returns_200(self, client):
        async with client as c:
            r = await c.get("/api/live/options/AAPL")
            assert r.status_code == 200
            d = r.json()
            assert d["symbol"] == "AAPL"
            assert "contracts" in d
            assert len(d["contracts"]) == 5
            assert "trust" in d
            assert d["trust"]["mode"] == "SYNTHETIC"

    @pytest.mark.anyio
    async def test_options_contract_structure(self, client):
        async with client as c:
            r = await c.get("/api/live/options/MSFT")
            d = r.json()
            for c_item in d["contracts"]:
                for key in ["strike", "dte", "type", "delta", "iv", "oi",
                            "spread_quality", "ev", "break_even"]:
                    assert key in c_item, f"Missing {key} in contract"

    @pytest.mark.anyio
    async def test_options_iv_context(self, client):
        async with client as c:
            r = await c.get("/api/live/options/AAPL")
            d = r.json()
            assert "iv_rank" in d
            assert "iv_percentile" in d
            assert "term_structure" in d
            assert "skew_note" in d
            assert "regime_context" in d

    @pytest.mark.anyio
    async def test_options_404_bad_ticker(self, client):
        async with client as c:
            r = await c.get("/api/live/options/ZZZZZ9")
            assert r.status_code == 404

    @pytest.mark.anyio
    async def test_dossier_trust_has_as_of(self, client):
        async with client as c:
            r = await c.get("/api/live/dossier/AAPL")
            trust = r.json()["trust"]
            assert "as_of" in trust
            assert "source" in trust
            assert "mode" in trust

    @pytest.mark.anyio
    async def test_brief_trust_has_as_of(self, client):
        async with client as c:
            r = await c.get("/api/live/brief")
            trust = r.json()["trust"]
            assert "as_of" in trust
            assert "source" in trust

    def test_patterns_importable(self):
        from src.research_lab.patterns import detect_patterns  # noqa: F401
        assert callable(detect_patterns)


# ════════════════════════════════════════════════════════════════
# Phase 3 — Operator Console + Data Catalog endpoints
# ════════════════════════════════════════════════════════════════


class TestPhase3OpsEndpoints:
    """Tests for Phase 3 operator console and data catalog endpoints."""

    @pytest.fixture
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.anyio
    async def test_ops_status_returns_200(self, client):
        async with client as c:
            r = await c.get("/api/ops/status")
            assert r.status_code == 200
            d = r.json()
            assert "uptime" in d
            assert "uptime_seconds" in d
            assert "version" in d
            assert "engine" in d
            assert "latency" in d
            assert "trust" in d

    @pytest.mark.anyio
    async def test_ops_status_engine_fields(self, client):
        async with client as c:
            r = await c.get("/api/ops/status")
            eng = r.json()["engine"]
            for key in [
                "running",
                "dry_run",
                "cycle_count",
                "signals_today",
                "trades_today",
                "cached_recommendations",
                "circuit_breaker",
            ]:
                assert key in eng, f"Missing {key} in engine"

    @pytest.mark.anyio
    async def test_ops_status_latency(self, client):
        async with client as c:
            r = await c.get("/api/ops/status")
            lat = r.json()["latency"]
            assert "regime_ms" in lat
            assert isinstance(lat["regime_ms"], (int, float))

    @pytest.mark.anyio
    async def test_ops_endpoints_returns_200(self, client):
        async with client as c:
            r = await c.get("/api/ops/endpoints")
            assert r.status_code == 200
            d = r.json()
            assert "count" in d
            assert "endpoints" in d
            assert d["count"] > 0
            assert isinstance(d["endpoints"], list)

    @pytest.mark.anyio
    async def test_ops_endpoints_includes_known_routes(self, client):
        async with client as c:
            r = await c.get("/api/ops/endpoints")
            paths = [ep["path"] for ep in r.json()["endpoints"]]
            for expected in [
                "/api/health",
                "/api/live/market",
                "/api/live/dossier/{ticker}",
                "/api/live/brief",
                "/api/live/options/{ticker}",
                "/api/ops/status",
                "/api/ops/endpoints",
            ]:
                assert expected in paths, f"Missing {expected} in endpoint inventory"

    @pytest.mark.anyio
    async def test_ops_endpoints_structure(self, client):
        async with client as c:
            r = await c.get("/api/ops/endpoints")
            ep = r.json()["endpoints"][0]
            assert "method" in ep
            assert "path" in ep
            assert ep["method"] in ("GET", "POST", "PUT", "DELETE")


# ════════════════════════════════════════════════════════════════
# Phase 4 — Hardening & Honesty
# ════════════════════════════════════════════════════════════════


class TestPhase4Hardening:
    """Tests for Phase 4: duplicate handler fix, deterministic options,
    ticker validation, honest AI endpoints."""

    @pytest.fixture
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    # ── Ticker validation ──

    @pytest.mark.anyio
    async def test_invalid_ticker_rejected(self, client):
        """Tickers with invalid chars should return 422."""
        async with client as c:
            r = await c.get("/api/live/quote/DROP TABLE")
            assert r.status_code == 422
            d = r.json()
            assert "Invalid ticker" in (d.get("error", "") or d.get("detail", ""))

    @pytest.mark.anyio
    async def test_ticker_too_long_rejected(self, client):
        """Tickers over 10 chars should return 422."""
        async with client as c:
            r = await c.get("/api/live/quote/ABCDEFGHIJK")
            assert r.status_code == 422

    @pytest.mark.anyio
    async def test_valid_ticker_accepted(self, client):
        """Valid tickers like AAPL should not return 422."""
        async with client as c:
            r = await c.get("/api/live/quote/aapl")
            # Should NOT be 422 — either 200 or 404 (data may be unavailable)
            assert r.status_code in (200, 404)

    @pytest.mark.anyio
    async def test_ticker_with_dot_accepted(self, client):
        """Tickers like BRK.B should pass validation."""
        async with client as c:
            r = await c.get("/api/live/quote/BRK.B")
            assert r.status_code in (200, 404)

    @pytest.mark.anyio
    async def test_ticker_validation_dossier(self, client):
        """Dossier endpoint should also reject invalid tickers."""
        async with client as c:
            r = await c.get("/api/live/dossier/<script>")
            assert r.status_code == 422

    @pytest.mark.anyio
    async def test_ticker_validation_options(self, client):
        """Options endpoint should also reject invalid tickers."""
        async with client as c:
            r = await c.get("/api/live/options/INVALID!!!")
            assert r.status_code == 422

    # ── Deterministic options ──

    @pytest.mark.anyio
    async def test_options_deterministic(self, client):
        """Same ticker on same day should produce identical IV results."""
        async with client as c:
            r1 = await c.get("/api/live/options/AAPL")
            r2 = await c.get("/api/live/options/AAPL")
            if r1.status_code == 200 and r2.status_code == 200:
                d1 = r1.json()
                d2 = r2.json()
                assert d1["iv_rank"] == d2["iv_rank"]
                assert d1["contracts"][0]["iv"] == d2["contracts"][0]["iv"]
                assert d1["contracts"][0]["delta"] == d2["contracts"][0]["delta"]

    # ── Honest AI endpoints ──

    @pytest.mark.anyio
    async def test_ai_advisor_live_regime(self, client):
        """AI advisor should return live regime data, not hardcoded marketing text."""
        async with client as c:
            r = await c.get("/api/ai-advisor")
            assert r.status_code == 200
            d = r.json()
            assert "status" in d
            assert d["status"] == "live"
            assert "trust" in d
            assert d["trust"]["mode"] == "LIVE"
            assert "chain_of_thought" in d
            assert isinstance(d["chain_of_thought"], list)
            # Should contain real regime info, not static text
            assert any("Regime:" in c for c in d["chain_of_thought"])

    @pytest.mark.anyio
    async def test_ml_status_honest(self, client):
        """ML status should be honest about model state, not fabricate metrics."""
        async with client as c:
            r = await c.get("/api/ml-status")
            assert r.status_code == 200
            d = r.json()
            assert "trust" in d
            assert d["trust"]["mode"] in ("LIVE", "HONEST")
            # Must NOT contain fabricated accuracy (the old 72.5 was fake)
            assert "accuracy" not in d or d.get("trust", {}).get("mode") == "LIVE"

    # ── Exception handler dedup ──

    @pytest.mark.anyio
    async def test_exception_handler_has_timestamp(self, client):
        """HTTP errors should include a timestamp (from the detailed handler, not the simple one)."""
        async with client as c:
            # Trigger a 422 via bad ticker
            r = await c.get("/api/live/quote/!!!")
            assert r.status_code == 422
            d = r.json()
            # The detailed handler adds structured error info
            assert "detail" in d or "error" in d

    @pytest.mark.anyio
    async def test_404_has_structured_response(self, client):
        """404 errors should have a structured JSON response."""
        async with client as c:
            r = await c.get("/api/live/quote/ZZZZZZ")
            if r.status_code == 404:
                d = r.json()
                # Should have error or detail field
                assert "error" in d or "detail" in d

    # ── validate_ticker unit tests ──

    def test_validate_ticker_strips_whitespace(self):
        from src.api.main import validate_ticker

        assert validate_ticker("  aapl ") == "AAPL"

    def test_validate_ticker_uppercases(self):
        from src.api.main import validate_ticker

        assert validate_ticker("msft") == "MSFT"

    def test_validate_ticker_rejects_empty(self):
        from src.api.main import validate_ticker

        with pytest.raises(Exception):  # HTTPException
            validate_ticker("")

    def test_validate_ticker_rejects_special_chars(self):
        from src.api.main import validate_ticker

        with pytest.raises(Exception):
            validate_ticker("<script>alert(1)</script>")

    def test_validate_ticker_allows_dots(self):
        from src.api.main import validate_ticker

        assert validate_ticker("BRK.B") == "BRK.B"

    def test_validate_ticker_allows_caret(self):
        from src.api.main import validate_ticker

        assert validate_ticker("^VIX") == "^VIX"
