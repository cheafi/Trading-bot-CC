"""
Sprint 67 Tests
================
- RegimeService singleton (fetch, cache, fallback)
- RegimeService wired into SectorPipeline (auto-fetch)
- Peer rank in batch output
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ── RegimeService ──


def test_regime_service_default():
    """RegimeService returns valid regime dict."""
    from src.services.regime_service import RegimeService

    RegimeService.invalidate()
    regime = RegimeService.get()
    assert "trend" in regime
    assert "risk_score" in regime
    assert "should_trade" in regime


def test_regime_service_cache():
    """Second call returns cached result instantly."""
    import time

    from src.services.regime_service import RegimeService

    r1 = RegimeService.get()
    t0 = time.time()
    r2 = RegimeService.get()
    elapsed = time.time() - t0
    assert elapsed < 1.0, f"Cache miss: {elapsed:.1f}s"
    assert r1["trend"] == r2["trend"]


def test_regime_service_invalidate():
    """Invalidate clears cache."""
    from src.services.regime_service import RegimeService

    RegimeService.get()
    assert RegimeService._cache_time > 0
    RegimeService.invalidate()
    assert RegimeService._cache_time == 0


def test_regime_service_default_fallback():
    """_default_regime returns valid structure."""
    from src.services.regime_service import RegimeService

    d = RegimeService._default_regime()
    assert d["trend"] == "SIDEWAYS"
    assert d["should_trade"] is True
    assert d["source"] == "default"


# ── Pipeline auto-fetch regime ──


def test_pipeline_auto_regime():
    """Pipeline works with regime=None (auto-fetch)."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()
    signal = {
        "ticker": "AAPL",
        "rsi": 55,
        "volume_ratio": 1.5,
        "rs_rank": 70,
    }
    result = pipeline.process_batch([signal])
    assert len(result) == 1
    assert result[0].decision.action in ("TRADE", "WATCH", "WAIT", "NO_TRADE")


def test_pipeline_empty_regime():
    """Pipeline with empty regime dict auto-fetches."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()
    signal = {
        "ticker": "MSFT",
        "rsi": 50,
        "volume_ratio": 2.0,
        "rs_rank": 80,
    }
    result = pipeline.process_batch([signal], regime={})
    assert len(result) == 1


# ── Peer rank ──


def test_peer_rank_in_batch():
    """Batch output includes peer_rank field."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()
    signals = [
        {
            "ticker": "NVDA",
            "rsi": 55,
            "volume_ratio": 2.0,
            "rs_rank": 90,
            "sector": "Technology",
        },
        {
            "ticker": "AMD",
            "rsi": 50,
            "volume_ratio": 1.5,
            "rs_rank": 70,
            "sector": "Technology",
        },
        {
            "ticker": "JPM",
            "rsi": 45,
            "volume_ratio": 1.2,
            "rs_rank": 60,
            "sector": "Financials",
        },
    ]
    regime = {"trend": "UPTREND", "risk_score": 30}
    results = pipeline.process_batch(signals, regime)
    assert len(results) == 3
    # All should have peer_rank
    for r in results:
        pr = r.signal.get("peer_rank", "")
        assert "of" in pr, f"Missing peer_rank for {r.signal['ticker']}"


def test_peer_rank_format():
    """Peer rank format is 'N of M in bucket'."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()
    signals = [
        {
            "ticker": "AAPL",
            "rsi": 55,
            "volume_ratio": 2.0,
            "rs_rank": 90,
            "sector": "Technology",
        },
        {
            "ticker": "GOOGL",
            "rsi": 50,
            "volume_ratio": 1.5,
            "rs_rank": 70,
            "sector": "Technology",
        },
    ]
    regime = {"trend": "UPTREND", "risk_score": 30}
    results = pipeline.process_batch(signals, regime)
    for r in results:
        pr = r.signal["peer_rank"]
        parts = pr.split(" of ")
        assert len(parts) == 2
        assert parts[0] in ("1", "2")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
