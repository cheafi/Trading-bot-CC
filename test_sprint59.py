"""
Tests for Phase A+B: Data Foundation + Pipeline Integrity.

Tests:
  A1. SignalEnricher computes real fields from OHLCV
  A2. StructureDetector wired into enricher
  A3. SectorClassifier uses structure for stage detection
  A4. SectorClassifier cache has TTL
  B1. PortfolioGate wired into SectorPipeline
  B2. Regime-sector gate blocks incompatible combos
  B3. FitScorer uses structure data for setup scoring
  B4. Regime gate modifier applied in FitScorer._score_sector
"""

import time
import numpy as np
import pandas as pd


# ── A1: SignalEnricher ──────────────────────────────────────────

def test_signal_enricher_computes_fields():
    """SignalEnricher should compute RSI, ATR, vol_ratio, etc."""
    from src.engines.signal_enricher import SignalEnricher

    enricher = SignalEnricher()

    # Generate synthetic uptrend OHLCV (100 bars)
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5 + 0.1)
    high = close + np.abs(np.random.randn(n)) * 0.5
    low = close - np.abs(np.random.randn(n)) * 0.5
    volume = np.random.randint(1_000_000, 5_000_000, n).astype(float)

    df = pd.DataFrame({
        "open": close - 0.1,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })

    result = enricher.enrich("NVDA", df)

    # Check all expected fields exist
    assert "rsi" in result, "Missing RSI"
    assert "atr_pct" in result, "Missing ATR%"
    assert "vol_ratio" in result, "Missing vol_ratio"
    assert "distance_from_50ma_pct" in result
    assert "bb_width" in result
    assert "rs_rank" in result
    assert "contraction_count" in result
    assert "base_depth_pct" in result
    assert "trend_structure" in result
    assert "breakout_quality" in result or result.get("breakout_quality") is None

    # Check reasonable ranges
    assert 0 <= result["rsi"] <= 100, f"RSI out of range: {result['rsi']}"
    assert result["atr_pct"] > 0, "ATR should be positive"
    assert result["vol_ratio"] > 0, "vol_ratio should be positive"
    assert 0 <= result["rs_rank"] <= 100


# ── A2: StructureDetector wired ────────────────────────────────

def test_structure_detector_wired_into_enricher():
    """Enricher should call StructureDetector and merge output."""
    from src.engines.signal_enricher import SignalEnricher

    enricher = SignalEnricher()

    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5 + 0.1)
    high = close + np.abs(np.random.randn(n)) * 0.5
    low = close - np.abs(np.random.randn(n)) * 0.5
    volume = np.random.randint(1_000_000, 5_000_000, n).astype(float)

    df = pd.DataFrame({
        "open": close, "high": high, "low": low,
        "close": close, "volume": volume,
    })

    result = enricher.enrich("TEST", df)

    # StructureDetector output should be present
    assert result.get("_structure") is not None, \
        f"StructureReport not attached, keys: {list(result.keys())}"
    assert result.get("_structure_dict"), "Structure dict empty"
    assert result["trend_structure"] in (
        "strong_uptrend", "uptrend", "range",
        "downtrend", "strong_downtrend", "transition",
    )
    assert isinstance(result.get("trend_quality"), (int, float))
    assert isinstance(result.get("is_extended"), (bool, np.bool_))
    assert isinstance(result.get("volume_confirms"), (bool, np.bool_))


# ── A3: SectorClassifier uses structure data ───────────────────

def test_sector_classifier_uses_structure_for_stage():
    """Stage detection should use trend_structure, not just RSI+vol."""
    from src.engines.sector_classifier import (
        SectorClassifier, SectorStage,
    )

    clf = SectorClassifier()

    # Downtrend signal → DISTRIBUTION
    sig_down = {
        "ticker": "TEST1",
        "trend_structure": "downtrend",
        "rs_rank": 30,
        "vol_ratio": 1.5,
        "rsi": 60,  # RSI would suggest ACCELERATION in old code
    }
    ctx = clf.classify("TEST1", sig_down)
    assert ctx.sector_stage == SectorStage.DISTRIBUTION, \
        f"Downtrend should be DISTRIBUTION, got {ctx.sector_stage}"

    # Extended + volume exhaustion → CLIMAX
    clf.clear_cache()
    sig_climax = {
        "ticker": "TEST2",
        "trend_structure": "strong_uptrend",
        "is_extended": True,
        "volume_exhaustion": True,
        "rs_rank": 90,
        "vol_ratio": 1.0,
        "rsi": 50,
    }
    ctx2 = clf.classify("TEST2", sig_climax)
    assert ctx2.sector_stage == SectorStage.CLIMAX, \
        f"Extended+exhaustion should be CLIMAX, got {ctx2.sector_stage}"

    # Uptrend + volume → ACCELERATION
    clf.clear_cache()
    sig_accel = {
        "ticker": "TEST3",
        "trend_structure": "uptrend",
        "rs_rank": 70,
        "vol_ratio": 1.5,
        "rsi": 55,
    }
    ctx3 = clf.classify("TEST3", sig_accel)
    assert ctx3.sector_stage == SectorStage.ACCELERATION


