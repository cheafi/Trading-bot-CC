"""Sprint 114 — Opportunity Scanner.

Tests:
  1.  _robust_normalise returns bounded ordered values
  2.  _sigmoid midpoint and bounds
  3.  _rs_score positive when ticker outperforms SPY
  4.  _breakout_score strong setup scores high
  5.  _compression_score rewards tight volatility
  6.  _stage_score returns Stage 2 score for aligned trend
  7.  OpportunityCandidate serialises 2xATR stop/activation
  8.  run_opportunity_scanner returns ranked bull candidates
  9.  ScannerResult.to_dict exposes filter funnel keys
  10. REST GET /opportunity-scanner returns 200
  11. REST status shows separate cache keys for different filters
  12. REST invalidate clears cache and cache file
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd


def _price_series(base: float, step: float, size: int = 252) -> np.ndarray:
    return np.array([base + i * step for i in range(size)], dtype=float)


def _mock_indicators(close_arr, vol_arr):
    size = len(close_arr)
    idx = np.arange(size, dtype=float)
    return {
        "sma20": close_arr - 1.0,
        "sma50": close_arr - 2.0,
        "sma200": close_arr - 5.0,
        "rsi14": np.full(size, 62.0),
        "vol_ratio": np.full(size, 1.6),
        "atr14": np.full(size, 2.0),
        "bb_pct_b": np.full(size, 0.88),
        "bb_width": np.linspace(0.08, 0.03, size),
    }


def _make_router_result():
    from src.engines.opportunity_scanner import OpportunityCandidate, ScannerResult

    candidate = OpportunityCandidate(
        rank=1,
        ticker="AAA",
        engine="bull",
        score=88.4,
        leadership_score=91.0,
        actionability_score=76.0,
        is_leader=True,
        is_actionable=True,
        close=100.0,
        stop_loss=96.0,
        activation=104.0,
        atr14=2.0,
        rs_score=0.25,
        trend_score=0.9,
        volume_ratio=1.6,
        rsi14=62.0,
        above_50sma=True,
        above_200sma=True,
    )
    return ScannerResult(
        engine="bull",
        regime="BULL",
        universe_size=2,
        passed_initial=2,
        passed_rs=2,
        passed_pattern=2,
        candidates_raw=2,
        candidates_ranked=1,
        top_n=50,
        generated_at="2026-05-07T00:00:00+00:00",
        candidates=[candidate],
    )


def test_robust_normalise_returns_bounded_ordered_values():
    from src.engines.opportunity_scanner import _robust_normalise

    values = _robust_normalise([1.0, 2.0, 10.0])
    assert len(values) == 3
    assert all(0.0 < value < 1.0 for value in values)
    assert values[0] < values[1] < values[2]


def test_sigmoid_midpoint_and_bounds():
    from src.engines.opportunity_scanner import _sigmoid

    assert _sigmoid(0.0) == 0.5
    assert _sigmoid(-10.0) < 0.01
    assert _sigmoid(10.0) > 0.99


def test_rs_score_positive_when_ticker_beats_spy():
    from src.engines.opportunity_scanner import _rs_score

    ticker = np.array([100.0, 140.0])
    spy = np.array([100.0, 110.0])
    assert _rs_score(ticker, spy) > 0


def test_breakout_score_strong_setup_high():
    from src.engines.opportunity_scanner import _breakout_score

    score = _breakout_score(
        np.array([90.0, 100.0]),
        np.array([0.7, 0.9]),
        np.array([58.0, 64.0]),
        np.array([1.1, 1.8]),
    )
    assert score >= 0.8


def test_compression_score_rewards_tight_bands():
    from src.engines.opportunity_scanner import _compression_score

    widths = np.array([0.60] * 59 + [0.10])
    assert _compression_score(widths) > 0.8


def test_stage_score_stage_two_alignment():
    from src.engines.opportunity_scanner import _stage_score

    close = np.array([90.0, 105.0])
    sma50 = np.array([85.0, 100.0])
    sma200 = np.array([80.0, 95.0])
    assert _stage_score(close, sma50, sma200) == 0.90


def test_candidate_to_dict_includes_two_atr_levels():
    from src.engines.opportunity_scanner import OpportunityCandidate

    candidate = OpportunityCandidate(
        rank=1,
        ticker="AAA",
        engine="bull",
        score=77.7,
        leadership_score=80.0,
        actionability_score=75.0,
        is_actionable=True,
        close=100.0,
        stop_loss=96.0,
        activation=104.0,
        atr14=2.0,
    )
    data = candidate.to_dict()
    assert data["stop_loss"] == 96.0
    assert data["activation"] == 104.0
    assert data["tags"] == ["⚡"]


def test_run_opportunity_scanner_returns_ranked_bull_candidates(monkeypatch):
    import src.scanners.us_universe as universe_mod
    import src.services.indicators as indicators_mod
    from src.engines.opportunity_scanner import ScannerResult, run_opportunity_scanner

    monkeypatch.setattr(universe_mod, "US_UNIVERSE", ["AAA", "BBB"])
    monkeypatch.setattr(indicators_mod, "compute_indicators", _mock_indicators)

    dates = pd.date_range("2025-01-01", periods=252, freq="D")
    aaa_close = _price_series(50.0, 0.25)
    bbb_close = _price_series(30.0, 0.05)
    aaa_vol = np.full(252, 500_000.0)
    bbb_vol = np.full(252, 400_000.0)
    spy_close = _price_series(100.0, 0.05)

    def fake_download(tickers, *args, **kwargs):
        if tickers == "SPY":
            return pd.DataFrame({"Close": spy_close}, index=dates)
        columns = pd.MultiIndex.from_tuples(
            [
                ("AAA", "Close"),
                ("AAA", "Volume"),
                ("BBB", "Close"),
                ("BBB", "Volume"),
            ]
        )
        return pd.DataFrame(
            np.column_stack([aaa_close, aaa_vol, bbb_close, bbb_vol]),
            index=dates,
            columns=columns,
        )

    monkeypatch.setitem(
        sys.modules, "yfinance", types.SimpleNamespace(download=fake_download)
    )

    import asyncio

    result = asyncio.run(run_opportunity_scanner(regime="BULL", top_n=10))
    assert isinstance(result, ScannerResult)
    assert result.engine == "bull"
    assert result.candidates_ranked >= 1
    assert result.candidates[0].ticker == "AAA"
    assert result.candidates[0].stop_loss == round(result.candidates[0].close - 4.0, 2)


def test_scanner_result_to_dict_has_filter_funnel_keys():
    result = _make_router_result()
    data = result.to_dict()
    funnel = data["filter_funnel"]
    assert set(funnel) == {
        "initial_universe",
        "passed_initial_filters",
        "passed_rs_filter",
        "passed_pattern_filter",
        "final_candidates",
        "raw_candidates",
    }


def test_rest_opportunity_scanner_get_200(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import src.api.routers.opportunity_scanner as router_mod

    monkeypatch.setattr(router_mod, "_CACHE_FILE", tmp_path / "oppty_cache.json")

    async def fake_run(**kwargs):
        return _make_router_result()

    monkeypatch.setattr(router_mod, "run_opportunity_scanner", fake_run)

    app = FastAPI()
    app.include_router(router_mod.router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/api/v7/opportunity-scanner?regime=BULL&top_n=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["engine"] == "bull"
    assert len(body["candidates"]) == 1


def test_rest_status_tracks_distinct_filter_cache_keys(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import src.api.routers.opportunity_scanner as router_mod

    monkeypatch.setattr(router_mod, "_CACHE_FILE", tmp_path / "oppty_cache.json")
    router_mod._cache.clear()

    async def fake_run(**kwargs):
        return _make_router_result()

    monkeypatch.setattr(router_mod, "run_opportunity_scanner", fake_run)

    app = FastAPI()
    app.include_router(router_mod.router)
    client = TestClient(app, raise_server_exceptions=True)

    first = client.get(
        "/api/v7/opportunity-scanner?regime=BULL&top_n=50&min_price=5&min_vol=200000"
    )
    second = client.get(
        "/api/v7/opportunity-scanner?regime=BULL&top_n=50&min_price=10&min_vol=200000"
    )
    status = client.get("/api/v7/opportunity-scanner/status")

    assert first.status_code == 200
    assert second.status_code == 200
    assert status.status_code == 200
    keys = {entry["key"] for entry in status.json()["cached_runs"]}
    assert len(keys) == 2
    assert any("_5.00_200000" in key for key in keys)
    assert any("_10.00_200000" in key for key in keys)


def test_rest_invalidate_clears_cache_and_file(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import src.api.routers.opportunity_scanner as router_mod

    monkeypatch.setenv("API_KEY", "test-key-114")
    cache_file = tmp_path / "oppty_cache.json"
    monkeypatch.setattr(router_mod, "_CACHE_FILE", cache_file)
    router_mod._cache.clear()
    router_mod._cache["BULL_50_5.00_200000"] = {
        "data": {"engine": "bull", "generated_at": "2026-05-07T00:00:00+00:00"},
        "ts": 1.0,
    }
    cache_file.write_text('{"key":"BULL_50_5.00_200000","data":{},"ts":1.0}')

    app = FastAPI()
    app.include_router(router_mod.router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post(
        "/api/v7/opportunity-scanner/invalidate",
        headers={"X-API-Key": "test-key-114"},
    )
    assert resp.status_code == 200
    assert resp.json()["cleared"] == 1
    assert router_mod._cache == {}
    assert not cache_file.exists()
