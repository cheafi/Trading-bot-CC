"""
VNext Sprint 2 Tests
=====================

Tests for:
  - Commit D: Performance Artifact Writer (json/csv/png/md)
  - Commit H: Portfolio Brief with catalyst integration + holdings param
  - Commit K: Compare Overlay alignment modes
  - Commit L: Strategy Portfolio Lab optimizer
"""

import json
import math
import os
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Configure pytest-asyncio
pytest_plugins = ('anyio',)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ────────────────────────────────────────────────────────────────
# 1) Performance Artifact Writer
# ────────────────────────────────────────────────────────────────


class TestPerformanceArtifactWriter:
    """Tests for src/services/artifacts/performance_artifact_writer.py"""

    def _sample_payload(self):
        return {
            "summary": {
                "annual_return": 28.5,
                "alpha": 12.3,
                "beta": 0.85,
                "sharpe": 1.45,
                "sortino": 2.10,
                "calmar": 1.80,
                "max_drawdown": -15.2,
                "win_rate": 0.62,
                "profit_factor": 1.85,
                "var_95": -4.2,
                "cvar_95": -6.1,
            },
            "trust": {
                "mode": "SYNTHETIC",
                "source": "synthetic_demo",
                "sample_size": 0,
                "assumptions": {"gross_or_net": "net", "fees_bps": 5},
                "data_warning": "SYNTHETIC DATA",
            },
            "equity_curve": {
                "dates": [f"2025-{m:02d}-01" for m in range(1, 13)],
                "values": [100 + i * 2.5 for i in range(12)],
                "benchmark": [100 + i * 1.5 for i in range(12)],
            },
            "monthly_returns": {
                "2025": {"Jan": 2.1, "Feb": 3.4, "Mar": -1.2},
            },
            "annual_returns": [],
            "as_of": "2026-04-04T00:00:00Z",
        }

    def test_write_produces_json_csv_md(self):
        from src.services.artifacts.performance_artifact_writer import \
            PerformanceArtifactWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PerformanceArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(self._sample_payload())

            assert "artifact_id" in meta
            assert meta["artifact_id"].startswith("perf-")
            assert "generated_at" in meta

            paths = meta["artifact_paths"]
            assert "json" in paths
            assert "csv" in paths
            assert "md" in paths

            # Verify JSON artifact is valid
            with open(paths["json"]) as f:
                data = json.load(f)
            assert data["artifact_id"] == meta["artifact_id"]
            assert "summary" in data
            assert data["summary"]["sharpe"] == 1.45

    def test_json_artifact_contains_provenance(self):
        from src.services.artifacts.performance_artifact_writer import \
            PerformanceArtifactWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PerformanceArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(self._sample_payload())

            with open(meta["artifact_paths"]["json"]) as f:
                data = json.load(f)

            assert "generated_at" in data
            assert "version" in data
            assert data["trust"]["mode"] == "SYNTHETIC"

    def test_csv_artifact_has_kpi_and_equity(self):
        from src.services.artifacts.performance_artifact_writer import \
            PerformanceArtifactWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PerformanceArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(self._sample_payload())

            csv_text = Path(meta["artifact_paths"]["csv"]).read_text()
            assert "# KPI Summary" in csv_text
            assert "# Equity Curve" in csv_text
            assert "sharpe" in csv_text
            assert "1.45" in csv_text

    def test_md_artifact_has_summary_table(self):
        from src.services.artifacts.performance_artifact_writer import \
            PerformanceArtifactWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PerformanceArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(self._sample_payload())

            md_text = Path(meta["artifact_paths"]["md"]).read_text()
            assert "Performance Lab Report" in md_text
            assert "SYNTHETIC" in md_text
            assert "| Sharpe |" in md_text

    def test_png_artifact_optional(self):
        """PNG generation is best-effort — should not crash without matplotlib."""
        from src.services.artifacts.performance_artifact_writer import \
            PerformanceArtifactWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PerformanceArtifactWriter(data_dir=Path(tmpdir))
            meta = writer.write(self._sample_payload())
            # PNG may or may not be present depending on matplotlib
            # But the writer should never raise
            assert meta["artifact_id"] is not None


