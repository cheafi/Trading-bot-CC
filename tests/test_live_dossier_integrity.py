"""Live dossier technicals: real values or N/A — never placeholder defaults."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import live_dossier as ld


def _bars(n: int, *, gap_up_at: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + 1.0
    low = close - 1.0
    if gap_up_at is not None:
        close[gap_up_at:] += 20
        high[gap_up_at:] += 20
        low[gap_up_at:] += 20
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": 1_000_000},
        index=idx,
    )


class _FakeMDS:
    def __init__(self, hist):
        self._hist = hist

    async def get_quote(self, ticker):
        h = self._hist
        price = float(h["Close"].iloc[-1]) if isinstance(h, pd.DataFrame) else 100.0
        return {"price": price, "change_pct": 0.0, "change": 0.0, "volume": 1}

    async def get_history(self, ticker, period="1y", interval="1d"):
        if isinstance(self._hist, Exception):
            raise self._hist
        return self._hist


def _client(monkeypatch, hist) -> TestClient:
    async def _regime(_request):
        return SimpleNamespace(regime="UNKNOWN", should_trade=False)

    monkeypatch.setattr(ld, "fetch_regime_state", _regime)
    app = FastAPI()
    app.include_router(ld.router)
    app.state.market_data = _FakeMDS(hist)
    return TestClient(app)


def test_atr_uses_true_range_including_gaps(monkeypatch):
    hist = _bars(60, gap_up_at=55)
    d = _client(monkeypatch, hist).get("/api/live/dossier/AAPL").json()
    prev = hist["Close"].shift(1)
    tr = pd.concat(
        [hist["High"] - hist["Low"], (hist["High"] - prev).abs(), (hist["Low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    expected = round(float(tr.rolling(14).mean().iloc[-1]), 2)
    assert d["technicals"]["atr"] == expected
    assert expected > 2.0  # high-low alone is always 2.0 here


@pytest.mark.parametrize("hist", [None, _bars(10), RuntimeError("feed down")])
def test_missing_history_yields_na_and_no_plan(monkeypatch, hist):
    d = _client(monkeypatch, hist).get("/api/live/dossier/AAPL").json()
    t = d["technicals"]
    for k in ("rsi", "atr", "volume_ratio", "support", "resistance", "high_52w", "macd_signal"):
        assert t[k] is None, k
    assert t["error"] in ("insufficient_history", "computation_failed")
    assert d["trade_plan"]["status"] == "UNAVAILABLE"
    assert "stop" not in d["trade_plan"]
    assert d["factor_summary"]["positive"] == 0
    assert d["factor_summary"]["negative"] == 0
    assert all(f["signal"] == "unavailable" for f in d["factors"])
    assert not any(w.startswith("✅") for w in d["why_stop"])


def test_full_history_produces_projection_plan(monkeypatch):
    d = _client(monkeypatch, _bars(250)).get("/api/live/dossier/AAPL").json()
    t = d["technicals"]
    assert 0 <= t["rsi"] <= 100
    assert t["error"] is None
    tp = d["trade_plan"]
    assert tp["status"] == "PROJECTION"
    assert tp["stop"] < d["price"] < tp["target_1r"]
    risk = d["price"] - tp["stop"]
    assert tp["rr_ratio"] == pytest.approx((tp["target_1r"] - d["price"]) / risk, abs=0.02)
