"""
Tests for Phase C+D: Scanner Reality + Output Quality.

Tests:
  C1. Flow scanners use computed fields (not boolean flags)
  C2. RSRanker produces universe percentile ranks
  C3. SimilarPatternScanner returns real hits for clusters
  C4. EdgeDecayScanner detects exhaustion patterns
  C5. BreakoutScanner uses breakout_quality from StructureDetector
  D1. Decision includes position_size_pct
  D2. Discord embed includes regime, timestamp, size
  D4. Alert deduplication works
"""


# ── C1: Flow scanners use computed fields ──────────────────────

def test_flow_scanners_use_computed_fields():
    """Flow scanners should trigger on volume+RS+trend, not boolean flags."""
    from src.engines.scanner_matrix import (
        InsiderScanner,
        InstitutionalScanner,
        OptionsFlowScanner,
    )

    # Signal with computed fields (no boolean flags)
    sig = {
        "ticker": "NVDA",
        "vol_ratio": 3.0,
        "rs_rank": 90,
        "trend_structure": "strong_uptrend",
        "bb_width": 3.5,
        "volume_confirms": True,
        "rsi": 65,
    }
    regime = {"trend": "BULLISH"}

    # OptionsFlowScanner: high vol + uptrend + tight BB
    opts = OptionsFlowScanner().scan([sig], regime)
    assert len(opts) >= 1, "OptionsFlowScanner should detect vol+tight BB"

    # InsiderScanner: quiet accumulation (low vol + strong RS)
    sig_quiet = dict(sig, vol_ratio=0.6, ticker="MSFT")
    insider = InsiderScanner().scan([sig_quiet], regime)
    assert len(insider) >= 1, "InsiderScanner should detect quiet accumulation"

    # InstitutionalScanner: high vol + leader RS + volume confirms
    inst = InstitutionalScanner().scan([sig], regime)
    assert len(inst) >= 1, "InstitutionalScanner should detect accumulation"


# ── C2: RSRanker ───────────────────────────────────────────────

def test_rs_ranker():
    """RSRanker should produce 0-100 percentile ranks."""
    from src.engines.rs_ranker import RSRanker

    ranker = RSRanker()

    universe = {
        "NVDA": {"21d": 15.0, "63d": 40.0, "126d": 80.0},
        "AAPL": {"21d": 5.0, "63d": 10.0, "126d": 20.0},
        "XOM": {"21d": -2.0, "63d": -5.0, "126d": 0.0},
        "KO": {"21d": 1.0, "63d": 2.0, "126d": 5.0},
        "GME": {"21d": -10.0, "63d": -20.0, "126d": -30.0},
    }
    spy = {"21d": 3.0, "63d": 8.0, "126d": 15.0}

    ranks = ranker.rank_universe(universe, spy)

    assert len(ranks) == 5
    assert all(0 <= v <= 100 for v in ranks.values())
    # NVDA should rank highest (best excess returns)
    assert ranks["NVDA"] > ranks["XOM"]
    assert ranks["NVDA"] > ranks["GME"]


def test_rs_ranker_from_closes():
    """RSRanker.rank_from_closes with raw price arrays."""
    import numpy as np

    from src.engines.rs_ranker import RSRanker

    ranker = RSRanker()
    np.random.seed(42)

    # Generate 130 days of prices
    universe = {
        "STOCK_A": list(100 + np.cumsum(np.random.randn(130) * 0.5 + 0.2)),
        "STOCK_B": list(100 + np.cumsum(np.random.randn(130) * 0.5 - 0.1)),
        "STOCK_C": list(100 + np.cumsum(np.random.randn(130) * 0.5)),
    }
    spy = list(100 + np.cumsum(np.random.randn(130) * 0.3 + 0.05))

    ranks = ranker.rank_from_closes(universe, spy)
    assert len(ranks) == 3
    assert all(0 <= v <= 100 for v in ranks.values())


# ── C3: SimilarPatternScanner ──────────────────────────────────

def test_similar_pattern_scanner():
    """SimilarPatternScanner should detect pattern clusters."""
    from src.engines.scanner_matrix import SimilarPatternScanner

    # 4 signals with same trend+breakout pattern
    signals = [
        {"ticker": "NVDA", "trend_structure": "uptrend", "breakout_quality": "genuine"},
        {"ticker": "AMD", "trend_structure": "uptrend", "breakout_quality": "genuine"},
        {"ticker": "AVGO", "trend_structure": "uptrend", "breakout_quality": "genuine"},
        {"ticker": "MRVL", "trend_structure": "uptrend", "breakout_quality": "genuine"},
        {"ticker": "XOM", "trend_structure": "downtrend", "breakout_quality": None},
    ]
    regime = {}

    hits = SimilarPatternScanner().scan(signals, regime)
    assert len(hits) >= 4, f"Should find cluster of 4, got {len(hits)}"
    assert any("NVDA" in h.ticker for h in hits)


# ── C4: EdgeDecayScanner ───────────────────────────────────────

