"""Sprint 46 tests — Honest confidence, shadow resolve, Swing_Project features."""
import pytest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

def test_honest_confidence_label():
    from src.api.main import _honest_confidence_label
    r = _honest_confidence_label(0.72)
    assert "composite" in r
    assert "honest_note" in r
    assert r["composite"] == 0.72

def test_rs_vs_spy():
    from src.api.main import _compute_rs_vs_spy
    stock = list(range(100, 200))  # uptrend
    spy = list(range(100, 200))    # same trend
    r = _compute_rs_vs_spy(stock, spy)
    assert "rs_score" in r
    assert "rs_trending_up" in r
    assert isinstance(r["rs_score"], int)

def test_rs_vs_spy_outperformance():
    from src.api.main import _compute_rs_vs_spy
    stock = [100 + i*1.5 for i in range(100)]  # faster uptrend
    spy = [100 + i*0.5 for i in range(100)]    # slower
    r = _compute_rs_vs_spy(stock, spy)
    assert r["rs_return_20d"] > 0
    assert r["rs_score"] >= 2

def test_distribution_days():
    from src.api.main import _detect_distribution_days
    data = [{"close": 100 + i * 0.1, "volume": 1000000} for i in range(30)]
    r = _detect_distribution_days(data)
    assert "distribution_day_count" in r
    assert "regime_pressure" in r
    assert r["regime_pressure"] in ("neutral", "moderate_distribution", "heavy_distribution")

def test_vcp_pattern():
    from src.api.main import _detect_vcp_pattern
    import math
    # Create synthetic tightening pattern
    highs = [100 + 10*math.sin(i/5) + max(0, 20-i*0.3) for i in range(120)]
    lows = [90 + 10*math.sin(i/5) - max(0, 20-i*0.3) for i in range(120)]
    closes = [(h+l)/2 for h,l in zip(highs, lows)]
    volumes = [1000000 - i*5000 for i in range(120)]
    r = _detect_vcp_pattern(highs, lows, closes, volumes)
    assert "is_vcp" in r
    assert "vcp_score" in r
    assert "volume_dryup_ratio" in r

def test_volume_quality():
    from src.api.main import _compute_volume_quality
    volumes = [1000000] * 50
    closes = [100 + i*0.1 for i in range(50)]
    r = _compute_volume_quality(volumes, closes)
    assert "volume_quality_score" in r
    assert "up_down_volume_ratio" in r
    assert "pocket_pivot_detected" in r

def test_pullback_entry():
    from src.api.main import _detect_pullback_entry
    closes = list(range(80, 105))  # uptrend
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000000] * len(closes)
    sma20 = sum(closes[-20:]) / 20
    r = _detect_pullback_entry(closes, highs, lows, volumes, sma20)
    assert "pullback_state" in r
    assert "entry_ready" in r
    assert "distance_to_sma20_pct" in r

def test_leadership_actionability():
    from src.api.main import _compute_leadership_actionability
    rs = {"rs_score": 4, "rs_trending_up": True}
    vcp = {"vcp_score": 0.7}
    vol = {"volume_quality_score": 3}
    pb = {"pullback_state": "pullback-entry-ready"}
    r = _compute_leadership_actionability(rs, vcp, vol, pb, 55.0, 2.0, 150.0, 130.0)
    assert "leadership_score" in r
    assert "actionability_score" in r
    assert "final_score" in r
    assert "setup_tag" in r
    assert 0 <= r["final_score"] <= 100

def test_leadership_tag_classification():
    from src.api.main import _compute_leadership_actionability
    # Strong leader + actionable
    r = _compute_leadership_actionability(
        {"rs_score": 5, "rs_trending_up": True},
        {"vcp_score": 0.9}, {"volume_quality_score": 5},
        {"pullback_state": "pullback-entry-ready"},
        55.0, 2.0, 200.0, 130.0)
    assert r["setup_tag"] == "leader-actionable"

def test_days_to_earnings():
    """_days_to_earnings is async and needs mds param — just verify it exists."""
    from src.api.main import _days_to_earnings
    import inspect
    assert callable(_days_to_earnings)
    assert inspect.iscoroutinefunction(_days_to_earnings)

def test_shadow_resolve_endpoint_exists():
    from src.api.main import app
    routes = [r.path for r in app.routes]
    assert "/api/v6/shadow-resolve" in routes

def test_swing_endpoints_exist():
    from src.api.main import app
    routes = [r.path for r in app.routes]
    assert "/api/v6/rs-strength/{ticker}" in routes
    assert "/api/v6/vcp-scan/{ticker}" in routes
    assert "/api/v6/swing-analysis/{ticker}" in routes
    assert "/api/v6/swing-batch" in routes
    assert "/api/v6/distribution-days" in routes

def test_distribution_days_heavy():
    from src.api.main import _detect_distribution_days
    # Simulate heavy distribution: price down on higher volume
    data = []
    for i in range(30):
        data.append({"close": 100 - i*0.5, "volume": 1000000 + i*50000})
    r = _detect_distribution_days(data)
    assert r["distribution_day_count"] >= 3

def test_rs_short_data():
    from src.api.main import _compute_rs_vs_spy
    r = _compute_rs_vs_spy([100, 101], [100, 101])
    assert r["rs_score"] == 0  # too short