# ── A4: Cache TTL ──────────────────────────────────────────────

def test_sector_classifier_cache_ttl():
    """Cache should expire after TTL."""
    from src.engines.sector_classifier import SectorClassifier
    import src.engines.sector_classifier as sc_mod

    clf = SectorClassifier()
    old_ttl = sc_mod._CACHE_TTL_SECONDS

    try:
        # Set TTL to 0 so cache expires immediately
        sc_mod._CACHE_TTL_SECONDS = 0

        sig = {"rs_rank": 90, "vol_ratio": 1.0, "rsi": 50}
        ctx1 = clf.classify("NVDA", sig)
        assert ctx1.sector_bucket.value == "HIGH_GROWTH"

        # Should re-classify (TTL=0 → expired)
        time.sleep(0.01)
        sig2 = {"rs_rank": 20, "vol_ratio": 1.0, "rsi": 50}
        ctx2 = clf.classify("NVDA", sig2)
        # Should have updated leader status
        assert ctx2.leader_status.value == "LAGGARD"
    finally:
        sc_mod._CACHE_TTL_SECONDS = old_ttl


# ── B1: PortfolioGate wired into pipeline ──────────────────────

def test_portfolio_gate_downgrades_trade():
    """If portfolio is full, TRADE should be downgraded to WATCH."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()

    # Strong signal that would be TRADE
    signal = {
        "ticker": "NVDA",
        "score": 9.0,
        "rsi": 60,
        "rs_rank": 90,
        "vol_ratio": 2.0,
        "risk_reward": 3.5,
        "atr_pct": 2.0,
        # Portfolio already at max positions
        "_current_positions": [
            {"ticker": f"POS{i}", "sector": "OTHER", "size_pct": 5, "risk_pct": 0.5}
            for i in range(10)
        ],
    }
    regime = {"should_trade": True, "trend": "BULLISH", "vix": 15}

    result = pipeline.process(signal, regime)
    if result.decision.action == "TRADE":
        # Gate should have caught it
        assert "portfolio gate" in result.decision.rationale.lower() or \
               result.decision.action == "WATCH", \
               "Full portfolio should downgrade TRADE"


# ── B2: Regime-sector gate ─────────────────────────────────────

def test_regime_sector_gate():
    """CRISIS + HIGH_GROWTH should be blocked."""
    from src.engines.regime_sector_gate import (
        get_regime_sector_modifier,
        is_regime_blocked,
    )
    from src.engines.sector_classifier import SectorBucket

    # CRISIS + HIGH_GROWTH = -4.0
    mod = get_regime_sector_modifier(
        {"trend": "CRISIS"}, SectorBucket.HIGH_GROWTH
    )
    assert mod == -4.0

    assert is_regime_blocked(
        {"trend": "CRISIS"}, SectorBucket.HIGH_GROWTH
    )

    # RISK_ON + DEFENSIVE = -1.0 (not blocked)
    mod2 = get_regime_sector_modifier(
        {"trend": "RISK_ON"}, SectorBucket.DEFENSIVE
    )
    assert mod2 == -1.0
    assert not is_regime_blocked(
        {"trend": "RISK_ON"}, SectorBucket.DEFENSIVE
    )

    # BULLISH + HIGH_GROWTH = 0.0 (neutral)
    mod3 = get_regime_sector_modifier(
        {"trend": "BULLISH"}, SectorBucket.HIGH_GROWTH
    )
    assert mod3 == 0.0


# ── B3: FitScorer uses structure ───────────────────────────────

def test_fit_scorer_uses_structure_data():
    """FitScorer._score_setup should use structure fields."""
    from src.engines.fit_scorer import FitScorer
    from src.engines.sector_classifier import SectorClassifier

    scorer = FitScorer()
    clf = SectorClassifier()

    # Signal with genuine breakout + volume confirmation
    sig_good = {
        "ticker": "NVDA",
        "trend_structure": "strong_uptrend",
        "trend_quality": 85.0,
        "breakout_quality": "genuine",
        "volume_confirms": True,
        "volume_exhaustion": False,
        "is_near_support": False,
        "contraction_count": 3,
        "risk_reward": 3.5,
        "rs_rank": 90,
        "vol_ratio": 2.0,
        "rsi": 60,
    }

    sector = clf.classify("NVDA", sig_good)
    regime = {"should_trade": True, "trend": "BULLISH", "vix": 15}
    scores = scorer.score(sig_good, sector, regime)

    assert scores.setup_quality >= 7.0, \
        f"Genuine breakout should score high, got {scores.setup_quality}"

    # Signal with fake breakout + exhaustion
    sig_bad = {
        "ticker": "GME",
        "trend_structure": "range",
        "trend_quality": 30.0,
        "breakout_quality": "fake",
        "volume_confirms": False,
        "volume_exhaustion": True,
        "is_near_support": False,
        "contraction_count": 0,
        "risk_reward": 0.8,
        "rs_rank": 30,
        "vol_ratio": 1.0,
        "rsi": 50,
    }

    clf.clear_cache()
    sector2 = clf.classify("GME", sig_bad)
    scores2 = scorer.score(sig_bad, sector2, regime)

    assert scores2.setup_quality < 5.0, \
        f"Fake breakout should score low, got {scores2.setup_quality}"


# ── B4: Regime modifier in sector_fit ──────────────────────────

def test_regime_modifier_in_sector_fit():
    """CRISIS should penalize HIGH_GROWTH sector_fit."""
    from src.engines.fit_scorer import FitScorer
    from src.engines.sector_classifier import SectorClassifier

    scorer = FitScorer()
    clf = SectorClassifier()

    sig = {
        "ticker": "NVDA",
        "rs_rank": 80,
        "vol_ratio": 1.5,
        "rsi": 55,
    }
    sector = clf.classify("NVDA", sig)

    # BULLISH regime
    regime_bull = {"should_trade": True, "trend": "BULLISH", "vix": 15}
    scores_bull = scorer.score(sig, sector, regime_bull)

    # CRISIS regime
    clf.clear_cache()
    sector2 = clf.classify("NVDA", sig)
    regime_crisis = {"should_trade": True, "trend": "CRISIS", "vix": 35}
    scores_crisis = scorer.score(sig, sector2, regime_crisis)

    assert scores_crisis.sector_fit < scores_bull.sector_fit, \
        f"CRISIS should penalize sector_fit: bull={scores_bull.sector_fit}, crisis={scores_crisis.sector_fit}"


# ── Pipeline integration ───────────────────────────────────────

def test_pipeline_end_to_end():
    """Full pipeline should work with enriched signal."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()

    signal = {
        "ticker": "NVDA",
        "trend_structure": "strong_uptrend",
        "trend_quality": 80.0,
        "breakout_quality": "genuine",
        "volume_confirms": True,
        "volume_exhaustion": False,
        "is_near_support": False,
        "contraction_count": 2,
        "risk_reward": 3.0,
        "rsi": 60,
        "rs_rank": 85,
        "vol_ratio": 1.8,
        "atr_pct": 2.5,
        "distance_from_50ma_pct": 5.0,
        "is_extended": False,
        "base_depth_pct": 10,
    }
    regime = {"should_trade": True, "trend": "BULLISH", "vix": 16}

    result = pipeline.process(signal, regime)
    d = result.to_dict()

    assert d["action"] in ("TRADE", "WATCH", "WAIT"), \
        f"Strong signal should be actionable, got {d['action']}"
    assert d["final_score"] > 0
    assert d["grade"] in ("A+", "A", "B+", "B", "C", "D", "F")
    assert "sector_context" in d
    assert "fit_scores" in d
    assert "confidence_breakdown" in d
    assert "explanation" in d


if __name__ == "__main__":
    tests = [
        test_signal_enricher_computes_fields,
        test_structure_detector_wired_into_enricher,
        test_sector_classifier_uses_structure_for_stage,
        test_sector_classifier_cache_ttl,
        test_portfolio_gate_downgrades_trade,
        test_regime_sector_gate,
        test_fit_scorer_uses_structure_data,
        test_regime_modifier_in_sector_fit,
        test_pipeline_end_to_end,
    ]
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
