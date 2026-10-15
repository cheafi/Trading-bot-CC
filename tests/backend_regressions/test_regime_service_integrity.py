"""⚠ SYNTHETIC fixtures: mocked engine/provider; no network or trading."""

import asyncio
from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest
import yfinance as yf

from src.engines.macro_regime_engine import MacroRegimeEngine, RegimeResult
from src.services.regime_service import RegimeService


@pytest.fixture(autouse=True)
def isolated_regime(monkeypatch):
    monkeypatch.setattr(RegimeService, "_cache", {})
    monkeypatch.setattr(RegimeService, "_cache_time", 0)
    monkeypatch.setattr(RegimeService, "_refresh_lock", asyncio.Lock())
    monkeypatch.setattr(RegimeService, "_is_synthetic", False, raising=False)
    monkeypatch.setattr(
        RegimeService, "_missing_benchmarks", [], raising=False
    )
    monkeypatch.setattr(
        "src.services.regime_service.time.time", lambda: 100_000.0
    )
    monkeypatch.setattr(yf, "download", Mock(return_value=pd.DataFrame()))
    compute = Mock(return_value=RegimeResult(
        trend="UPTREND", risk_score=25.0, vix_level=13.0,
        confidence=0.85, signals=["mocked engine result"],
    ))
    monkeypatch.setattr(MacroRegimeEngine, "compute", compute)
    return compute


def install_provider(monkeypatch, missing=()):
    def download(ticker, **kwargs):
        if ticker in missing:
            return pd.DataFrame()
        # Exercise the repaired MultiIndex normalization, not a replacement.
        return pd.DataFrame(
            {("Close", ticker): [100.0 + i for i in range(60)]},
            index=pd.date_range("2026-01-01", periods=60),
        )

    provider = Mock(side_effect=download)
    monkeypatch.setattr(yf, "download", provider)
    return provider


def test_complete_real_provider_can_allow_trading(
    monkeypatch, isolated_regime
):
    provider = install_provider(monkeypatch)
    regime = RegimeService.get()
    assert regime["should_trade"] is True
    assert regime["synthetic"] is False
    assert regime["stale"] is False
    assert regime["data_status"] == "live"
    assert regime["missing_benchmarks"] == []
    assert regime["trade_block_reason"] is None
    assert regime["risk_score"] == 25.0
    assert provider.call_count == 5
    assert isolated_regime.call_args.kwargs["spy_closes"] == [
        100.0 + i for i in range(60)
    ]
    assert RegimeService.get() is regime


@pytest.mark.parametrize("missing", [
    ("^VIX",), ("QQQ",), ("IWM",), ("HYG",),
    ("QQQ", "^VIX", "IWM", "HYG"),
])
def test_partial_real_provider_never_allows_trading(monkeypatch, missing):
    install_provider(monkeypatch, missing)
    regime = RegimeService.get()
    assert regime["should_trade"] is False
    assert regime["synthetic"] is False
    assert regime["data_status"] == "incomplete"
    assert regime["missing_benchmarks"] == list(missing)
    for ticker in missing:
        assert ticker in regime["trade_block_reason"]
    assert regime["trade_block_reason"] in regime["signals"]
    assert regime["risk_score"] == 25.0


@pytest.mark.parametrize("missing", [
    ("SPY",), RegimeService.REQUIRED_BENCHMARKS
])
def test_synthetic_fallback_never_allows_trading(
    monkeypatch, isolated_regime, missing
):
    install_provider(monkeypatch, missing)
    regime = RegimeService.get()
    assert regime["should_trade"] is False
    assert regime["synthetic"] is True
    assert regime["data_status"] == "synthetic"
    assert regime["missing_benchmarks"] == list(missing)
    assert "research-only" in regime["trade_block_reason"]
    for ticker in missing:
        assert ticker in regime["trade_block_reason"]
    assert isolated_regime.call_args.kwargs["spy_closes"] == [100.0] * 60


@pytest.mark.parametrize("risk_score, expected", [
    (74.9, True), (75.0, False), (90.0, False)
])
def test_existing_risk_score_gate_is_preserved(
    monkeypatch, isolated_regime, risk_score, expected
):
    install_provider(monkeypatch)
    isolated_regime.return_value.risk_score = risk_score
    assert RegimeService.get()["should_trade"] is expected


@pytest.mark.parametrize("async_get", [False, True])
def test_failed_refresh_returns_stale_copy_without_mutation(
    monkeypatch, async_get
):
    install_provider(monkeypatch)
    cached = RegimeService.get()
    original = deepcopy(cached)
    expired_at = 100_000.0 - RegimeService.CACHE_TTL
    monkeypatch.setattr(RegimeService, "_cache_time", expired_at)
    refresh = Mock(side_effect=RuntimeError("isolated refresh failure"))
    monkeypatch.setattr(RegimeService, "_fetch_and_compute", refresh)

    result = (
        asyncio.run(RegimeService.aget()) if async_get else RegimeService.get()
    )

    assert result is not cached
    assert result["should_trade"] is False
    assert result["stale"] is True
    assert result["data_status"] == "stale"
    assert result["source"] == "regime_service_cache_stale"
    assert result["confidence"] == 0.0
    assert "refresh failed" in result["trade_block_reason"]
    assert result["risk_score"] == cached["risk_score"]
    assert result["vix"] == cached["vix"]
    assert result["synthetic"] is False  # Historical real data, not synthetic.
    result["signals"].append("caller change")
    result["missing_benchmarks"].append("caller change")
    assert RegimeService._cache is cached
    assert cached == original
    assert cached["should_trade"] is True
    assert RegimeService._cache_time == expired_at
    refresh.assert_called_once_with()


@pytest.mark.parametrize("async_get", [False, True])
def test_failed_refresh_without_cache_is_disclosed_default(
    monkeypatch, async_get
):
    monkeypatch.setattr(RegimeService, "_fetch_and_compute", Mock(
        side_effect=RuntimeError("isolated initial failure")
    ))
    result = (
        asyncio.run(RegimeService.aget()) if async_get else RegimeService.get()
    )
    assert result["should_trade"] is False
    assert result["synthetic"] is True
    assert result["data_status"] == "unavailable"
    assert result["missing_benchmarks"] == list(
        RegimeService.REQUIRED_BENCHMARKS
    )
    assert "synthetic defaults" in result["trade_block_reason"]
    assert RegimeService._cache == {}
    assert RegimeService._cache_time == 0


def test_new_real_refresh_clears_previous_synthetic_provenance(monkeypatch):
    fallback = RegimeService.get()
    assert fallback["synthetic"] is True
    install_provider(monkeypatch)
    RegimeService.invalidate()
    refreshed = RegimeService.get()
    assert refreshed["synthetic"] is False
    assert refreshed["should_trade"] is True
    assert refreshed["missing_benchmarks"] == []
    assert refreshed["data_status"] == "live"
