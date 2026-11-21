"""v7 surfaces: endpoints that used to raise NameError, and what they now return."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import v7_surfaces as v7


def _hist(n: int = 80) -> pd.DataFrame:
    close = 100 + np.cumsum(np.random.default_rng(3).normal(0, 1, n))
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1e6},
        index=idx,
    )


class _MDS:
    def __init__(self, hist):
        self.hist = hist

    async def get_quote(self, ticker):
        return {"price": 123.0, "change_pct": 3.1, "change": 3.7, "volume": 10}

    async def get_history(self, ticker, period="3mo", interval="1d"):
        return self.hist


@pytest.fixture
def client_factory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(v7, "_engine", lambda: None)

    async def _regime(_request):
        return {"regime": "UNKNOWN", "should_trade": False}

    monkeypatch.setattr(v7, "fetch_regime_state", _regime)

    def make(hist):
        app = FastAPI()
        app.include_router(v7.router)
        app.state.market_data = _MDS(hist)
        app.state.regime_cache = None
        return TestClient(app)

    return make


def test_why_moved_runs_without_name_error(client_factory):
    r = client_factory(_hist()).get("/api/v7/why-moved/AAPL")
    assert r.status_code == 200


def test_why_moved_without_history_does_not_invent_rsi(client_factory):
    r = client_factory(None).get("/api/v7/why-moved/AAPL")
    assert r.status_code == 200
    assert "RSI" not in r.text


@pytest.mark.parametrize("bad", ["../../etc/passwd", "2026-13-40", "x"])
def test_portfolio_brief_rejects_non_iso_date(client_factory, bad):
    r = client_factory(_hist()).get("/api/v7/portfolio-brief", params={"date": bad})
    assert r.status_code == 400


def test_regime_screener_has_no_fabricated_fallback(client_factory):
    r = client_factory(_hist()).get("/api/v7/regime-screener")
    assert r.status_code == 200
    body = r.json()
    assert body["candidates"] == []
    assert body["trust"]["source"] == "none"
    assert any("No engine recommendations" in w for w in body["warnings"])


def test_options_screen_refuses_without_rsi(client_factory):
    r = client_factory(None).get("/api/v7/options-screen", params={"ticker": "AAPL"})
    assert r.status_code == 503


def test_no_undefined_names_in_src():
    """F821 = a code path that raises NameError the first time it runs."""
    import subprocess
    import sys
    from pathlib import Path

    pytest.importorskip("ruff")
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(  # fixed argv, no shell, no external input
        [sys.executable, "-m", "ruff", "check", "src", "--select", "F821",
         "--output-format=concise", "--exclude", "* [0-9].py"],
        cwd=root, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
