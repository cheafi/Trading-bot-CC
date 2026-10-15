"""Signal Board — scoring, triggers, filters, holding alerts, track record, API."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services import signal_board as sb

N = 260


def _bars(
    close: np.ndarray, spread_pct: float = 0.01, volume: np.ndarray | None = None
):
    high = close * (1 + spread_pct)
    low = close * (1 - spread_pct)
    vol = volume if volume is not None else np.full(len(close), 2_000_000.0)
    return high, low, close, vol


def _wiggle(n: int, amp: float) -> np.ndarray:
    return np.where(np.arange(n) % 2 == 0, amp, -amp)


def _uptrend_breakout():
    close = np.linspace(50, 100, N) + _wiggle(N, 0.8)
    close[-21:-1] = np.linspace(97, 99, 20) + _wiggle(20, 0.8)  # base below prior high
    close[-1] = 104.0
    vol = np.full(N, 2_000_000.0)
    vol[-1] = 5_000_000.0
    return _bars(close, volume=vol)


def _downtrend_breakdown():
    close = np.linspace(150, 60, N) + _wiggle(N, 0.3)
    close[-21:-1] = np.linspace(63, 61, 20) + _wiggle(20, 0.3)
    close[-1] = 59.0
    vol = np.full(N, 2_000_000.0)
    vol[-1] = 5_000_000.0
    return _bars(close, volume=vol)


def _features(ticker: str, bars, bench=None) -> sb.Features:
    f = sb.compute_features(ticker, *bars, bench_close=bench)
    assert f is not None
    return f


def test_short_history_is_rejected():
    assert sb.compute_features("X", *_bars(np.linspace(10, 20, 50))) is None


def test_uptrend_breakout_scores_as_buy():
    f = _features("UP", _uptrend_breakout())
    score, setup, why = sb.score_long(f, rs_pct=90)
    assert setup == "Breakout"
    assert score >= sb.STRONG_THRESHOLD
    assert any("breakout" in w.lower() for w in why)
    plan = sb.trade_plan(f, "BUY")
    assert plan["stop"] < plan["entry"] < plan["target1"] < plan["target2"]
    assert (
        sb.bucket_for(score, setup, "BUY", "RISK_ON", 90, plan["risk_pct"])
        == "strong_buy"
    )


def test_downtrend_breakdown_scores_as_sell():
    f = _features("DN", _downtrend_breakdown())
    score, setup, _ = sb.score_short(f, rs_pct=5)
    assert setup == "Breakdown"
    plan = sb.trade_plan(f, "SELL")
    assert plan["target2"] < plan["target1"] < plan["entry"] < plan["stop"]
    assert (
        sb.bucket_for(score, setup, "SELL", "RISK_OFF", 5, plan["risk_pct"])
        == "strong_sell"
    )


def test_no_trigger_means_no_bucket():
    assert sb.bucket_for(99.0, "", "BUY", "RISK_ON", 99, 3.0) is None


def test_regime_headwind_raises_threshold():
    score = sb.SIGNAL_THRESHOLD + 5
    assert sb.bucket_for(score, "Breakdown", "SELL", "NEUTRAL", 10, 3.0) == "sell"
    assert sb.bucket_for(score, "Breakdown", "SELL", "RISK_ON", 10, 3.0) is None


def test_strong_requires_relative_strength():
    assert sb.bucket_for(95, "Breakout", "BUY", "RISK_ON", 50, 3.0) == "buy"
    assert sb.bucket_for(95, "Breakout", "BUY", "RISK_ON", 80, 3.0) == "strong_buy"


def test_wide_stop_is_dropped():
    assert (
        sb.bucket_for(95, "Breakout", "BUY", "RISK_ON", 90, sb.MAX_RISK_PCT + 0.1)
        is None
    )


def test_pinned_price_is_not_tradeable():
    close = np.full(N, 72.5) + np.sin(np.arange(N)) * 0.02
    f = _features("PIN", _bars(close, spread_pct=0.001))
    assert not sb.is_liquid(f)


def test_overbought_extension_is_penalised():
    close = np.linspace(50, 100, N)
    close[-10:] = np.linspace(100, 140, 10)
    f = _features("HOT", _bars(close))
    _, _, why = sb.score_long(f, rs_pct=99)
    assert any("Overbought" in w or "Extended" in w for w in why)


def test_percentile_ranks_handle_ties():
    ranks = sb.percentile_ranks({"a": 1.0, "b": 2.0, "c": 2.0, "d": 3.0})
    assert ranks["a"] == 0.0 and ranks["d"] == 100.0
    assert ranks["b"] == ranks["c"]


def test_regime_classification():
    up = _features("SPY", _uptrend_breakout())
    dn = _features("SPY", _downtrend_breakdown())
    assert sb.classify_regime(up)["label"] == "RISK_ON"
    assert sb.classify_regime(dn)["label"] == "RISK_OFF"
    assert sb.classify_regime(None)["label"] == "UNKNOWN"


def test_holding_exit_on_breakdown_and_hold_in_uptrend():
    dn = _features("DN", _downtrend_breakdown())
    ss, setup, _ = sb.score_short(dn, 5)
    alert = sb.holding_alert(dn, ss, setup, avg_cost=100.0)
    assert alert["action"] == "EXIT"
    assert alert["pnl_pct"] < 0

    close = np.linspace(50, 100, N) + np.sin(np.arange(N) / 3) * 0.5
    up = _features("UP", _bars(close))
    ss, setup, _ = sb.score_short(up, 90)
    assert sb.holding_alert(up, ss, setup, avg_cost=None)["action"] in ("HOLD", "TRIM")


def test_evaluate_signal_stop_wins_ties():
    assert (
        sb.evaluate_signal("BUY", 100, 95, 110, [111], [94], 100)["status"] == "stopped"
    )
    assert sb.evaluate_signal("BUY", 100, 95, 110, [104, 111], [99, 101], 108) == {
        "status": "target",
        "r": 2.0,
    }
    assert (
        sb.evaluate_signal("SELL", 100, 105, 90, [101], [89], 95)["status"] == "target"
    )
    open_ = sb.evaluate_signal("SELL", 100, 105, 90, [102], [97], 97.5)
    assert open_ == {"status": "open", "r": 0.5}


def test_track_record_summary():
    summary = sb.summarize_track_record(
        [
            {"status": "target", "r": 2.0, "bucket": "buy"},
            {"status": "stopped", "r": -1.0, "bucket": "buy"},
            {"status": "open", "r": 0.3, "bucket": "sell"},
        ]
    )
    assert summary["closed"] == 2 and summary["open"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["by_bucket"]["buy"]["avg_r"] == 0.5


def test_build_board_buckets_and_sector_cap():
    bench = _features("SPY", _uptrend_breakout())
    feats = {}
    sectors = {}
    for i in range(6):
        feats[f"U{i}"] = _features(f"U{i}", _uptrend_breakout())
        feats[f"U{i}"].rs_raw = 100 + i
        sectors[f"U{i}"] = "Tech"
    for i in range(2):
        feats[f"D{i}"] = _features(f"D{i}", _downtrend_breakdown())
        sectors[f"D{i}"] = "Energy"
    for i in range(4):
        close = np.linspace(60, 61, N) + np.sin(np.arange(N) / 4)
        feats[f"F{i}"] = _features(f"F{i}", _bars(close))
        sectors[f"F{i}"] = "Utilities"
    board = sb.build_board(
        sb.BoardInputs(feats, sectors, bench, [{"ticker": "D0", "avg_cost": 70}])
    )

    buys = board["buckets"]["strong_buy"] + board["buckets"]["buy"]
    assert buys, "uptrend breakouts should produce BUY signals"
    assert all(r["side"] == "BUY" for r in buys)
    assert (
        len([r for r in board["buckets"]["strong_buy"] if r["sector"] == "Tech"])
        <= sb.SECTOR_CAP_PER_BUCKET
    )
    for row in buys:
        assert row["authority"] == sb.AUTHORITY["label"]
        assert row["invalidation"].startswith("Close below")
    assert board["holdings"][0]["ticker"] == "D0"
    assert board["holdings"][0]["action"] == "EXIT"
    assert board["regime"]["label"] == "RISK_ON"


def test_market_session_open_and_closed():
    open_ = sb.market_session(
        datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
    )  # 11:00 ET Wed
    assert open_["is_open"] and 0.1 <= open_["session_fraction"] < 1.0
    closed = sb.market_session(
        datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
    )  # Saturday
    assert not closed["is_open"]


@pytest.fixture
def client(monkeypatch):
    from src.api.routers import signal_board as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app), router_mod, monkeypatch


def test_api_warming_when_empty(client):
    c, router_mod, mp = client
    mp.setattr(router_mod.sb, "get_latest", dict)
    mp.setattr(router_mod, "_kick_refresh", lambda source: True)
    body = c.get("/api/v7/signal-board").json()
    assert body["status"] == "warming"
    assert body["authority"]["label"] == "Paper signal"


def test_api_returns_latest_board(client):
    c, router_mod, mp = client
    mp.setattr(
        router_mod.sb,
        "get_latest",
        lambda: {"status": "ok", "headline": {"top_buy": "UP"}},
    )
    body = c.get("/api/v7/signal-board").json()
    assert body["status"] == "ok"
    assert body["headline"]["top_buy"] == "UP"
    assert "refreshing" in body


def test_load_universe_includes_crypto() -> None:
    sectors = sb.load_universe()
    assert "BTC-USD" in sectors
    assert sectors["BTC-USD"] == "Crypto"
    assert "IBIT" in sectors


def test_crypto_liquid_thresholds() -> None:
    close = np.full(N, 100.0)
    vol = np.full(N, 150_000.0)  # ~$15M 20d $ vol — ok for crypto ($5M+), not equities ($20M+)
    h, lo, c, _vol = _bars(close, volume=vol)
    f = sb.compute_features("BTC-USD", h, lo, c, _vol)
    assert f is not None
    assert sb.is_liquid(f, "Crypto")
    f_eq = sb.compute_features("AAPL", h, lo, c, _vol)
    assert f_eq is not None
    assert not sb.is_liquid(f_eq)


def test_api_refresh_requires_key(client, monkeypatch):
    c, router_mod, mp = client
    from src.core import config

    monkeypatch.setattr(config.settings, "api_secret_key", "test-secret", raising=False)
    mp.setattr(router_mod, "_kick_refresh", lambda source: True)
    assert c.post("/api/v7/signal-board/refresh").status_code == 401
    ok = c.post("/api/v7/signal-board/refresh", headers={"X-API-Key": "test-secret"})
    assert ok.status_code == 200 and ok.json()["status"] == "started"
