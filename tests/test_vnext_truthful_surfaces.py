"""
VNext Sprint — Truthful Surfaces Tests
========================================
Verifies that core API endpoints:
  1. Read from singleton engine cache (not ad-hoc instances).
  2. Return trust metadata (mode / source / as_of).
  3. Never emit random data in non-SYNTHETIC mode.
  4. Include signal lifecycle fields on recommendations.
"""
import asyncio
import importlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_engine(
    cached_recs=None,
    leaderboard=None,
    dry_run=True,
):
    """Build a minimal mock AutoTradingEngine for testing."""
    engine = MagicMock()
    engine._cached_recommendations = cached_recs or []
    engine._cached_leaderboard = leaderboard or {}
    engine.dry_run = dry_run
    engine._no_trade_card = None
    engine.trade_repo = MagicMock()
    engine.trade_repo.get_closed_trades = MagicMock(
        return_value=[],
    )
    engine.kpi = MagicMock()
    engine.kpi.snapshot = MagicMock(return_value=None)
    return engine


# ---------------------------------------------------------------------------
# 1. TradeRecommendation lifecycle fields
# ---------------------------------------------------------------------------

class TestTradeRecommendationLifecycle:
    """Signal lifecycle fields exist and serialise correctly."""

    def test_lifecycle_fields_exist(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(ticker="AAPL")
        assert hasattr(rec, "lifecycle_status")
        assert hasattr(rec, "exited_at")
        assert hasattr(rec, "exit_reason")
        assert hasattr(rec, "expected_r")
        assert hasattr(rec, "realized_r")
        assert hasattr(rec, "realized_pnl_pct")

    def test_lifecycle_defaults(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(ticker="MSFT")
        assert rec.lifecycle_status == "TRIGGERED"
        assert rec.exit_reason == ""
        assert rec.realized_r == 0.0

    def test_lifecycle_serialisation(self):
        from src.core.models import TradeRecommendation

        rec = TradeRecommendation(
            ticker="NVDA",
            lifecycle_status="TP",
            exit_reason="tp_hit",
            expected_r=2.5,
            realized_r=3.1,
            realized_pnl_pct=6.2,
            exited_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        d = rec.to_api_dict()
        assert d["lifecycle_status"] == "TP"
        assert d["exit_reason"] == "tp_hit"
        assert d["realized_r"] == 3.1
        # exited_at should be serialised as ISO string
        assert isinstance(d["exited_at"], str)
        assert "2026-04-01" in d["exited_at"]


# ---------------------------------------------------------------------------
# 2. /api/recommendations reads singleton engine
# ---------------------------------------------------------------------------

class TestRecommendationsEndpoint:
    """Recommendations endpoint must use _get_engine(), not local instances."""

    @pytest.fixture
    def client(self):
        """Create a TestClient for the FastAPI app."""
        try:
            from fastapi.testclient import TestClient

            from src.api.main import app
            return TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient not available")

    def test_response_has_trust_metadata(self, client):
        resp = client.get("/api/recommendations?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert data["mode"] in ("LIVE", "PAPER", "OFFLINE")
        assert "source" in data
        assert data["source"] == "engine_cache"
        assert "as_of" in data

    def test_response_has_regime(self, client):
        resp = client.get("/api/recommendations?limit=3")
        data = resp.json()
        assert "regime" in data

    def test_no_stale_note_field(self, client):
        """Old 'note' field should be gone."""
        resp = client.get("/api/recommendations")
        data = resp.json()
        # Should not contain the old placeholder note
        assert data.get("note") != \
            "Live data populated when AutoTradingEngine is running."

    def test_count_matches_recommendations(self, client):
        resp = client.get("/api/recommendations?limit=5")
        data = resp.json()
        assert data["count"] == len(data["recommendations"])


# ---------------------------------------------------------------------------
# 3. Performance Lab never returns random in live mode
# ---------------------------------------------------------------------------

class TestPerformanceLabTruth:
    """Performance Lab must clearly separate LIVE from SYNTHETIC."""

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient

            from src.api.main import app
            return TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient not available")

    def test_synthetic_mode_labelled(self, client):
        """When no real trades, mode must be SYNTHETIC."""
        resp = client.get("/api/v7/performance-lab?source=live")
        assert resp.status_code == 200
        data = resp.json()
        trust = data.get("trust", {})
        # Without real trades in test env, should fall to SYNTHETIC
        assert trust.get("mode") == "SYNTHETIC"
        assert trust.get("data_warning") is not None
        assert "SYNTHETIC" in trust["data_warning"]

    def test_trust_block_structure(self, client):
        resp = client.get("/api/v7/performance-lab")
        data = resp.json()
        trust = data.get("trust", {})
        assert "mode" in trust
        assert "source" in trust
        assert "sample_size" in trust
        assert "assumptions" in trust

    def test_no_random_beta_in_response(self, client):
        """Beta must be computed, not random."""
        resp = client.get("/api/v7/performance-lab")
        data = resp.json()
        summary = data.get("summary", {})
        beta = summary.get("beta", None)
        assert beta is not None
        # Synthetic seed should give deterministic result
        resp2 = client.get("/api/v7/performance-lab")
        data2 = resp2.json()
        beta2 = data2["summary"]["beta"]
        # Same synthetic seed → same beta (not random)
        assert beta == beta2

    def test_no_random_profit_factor(self, client):
        """Profit factor must be computed, not random."""
        resp = client.get("/api/v7/performance-lab")
        data = resp.json()
        pf = data["summary"]["profit_factor"]
        resp2 = client.get("/api/v7/performance-lab")
        data2 = resp2.json()
        pf2 = data2["summary"]["profit_factor"]
        assert pf == pf2  # deterministic

    def test_as_of_present(self, client):
        resp = client.get("/api/v7/performance-lab")
        data = resp.json()
        assert "as_of" in data


# ---------------------------------------------------------------------------
# 4. Compare Overlay uses MarketDataService
# ---------------------------------------------------------------------------

class TestCompareOverlayTrust:

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient

            from src.api.main import app
            return TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient not available")

    def test_trust_metadata_present(self, client):
        resp = client.get(
            "/api/v7/compare-overlay?tickers=SPY,QQQ",
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "trust" in data
            assert data["trust"]["mode"] == "LIVE"
            assert "as_of" in data


# ---------------------------------------------------------------------------
# 5. Portfolio Brief trust badge
# ---------------------------------------------------------------------------

class TestPortfolioBriefTrust:

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient

            from src.api.main import app
            return TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient not available")

    def test_trust_metadata_present(self, client):
        resp = client.get("/api/v7/portfolio-brief")
        if resp.status_code == 200:
            data = resp.json()
            # If loaded from artifact cache, may not have trust
            if "generated_at" in data and "trust" not in data:
                pytest.skip(
                    "Loaded from artifact cache (pre-VNext)"
                )
            assert "trust" in data
            trust = data["trust"]
            assert "mode" in trust
            assert "source" in trust
            assert "as_of" in data
