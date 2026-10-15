"""⚠ SYNTHETIC fixtures: isolated provider shapes, no market/network access."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
import yfinance as yf

from src.services.market_data import extract_close_series, _validate_frame
from src.services.regime_service import RegimeService


def close_frame(ticker="SPY", layout="flat", rows=30):
    index = pd.date_range("2026-01-01", periods=rows)
    column = {
        "flat": "Close",
        "lower": "close",
        "price_first": ("Close", ticker),
        "ticker_first": (ticker, "Close"),
    }[layout]
    frame = pd.DataFrame(
        {column: [100.0 + i for i in range(rows)]}, index=index
    )
    frame.attrs["synthetic_fixture"] = True
    return frame


@pytest.mark.parametrize(
    "layout", ["flat", "lower", "price_first", "ticker_first"]
)
def test_extract_close_preserves_values_dates_and_input(layout):
    frame = close_frame(layout=layout)
    original = frame.copy(deep=True)
    result = extract_close_series(frame, "SPY")
    assert isinstance(result, pd.Series)
    assert result.tolist() == [100.0 + i for i in range(30)]
    assert result.index.equals(frame.index)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("layout", ["price_first", "ticker_first"])
def test_extract_close_selects_requested_ticker_not_first_column(layout):
    frame = pd.concat(
        [close_frame("QQQ", layout) * 2, close_frame("SPY", layout)], axis=1
    )
    assert extract_close_series(frame, "SPY").iloc[-1] == 129.0
    assert extract_close_series(frame, "IWM") is None


@pytest.mark.parametrize(
    "frame",
    [
        None, [], pd.DataFrame(),
        pd.DataFrame({"Open": [100]}),
        pd.DataFrame({"Close": [float("nan")]}),
        pd.DataFrame({"Close": [float("inf"), "invalid"]}),
        pd.DataFrame([[100, 101]], columns=["Close", "Close"]),
    ],
)
def test_extract_unavailable_or_ambiguous_is_none(frame):
    assert extract_close_series(frame, "SPY") is None


def test_extract_drops_invalid_without_reindexing():
    frame = close_frame(rows=4)
    frame["Close"] = ["100", float("nan"), float("inf"), "103"]
    result = extract_close_series(frame, "SPY")
    assert result.tolist() == [100.0, 103.0]
    assert result.index.equals(frame.index[[0, 3]])


def test_existing_frame_validation_gates_are_unchanged():
    assert _validate_frame(close_frame(), "SPY", "1d") is not None
    assert _validate_frame(pd.DataFrame(), "SPY", "1d") is None
    assert _validate_frame(close_frame(rows=2), "SPY", "1d") is None
    assert _validate_frame(
        pd.DataFrame({"Close": [float("nan")] * 30}), "SPY", "1d"
    ) is None


@pytest.mark.parametrize("layout", ["flat", "price_first", "ticker_first"])
def test_regime_download_accepts_single_ticker_shapes(monkeypatch, layout):
    monkeypatch.setattr(RegimeService, "_is_synthetic", True, raising=False)
    download = Mock(
        side_effect=lambda ticker, **kw: close_frame(ticker, layout)
    )
    monkeypatch.setattr(yf, "download", download)
    closes = RegimeService._fetch_closes()
    assert set(closes) == {"SPY", "QQQ", "^VIX", "IWM", "HYG"}
    assert closes["SPY"] == [100.0 + i for i in range(30)]
    assert RegimeService._is_synthetic is False
    assert download.call_count == 5


@pytest.mark.parametrize("failure", ["empty", "error", "wrong_ticker"])
def test_regime_failure_keeps_synthetic_provenance(monkeypatch, failure):
    monkeypatch.setattr(RegimeService, "_is_synthetic", False, raising=False)
    download = Mock()
    if failure == "error":
        download.side_effect = RuntimeError("isolated provider failure")
    else:
        download.return_value = (pd.DataFrame() if failure == "empty"
                                 else close_frame("OTHER", "price_first"))
    monkeypatch.setattr(yf, "download", download)
    assert RegimeService._fetch_closes() == RegimeService._synthetic_closes()
    assert RegimeService._is_synthetic is True
    # Provenance verification, not permission to promote synthetic data.


@pytest.mark.parametrize("layout", ["flat", "price_first", "ticker_first"])
def test_rs_single_download_is_series_and_cached(monkeypatch, layout):
    from src.services import rs_data_service as rs

    monkeypatch.setattr(rs, "_CLOSES_CACHE", {})
    download = Mock(return_value=close_frame(layout=layout))
    monkeypatch.setattr(yf, "download", download)
    result = rs.fetch_single("SPY")
    assert isinstance(result, pd.Series)
    assert result.iloc[-1] == 129.0
    pd.testing.assert_series_equal(rs.fetch_single("SPY"), result)
    assert download.call_count == 1


@pytest.mark.parametrize("layout", ["price_first", "ticker_first"])
def test_rs_batch_tickers_and_minimum_rows(monkeypatch, layout):
    from src.services import rs_data_service as rs

    monkeypatch.setattr(rs, "_CLOSES_CACHE", {})
    frame = pd.concat([close_frame("SPY", layout),
                       close_frame("QQQ", layout) * 2,
                       close_frame("IWM", layout, rows=10)], axis=1)
    monkeypatch.setattr(yf, "download", Mock(return_value=frame))
    result = rs.fetch_closes_batch(["SPY", "QQQ", "IWM"])
    assert set(result) == {"SPY", "QQQ"}
    assert result["SPY"].iloc[-1] == 129.0
    assert result["QQQ"].iloc[-1] == 258.0


@pytest.mark.parametrize(
    "failure", ["empty", "error", "wrong_ticker", "flat_batch"]
)
def test_rs_failure_does_not_cache_or_invent_prices(monkeypatch, failure):
    from src.services import rs_data_service as rs

    monkeypatch.setattr(rs, "_CLOSES_CACHE", {})
    download = Mock()
    if failure == "error":
        download.side_effect = RuntimeError("isolated provider failure")
    else:
        download.return_value = {
            "empty": pd.DataFrame(),
            "wrong_ticker": close_frame("OTHER", "ticker_first"),
            "flat_batch": close_frame(),
        }[failure]
    monkeypatch.setattr(yf, "download", download)
    tickers = ["SPY", "QQQ"] if failure == "flat_batch" else ["SPY"]
    assert rs.fetch_closes_batch(tickers) == {}
    assert rs._CLOSES_CACHE == {}


@pytest.mark.parametrize("stale", [False, True])
def test_daily_rs_request_and_nonlive_mode(monkeypatch, stale):
    from src.api.routers import daily_decision as daily, playbook

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    monkeypatch.setattr(
        daily, "_rs_cache", {"ts": 0, "rows": [], "refreshing": False}
    )
    ranking = AsyncMock(return_value={"stale": stale, "rankings": [
        {"ticker": "TEST", "price": 100, "rs_percentile": 95}
    ]})
    monkeypatch.setattr(playbook, "rs_ranking", ranking)
    asyncio.run(daily._refresh_rs_cache(request, 3))
    ranking.assert_awaited_once_with(
        request, sector=None, cap=None, limit=8, live=False
    )
    row = daily._rs_cache["rows"][0]
    assert row["action"] == "WATCH" and row["buy_now"] is False
    assert row["risk_reward"] == 0 and row["stop_price"] is None
    assert row["stale"] is stale
    expected_source = "stale-brief-watchlist" if stale else "rs-watchlist"
    assert row["source"] == row["confidence_source"] == expected_source
    assert daily._rs_cache["refreshing"] is False


@pytest.mark.parametrize("failure", ["empty", "error"])
def test_daily_rs_failure_preserves_cache(monkeypatch, failure):
    from src.api.routers import daily_decision as daily, playbook

    old = {"ticker": "OLD", "action": "WATCH", "buy_now": False}
    monkeypatch.setattr(
        daily, "_rs_cache", {"ts": 123, "rows": [old], "refreshing": False}
    )
    ranking = AsyncMock(return_value={"rankings": []})
    if failure == "error":
        ranking.side_effect = RuntimeError("isolated RS failure")
    monkeypatch.setattr(playbook, "rs_ranking", ranking)
    asyncio.run(daily._refresh_rs_cache(SimpleNamespace(), 8))
    assert daily._rs_cache == {"ts": 123, "rows": [old], "refreshing": False}


@pytest.mark.parametrize("engine_present", [False, True])
def test_daily_empty_engine_is_unavailable(monkeypatch, engine_present):
    from src.api.routers import daily_decision as daily

    engine = (
        SimpleNamespace(_cached_recommendations=[], dry_run=True)
        if engine_present else None
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        engine=engine,
        regime_cache={"label": "SIDEWAYS", "should_trade": False}
    )))
    watchlist = AsyncMock(return_value=[])
    monkeypatch.setattr(daily, "_rs_watchlist", watchlist)
    monkeypatch.setattr(
        daily, "_rs_cache", {"ts": 0, "rows": [], "refreshing": False}
    )
    result = asyncio.run(daily.daily_decision_state(request, limit=8))
    watchlist.assert_awaited_once_with(request, 8)
    assert result["sources"]["engine_cache"] == {
        "count": 0, "status": "unavailable"
    }
    assert result["confidence"]["source"] == "unavailable"
    assert result["actionable"] == result["watchlist"] == []
    assert result["buy_now"] is None and result["decision"] == "WAIT"
    assert result["regime_gate"]["ok"] is False
    assert "unavailable" in result["summary"].lower()
    assert "matched strict" not in " ".join(result["no_trade_reasons"])


def test_daily_refresh_uses_real_rs_handler_without_live_compute(monkeypatch):
    from src.api.routers import daily_decision as daily, playbook
    from src.services import rs_decision_surface

    monkeypatch.setattr(
        daily, "_rs_cache", {"ts": 0, "rows": [], "refreshing": False}
    )
    monkeypatch.setattr(playbook, "_get_rs_ranking_cached", lambda key: None)
    fallback = Mock(return_value={"stale": True, "rankings": [
        {"ticker": "TEST", "price": 100, "rs_percentile": 95}
    ]})
    refresh = AsyncMock()
    live = AsyncMock(side_effect=AssertionError("must not run live compute"))
    monkeypatch.setattr(playbook, "_brief_rs_ranking_fallback", fallback)
    monkeypatch.setattr(playbook, "_refresh_rs_ranking_cache", refresh)
    monkeypatch.setattr(rs_decision_surface, "build_rs_decision_surface", live)

    async def run():
        await daily._refresh_rs_cache(SimpleNamespace(), 8)
        await asyncio.sleep(0)

    asyncio.run(run())
    fallback.assert_called_once_with(8, None, None)
    refresh.assert_awaited_once()
    live.assert_not_awaited()
    assert daily._rs_cache["rows"][0]["stale"] is True


@pytest.mark.parametrize("stale", [False, True])
def test_daily_watch_metadata_preserves_provenance(monkeypatch, stale):
    from src.api.routers import daily_decision as daily

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        engine=None,
        regime_cache={"label": "BULL", "should_trade": True, "vix": 18}
    )))
    source = "stale-brief-watchlist" if stale else "rs-watchlist"
    rows = daily._map_rs_rankings(
        [{"ticker": "TEST", "price": 100, "rs_percentile": 95}], 8, source
    )
    monkeypatch.setattr(
        daily, "_rs_cache",
        {"ts": daily.time.time(), "rows": rows, "refreshing": False},
    )
    result = asyncio.run(daily.daily_decision_state(request, limit=8))
    assert result["sources"]["rs_watchlist"]["stale"] is stale
    assert result["watchlist"][0]["source"] == source
    assert result["watchlist"][0]["confidence_source"] == source
    assert result["actionable"] == [] and result["buy_now"] is None
    assert result["decision"] == "WATCHLIST"
    assert result["watchlist"][0]["risk_reward"] == 0


def test_expired_rs_watch_cache_passes_request_to_refresh(monkeypatch):
    from src.api.routers import daily_decision as daily

    request = SimpleNamespace()
    monkeypatch.setattr(daily, "_rs_cache", {
        "ts": 0, "rows": [{"ticker": "OLD"}], "refreshing": False,
    })
    refresh = AsyncMock()
    monkeypatch.setattr(daily, "_refresh_rs_cache", refresh)

    async def run():
        result = await daily._rs_watchlist(request, 8)
        await asyncio.sleep(0)
        return result

    result = asyncio.run(run())
    refresh.assert_awaited_once_with(request, 8)
    assert result == [{"ticker": "OLD", "source": "rs-watchlist-stale"}]