def test_edge_decay_scanner():
    """EdgeDecayScanner should detect exhaustion patterns."""
    from src.engines.scanner_matrix import EdgeDecayScanner

    signals = [
        {
            "ticker": "EXHAUSTED",
            "volume_exhaustion": True,
            "breakout_quality": "exhaustion",
            "is_extended": True,
            "rsi": 80,
            "liquidity_trap_risk": 0.6,
        },
        {
            "ticker": "HEALTHY",
            "volume_exhaustion": False,
            "breakout_quality": "genuine",
            "is_extended": False,
            "rsi": 55,
            "liquidity_trap_risk": 0.1,
        },
    ]
    regime = {}

    hits = EdgeDecayScanner().scan(signals, regime)
    assert len(hits) >= 1
    assert hits[0].ticker == "EXHAUSTED"
    assert hits[0].is_warning


# ── C5: BreakoutScanner uses breakout_quality ──────────────────

def test_breakout_scanner_uses_quality():
    """BreakoutScanner should use breakout_quality from StructureDetector."""
    from src.engines.scanner_matrix import BreakoutScanner

    signals = [
        {"ticker": "GOOD", "breakout_quality": "genuine", "vol_ratio": 2.0},
        {"ticker": "BAD", "breakout_quality": "fake", "vol_ratio": 0.5},
    ]
    regime = {}

    hits = BreakoutScanner().scan(signals, regime)
    assert len(hits) == 2

    good = next(h for h in hits if h.ticker == "GOOD")
    bad = next(h for h in hits if h.ticker == "BAD")
    assert good.score > bad.score, \
        f"Genuine should score higher: {good.score} vs {bad.score}"


# ── D1: Position sizing in Decision ───────────────────────────

def test_decision_has_position_size():
    """TRADE decisions should include position_size_pct."""
    from src.engines.sector_pipeline import SectorPipeline

    pipeline = SectorPipeline()
    signal = {
        "ticker": "NVDA",
        "trend_structure": "strong_uptrend",
        "trend_quality": 90.0,
        "breakout_quality": "genuine",
        "volume_confirms": True,
        "volume_exhaustion": False,
        "contraction_count": 3,
        "risk_reward": 4.0,
        "rsi": 60,
        "rs_rank": 90,
        "vol_ratio": 2.0,
        "atr_pct": 2.0,
        "distance_from_50ma_pct": 5.0,
        "is_extended": False,
        "base_depth_pct": 8,
    }
    regime = {"should_trade": True, "trend": "BULLISH", "vix": 14}

    result = pipeline.process(signal, regime)
    d = result.to_dict()

    if d["action"] == "TRADE":
        assert d["decision"]["position_size_pct"] > 0, \
            "TRADE should have position size"
        assert d["decision"]["size_rationale"], \
            "Should have size rationale"


# ── D2: Discord embed includes regime + timestamp ─────────────

def test_discord_embed_has_regime_and_timestamp():
    """Discord embed should include regime label and timestamp."""
    from src.engines.sector_pipeline import SectorPipeline
    from src.notifications.sector_alerts import SectorAlertBuilder

    pipeline = SectorPipeline()
    signal = {
        "ticker": "NVDA",
        "rsi": 60,
        "rs_rank": 85,
        "vol_ratio": 1.8,
        "risk_reward": 3.0,
        "atr_pct": 2.0,
    }
    regime = {"should_trade": True, "trend": "BULLISH", "vix": 16}

    result = pipeline.process(signal, regime)
    builder = SectorAlertBuilder()
    alert = builder.build(result, regime=regime)

    assert alert.regime_label == "BULLISH"
    assert alert.regime_vix == 16
    assert alert.detected_at, "Should have timestamp"

    embed = alert.to_embed_dict()
    assert "now" in embed["footer"]["text"] or "UTC" in embed["footer"]["text"]
    # Check regime field exists
    field_names = [f["name"] for f in embed["fields"]]
    assert "🌍 Regime" in field_names


# ── D4: Alert deduplication ────────────────────────────────────

def test_alert_deduplication():
    """Same ticker+action should not re-alert same day."""
    from src.notifications.sector_alerts import (
        AlertType,
        SectorAlert,
        SectorAlertBuilder,
    )

    builder = SectorAlertBuilder()

    alerts = [
        SectorAlert(ticker="NVDA", action="TRADE",
                     alert_type=AlertType.ACTIONABLE),
        SectorAlert(ticker="NVDA", action="TRADE",
                     alert_type=AlertType.ACTIONABLE),
        SectorAlert(ticker="AMD", action="TRADE",
                     alert_type=AlertType.ACTIONABLE),
    ]

    filtered = builder.filter_actionable(alerts, dedup=True)
    # Should deduplicate NVDA TRADE (only 1 of 2 gets through)
    nvda_count = sum(1 for a in filtered if a.ticker == "NVDA")
    assert nvda_count == 1, f"Should dedup NVDA, got {nvda_count}"
    assert any(a.ticker == "AMD" for a in filtered)


if __name__ == "__main__":
    tests = [
        test_flow_scanners_use_computed_fields,
        test_rs_ranker,
        test_rs_ranker_from_closes,
        test_similar_pattern_scanner,
        test_edge_decay_scanner,
        test_breakout_scanner_uses_quality,
        test_decision_has_position_size,
        test_discord_embed_has_regime_and_timestamp,
        test_alert_deduplication,
    ]
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