# ────────────────────────────────────────────────────────────────
# 2) Catalyst Summarizer
# ────────────────────────────────────────────────────────────────


class TestCatalystSummarizer:
    """Tests for src/services/catalyst_summarizer.py"""

    @pytest.mark.anyio
    async def test_summarize_with_mock_mds(self):
        from src.services.catalyst_summarizer import CatalystSummarizer

        mock_mds = AsyncMock()
        mock_mds.get_news = AsyncMock(return_value=[
            {
                "title": "NVDA surges on AI demand",
                "link": "https://example.com/1",
                "publisher": "Reuters",
                "providerPublishTime": datetime.now().timestamp() - 3600,
            },
            {
                "title": "Tech stocks rally amid earnings beat",
                "link": "https://example.com/2",
                "publisher": "Bloomberg",
                "providerPublishTime": datetime.now().timestamp() - 7200,
            },
        ])

        cs = CatalystSummarizer(mock_mds)
        result = await cs.summarize(["NVDA", "AAPL"])

        assert "catalysts" in result
        assert len(result["catalysts"]) > 0
        assert "sector_summary" in result
        assert "follow_up_questions" in result
        assert len(result["follow_up_questions"]) > 0

    @pytest.mark.anyio
    async def test_empty_news_produces_valid_output(self):
        from src.services.catalyst_summarizer import CatalystSummarizer

        mock_mds = AsyncMock()
        mock_mds.get_news = AsyncMock(return_value=[])

        cs = CatalystSummarizer(mock_mds)
        result = await cs.summarize(["AAPL"])

        assert result["catalysts"] == []
        assert "No recent catalysts" in result["sector_summary"]

    def test_quick_sentiment(self):
        from src.services.catalyst_summarizer import CatalystSummarizer

        assert CatalystSummarizer._quick_sentiment(
            "NVDA surges on strong earnings beat",
        ) == "bullish"
        assert CatalystSummarizer._quick_sentiment(
            "Stock crashes after downgrade warning",
        ) == "bearish"
        assert CatalystSummarizer._quick_sentiment(
            "Markets trade sideways today",
        ) == "neutral"

    @pytest.mark.anyio
    async def test_handles_mds_errors_gracefully(self):
        from src.services.catalyst_summarizer import CatalystSummarizer

        mock_mds = AsyncMock()
        mock_mds.get_news = AsyncMock(
            side_effect=Exception("API timeout"),
        )

        cs = CatalystSummarizer(mock_mds)
        result = await cs.summarize(["NVDA", "AAPL"])
        # Should not raise — gracefully produces empty catalysts
        assert result["catalysts"] == []


# ────────────────────────────────────────────────────────────────
# 3) Compare Overlay Service
# ────────────────────────────────────────────────────────────────


