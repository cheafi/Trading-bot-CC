"""
Sprint 100 — Execution Intelligence + Risk Guards test suite
"""

from __future__ import annotations

# ── Execution Cost Engine ─────────────────────────────────────────────────────


def test_execution_cost_estimate():
    from src.engines.execution_cost import ExecutionCostEngine

    engine = ExecutionCostEngine()
    est = engine.estimate(
        ticker="AAPL",
        side="BUY",
        shares=100,
        price=185.0,
        atr=2.5,
        adv=60_000_000,
        twap_minutes=30,
    )
    assert est.commission >= 1.00, "Min commission should be $1"
    assert est.total_cost_usd > 0
    assert 0 < est.total_cost_bps < 100, f"Unexpected bps: {est.total_cost_bps}"


def test_execution_cost_slippage_sign():
    from src.engines.execution_cost import ExecutionCostEngine

    engine = ExecutionCostEngine()

    # BUY filled higher than expected = positive (bad) slippage
    rec = engine.record_fill("SPY", "BUY", 10, 500.0, 500.5, commission=0.05)
    assert rec.slippage_bps > 0, "BUY filled above expected should be +bps"

    # SELL filled lower than expected = positive (bad) slippage
    rec2 = engine.record_fill("SPY", "SELL", 10, 500.0, 499.5, commission=0.05)
    assert rec2.slippage_bps > 0, "SELL filled below expected should be +bps"


def test_execution_quality_stats_returns_dict():
    from src.engines.execution_cost import ExecutionCostEngine

    stats = ExecutionCostEngine().quality_stats(lookback_days=1)
    assert isinstance(stats, dict)
    assert "fills" in stats


def test_options_estimate():
    from src.engines.execution_cost import ExecutionCostEngine

    est = ExecutionCostEngine().estimate_options(
        contracts=2, premium=3.50, underlying_atr=2.0
    )
    assert est.commission == 2 * 0.65
    assert est.total_cost_usd > 0


# ── MTF Confluence ────────────────────────────────────────────────────────────


def test_rsi_range():
    import math as _math
    import pandas as pd
    from src.engines.mtf_confluence import _rsi

    # Use oscillating prices so both gains and losses exist
    prices = pd.Series([100 + 10 * _math.sin(i * 0.3) + i * 0.1 for i in range(60)])
    rsi = _rsi(prices, 14)
    valid = rsi.dropna()
    assert len(valid) > 0, "RSI returned all NaN for oscillating series"
    assert all(0 <= v <= 100 for v in valid), "RSI must be in [0, 100]"


def test_macd_hist_sign():
    import pandas as pd
    from src.engines.mtf_confluence import _macd_hist

    # Trending up → MACD hist should be positive at end
    prices = pd.Series([100 + i for i in range(60)])
    hist = _macd_hist(prices)
    assert hist.dropna().iloc[-1] > 0


def test_confluence_bypass_on_empty_data():
    import asyncio
    from src.engines.mtf_confluence import MTFConfluenceGate

    gate = MTFConfluenceGate()
    result = asyncio.get_event_loop().run_until_complete(
        gate.check("FAKE_TICKER_XYZ", daily_data=None, market_data_service=None)
    )
    # Should fail-open (approved=True) when data unavailable
    assert result.approved is True
    assert "bypass" in " ".join(result.notes).lower()


# ── MultiLayerRanker MTF wiring ───────────────────────────────────────────────


def _make_mock_result(mtf_score=None):
    """Build a minimal mock pipeline result for ranker tests."""

    class Fit:
        timing_fit = 8.0
        sector_fit = 8.0
        regime_fit = 8.0
        execution_fit = 8.0
        risk_fit = 8.0
        final_score = 8.0
        evidence_conflicts = []

    class Conf:
        thesis = 0.7
        final = 0.7

    class Sector:
        class leader_status:
            value = "PEER"

    class Decision:
        action = "TRADE"

    class Result:
        signal = {"ticker": "TEST", "score": 8, "vol_ratio": 1.5, "rs_rank": 70}
        fit = Fit()
        confidence = Conf()
        sector = Sector()
        decision = Decision()

    r = Result()
    if mtf_score is not None:
        r.signal["mtf_confluence_score"] = mtf_score
    return r


def test_mtf_boosts_action_score():
    from src.engines.multi_ranker import MultiLayerRanker

    ranker = MultiLayerRanker()
    r_high = _make_mock_result(mtf_score=1.0)
    r_low = _make_mock_result(mtf_score=0.0)
    r_none = _make_mock_result(mtf_score=None)
    score_high = ranker._action(r_high)
    score_low = ranker._action(r_low)
    score_none = ranker._action(r_none)
    assert (
        score_high > score_none > score_low
    ), f"MTF should boost/penalise action: high={score_high:.1f} none={score_none:.1f} low={score_low:.1f}"


def test_mtf_boosts_conviction_score():
    from src.engines.multi_ranker import MultiLayerRanker

    ranker = MultiLayerRanker()
    r_high = _make_mock_result(mtf_score=0.80)
    r_low = _make_mock_result(mtf_score=0.25)
    assert ranker._conviction(r_high) > ranker._conviction(r_low)


# ── Risk Guard helpers ────────────────────────────────────────────────────────


def test_pearson_known_correlation():
    from src.api.routers.risk_guard import _pearson

    # Perfectly correlated series
    a = [i * 0.01 for i in range(50)]
    b = [i * 0.02 for i in range(50)]
    assert abs(_pearson(a, b) - 1.0) < 0.01

    # Uncorrelated (alternating)
    a2 = [1.0, -1.0] * 25
    b2 = [1.0, 1.0, -1.0, -1.0] * 12 + [1.0, 1.0]
    corr = _pearson(a2, b2)
    assert abs(corr) < 0.5


def test_parametric_var_positive():
    from src.api.routers.risk_guard import _parametric_var

    returns = [-0.01, 0.02, -0.005, 0.015, -0.008, 0.012] * 10
    var = _parametric_var(returns, confidence=0.95, position_usd=10_000.0)
    assert var > 0, "VaR must be positive"
    assert var < 10_000.0, "VaR must be less than full position"


def test_risk_guard_router_prefix():
    from src.api.routers.risk_guard import router

    assert router.prefix == "/api/v7/risk"
    route_paths = [getattr(r, "path", "") for r in router.routes]
    assert any("correlation-guard" in p for p in route_paths)
    assert any("var-gate" in p for p in route_paths)
    assert any("concentration" in p for p in route_paths)
    assert any("summary" in p for p in route_paths)


# ── Kelly sizing sanity ───────────────────────────────────────────────────────


def test_kelly_formula_manual():
    """
    Kelly formula: f* = (p*b - q) / b
    With p=0.55, b=2 (W/L ratio): f* = (0.55*2 - 0.45) / 2 = 0.325
    """
    p, b = 0.55, 2.0
    q = 1 - p
    kelly = max(0, (p * b - q) / b)
    assert abs(kelly - 0.325) < 0.001

    # Quarter-Kelly should be 0.325 * 0.25 = 0.08125
    quarter = kelly * 0.25
    assert abs(quarter - 0.08125) < 0.001