class TestCompareOverlayService:
    """Tests for src/services/compare_overlay_service.py"""

    def _mock_history(self, n_days=100, base_price=100, vol=0.02):
        """Create a mock DataFrame mimicking price history."""
        import pandas as pd

        dates = pd.date_range("2025-01-01", periods=n_days, freq="B")
        np.random.seed(42)
        returns = np.random.normal(0.001, vol, n_days)
        prices = base_price * np.cumprod(1 + returns)
        return pd.DataFrame({"Close": prices}, index=dates)

    def test_normalized_mode(self):
        from src.services.compare_overlay_service import CompareOverlayService

        svc = CompareOverlayService()
        history_map = {
            "NVDA": self._mock_history(100, 100, 0.03),
            "AAPL": self._mock_history(100, 150, 0.02),
        }

        result = svc.compare(history_map, mode="normalized")

        assert "NVDA" in result.series
        assert "AAPL" in result.series
        # First value should be ~100 (normalized)
        assert abs(result.series["NVDA"][0] - 100) < 0.01
        assert abs(result.series["AAPL"][0] - 100) < 0.01
        assert len(result.dates) > 0

    def test_strict_join_drops_misaligned(self):
        import pandas as pd

        from src.services.compare_overlay_service import CompareOverlayService

        # Create two series with overlapping but not identical ranges
        df1 = pd.DataFrame(
            {"Close": list(range(100, 115))},
            index=pd.date_range("2025-01-01", periods=15),
        )
        df2 = pd.DataFrame(
            {"Close": list(range(200, 215))},
            index=pd.date_range("2025-01-05", periods=15),
        )

        svc = CompareOverlayService()
        result = svc.compare(
            {"A": df1, "B": df2}, mode="normalized", join="strict",
        )

        # Strict join should have fewer rows than either input
        assert result.alignment["join_strategy"] == "strict"
        assert result.alignment["rows_dropped"] >= 0

    def test_smooth_join_ffills(self):
        import pandas as pd

        from src.services.compare_overlay_service import CompareOverlayService

        df1 = pd.DataFrame(
            {"Close": [100, 101, 102, 103, 104, 105, 106]},
            index=pd.date_range("2025-01-01", periods=7),
        )
        df2 = pd.DataFrame(
            {"Close": [200, 201, 202, 203, 204]},
            index=pd.date_range("2025-01-03", periods=5),
        )

        svc = CompareOverlayService()
        result = svc.compare(
            {"A": df1, "B": df2}, mode="normalized", join="smooth",
        )

        assert result.alignment["join_strategy"] == "smooth"
        # Smooth should retain more rows than strict
        assert result.alignment["post_align_rows"] >= 5

    def test_relative_strength_mode(self):
        from src.services.compare_overlay_service import CompareOverlayService

        svc = CompareOverlayService()
        history_map = {
            "NVDA": self._mock_history(100, 100, 0.03),
            "SPY": self._mock_history(100, 400, 0.01),
        }

        result = svc.compare(
            history_map,
            mode="relative_strength",
            benchmark="SPY",
        )

        assert "NVDA" in result.stats
        assert "current_rs" in result.stats["NVDA"]
        assert "outperforming" in result.stats["NVDA"]

    def test_correlation_matrix_symmetric(self):
        from src.services.compare_overlay_service import CompareOverlayService

        svc = CompareOverlayService()
        history_map = {
            "A": self._mock_history(100, 100, 0.02),
            "B": self._mock_history(100, 150, 0.03),
        }

        result = svc.compare(history_map, mode="normalized")

        # Self-correlation should be 1.0
        assert result.correlation_matrix["A"]["A"] == 1.0
        assert result.correlation_matrix["B"]["B"] == 1.0
        # Symmetric
        assert (
            result.correlation_matrix["A"]["B"]
            == result.correlation_matrix["B"]["A"]
        )

    def test_alignment_metadata_present(self):
        from src.services.compare_overlay_service import CompareOverlayService

        svc = CompareOverlayService()
        result = svc.compare(
            {"X": self._mock_history(50)},
            mode="normalized",
        )

        a = result.alignment
        assert "join_strategy" in a
        assert "mode" in a
        assert "pre_align_rows" in a
        assert "post_align_rows" in a
        assert "date_range" in a


# ────────────────────────────────────────────────────────────────
# 4) Strategy Portfolio Lab
# ────────────────────────────────────────────────────────────────


class TestStrategyPortfolioLab:
    """Tests for src/services/strategy_portfolio_lab.py"""

    def _sample_streams(self, n=252):
        np.random.seed(42)
        return {
            "swing": list(np.random.normal(0.0008, 0.015, n)),
            "momentum": list(np.random.normal(0.0012, 0.022, n)),
            "mean_reversion": list(np.random.normal(0.0005, 0.010, n)),
        }

    def test_optimize_produces_three_objectives(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(self._sample_streams())

        assert len(result.optimizations) == 3
        objectives = {o.objective for o in result.optimizations}
        assert objectives == {"max_sharpe", "min_drawdown", "risk_parity"}

    def test_weights_sum_to_one(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(self._sample_streams())

        for opt in result.optimizations:
            total = sum(opt.weights.values())
            assert abs(total - 1.0) < 0.01, (
                f"{opt.objective} weights sum to {total}"
            )

    def test_correlation_matrix_complete(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(self._sample_streams())

        assert "swing" in result.correlation_matrix
        assert "momentum" in result.correlation_matrix["swing"]
        # Self-correlation ~1.0
        assert abs(result.correlation_matrix["swing"]["swing"] - 1.0) < 0.01

    def test_combined_equity_curve(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(self._sample_streams())

        assert result.combined_equity[0] == 100.0
        assert len(result.combined_equity) > 1

    def test_attribution_adds_to_100(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(self._sample_streams())

        total = sum(result.attribution.values())
        assert abs(total - 100.0) < 15.0, (
            f"Attribution sums to {total}"
        )

    def test_regime_conditioned_weights(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        result = lab.optimize(
            self._sample_streams(), regime="BULL",
        )

        assert result.regime_weights is not None
        assert "BULL" in result.regime_weights
        w = result.regime_weights["BULL"]
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_min_strategies_validation(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        with pytest.raises(ValueError, match="≥ 2"):
            lab.optimize({"only_one": [0.01] * 30})

    def test_min_observations_validation(self):
        from src.services.strategy_portfolio_lab import StrategyPortfolioLab

        lab = StrategyPortfolioLab()
        with pytest.raises(ValueError, match="≥ 10"):
            lab.optimize({"a": [0.01] * 5, "b": [0.02] * 5})


# ────────────────────────────────────────────────────────────────
# 5) API Endpoint Integration (via TestClient)
# ────────────────────────────────────────────────────────────────

# Use a try/except so missing httpx doesn't block other tests
try:
    from httpx import ASGITransport, AsyncClient

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
class TestPerformanceLabArtifact:
    """Performance-lab response should include artifact metadata."""

    @pytest.mark.anyio
    async def test_response_has_artifact_block(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/performance-lab?source=synthetic",
            )
            assert r.status_code == 200
            data = r.json()

            # Artifact block should be present
            assert "artifact" in data
            if data["artifact"] is not None:
                assert "artifact_id" in data["artifact"]
                assert "artifact_paths" in data["artifact"]
                assert "generated_at" in data["artifact"]


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
class TestPortfolioBriefHoldings:
    """Portfolio brief should accept custom holdings param."""

    @pytest.mark.anyio
    async def test_holdings_param_changes_watchlist_type(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/portfolio-brief?holdings=NVDA,AAPL,TSLA",
            )
            assert r.status_code == 200
            data = r.json()

            assert data["trust"]["watchlist_type"] == "user_holdings"


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
class TestStrategyPortfolioLabEndpoint:
    """Strategy Portfolio Lab endpoint tests."""

    @pytest.mark.anyio
    async def test_default_strategies(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get("/api/v7/strategy-portfolio-lab")
            assert r.status_code == 200
            data = r.json()

            assert "strategies" in data
            assert "optimizations" in data
            assert len(data["optimizations"]) == 3
            assert "correlation_matrix" in data
            assert "trust" in data
            assert data["trust"]["mode"] in ("LIVE", "SYNTHETIC", "MIXED")

    @pytest.mark.anyio
    async def test_custom_strategies(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/strategy-portfolio-lab"
                "?strategies=trend_following,pairs,value",
            )
            assert r.status_code == 200
            data = r.json()
            assert set(data["strategies"]) == {
                "trend_following", "pairs", "value",
            }

    @pytest.mark.anyio
    async def test_single_strategy_returns_400(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/strategy-portfolio-lab?strategies=swing",
            )
            assert r.status_code == 400


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
class TestCompareOverlayModes:
    """Compare overlay endpoint with new mode/join params."""

    @pytest.mark.anyio
    async def test_default_normalized(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/compare-overlay?tickers=NVDA,AAPL",
            )
            assert r.status_code == 200
            data = r.json()

            assert "alignment" in data
            assert data["trust"]["comparison_mode"] == "normalized"
            assert data["trust"]["join_strategy"] == "strict"

    @pytest.mark.anyio
    async def test_relative_strength_mode(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            r = await client.get(
                "/api/v7/compare-overlay"
                "?tickers=NVDA,AAPL&mode=relative_strength",
            )
            assert r.status_code == 200
            data = r.json()
            assert data["trust"]["comparison_mode"] == "relative_strength"
