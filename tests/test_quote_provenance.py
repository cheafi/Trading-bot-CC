"""Quote provenance propagation and fail-closed decision gates."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.core.models import TradeRecommendation
from src.core.quote_provenance import (
    SOURCE_DAILY_BAR,
    attach_bar_provenance_to_recommendation,
    flatten_provenance_to_api_dict,
    index_to_utc_iso,
    provenance_from_daily_bar_series,
    provenance_from_mapping,
    quote_age_seconds,
)
from src.core.trade_decision import DataFreshness, trade_decision_from_recommendation
from src.engines.daily_decision_engine import DailyDecisionEngine


def _fresh_ts(minutes_ago: float = 2.0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    ).isoformat().replace("+00:00", "Z")


def _tradeable_regime() -> dict:
    return {"regime": "RISK_ON", "should_trade": True, "entropy": 0.4}


def test_daily_bar_provenance_from_series() -> None:
    idx = pd.date_range("2026-03-01", periods=3, freq="D", tz="UTC")
    close = pd.Series([98.0, 99.0, 100.0], index=idx)
    prov = provenance_from_daily_bar_series(close)
    assert prov is not None
    assert prov.quote_source == SOURCE_DAILY_BAR
    assert prov.quote_price == 100.0
    assert prov.quote_timestamp is not None
    assert prov.research_as_of == prov.quote_timestamp


def test_attach_bar_provenance_to_recommendation() -> None:
    idx = pd.date_range("2026-03-01", periods=2, freq="D", tz="UTC")
    close = pd.Series([99.0, 100.0], index=idx)
    rec = TradeRecommendation(ticker="AAPL", entry_price=100.0, stop_price=95.0)
    assert attach_bar_provenance_to_recommendation(rec, close) is True
    assert rec.metadata.get("price_source") == SOURCE_DAILY_BAR
    assert rec.metadata.get("price_timestamp") is not None


def test_cache_flatten_preserves_provenance() -> None:
    row = {
        "ticker": "MSFT",
        "metadata": {
            "price_timestamp": _fresh_ts(),
            "price_source": "market_data:live_quote",
            "quote_price": 400.0,
            "research_as_of": _fresh_ts(60),
        },
    }
    out = flatten_provenance_to_api_dict(dict(row))
    assert out["price_timestamp"] == row["metadata"]["price_timestamp"]
    assert out["price_source"] == "market_data:live_quote"
    assert out["quote_price"] == 400.0


def test_from_dict_roundtrip_preserves_metadata() -> None:
    d = {
        "ticker": "NVDA",
        "entry_price": 900,
        "stop_price": 880,
        "target_price": 940,
        "price_timestamp": _fresh_ts(),
        "price_source": "market_data:live_quote",
        "quote_price": 900,
    }
    rec = TradeRecommendation.from_dict(d)
    assert rec.metadata.get("price_timestamp") == d["price_timestamp"]
    assert rec.metadata.get("price_source") == d["price_source"]


def test_stale_daily_bar_not_executable_buy() -> None:
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace(
        "+00:00", "Z"
    )
    rec = TradeRecommendation.from_dict(
        {
            "ticker": "AAPL",
            "direction": "LONG",
            "entry_price": 100,
            "stop_price": 95,
            "target_price": 110,
            "price_timestamp": stale_ts,
            "price_source": SOURCE_DAILY_BAR,
            "quote_price": 100,
        }
    )
    rec.stop_price = 95.0
    rec.trade_decision = True
    d = trade_decision_from_recommendation(rec, regime=_tradeable_regime())
    assert d.data_freshness == DataFreshness.STALE
    assert d.action != "BUY"
    assert not d.is_actionable


def test_fresh_live_quote_can_be_actionable_when_gates_pass() -> None:
    eng = DailyDecisionEngine()
    out = eng.build(
        [
            {
                "ticker": "AAPL",
                "direction": "LONG",
                "strategy_id": "momentum",
                "score": 0.72,
                "confidence": 72,
                "entry_price": 100.0,
                "stop_price": 95.0,
                "target_price": 110.0,
                "price_timestamp": _fresh_ts(2),
                "price_source": "market_data:live_quote",
                "quote_price": 100.0,
                "trust": {"mode": "LIVE", "freshness": "REAL_TIME"},
            }
        ],
        regime=_tradeable_regime(),
    )
    top = out.decisions[0]
    assert top.data_freshness == DataFreshness.VERIFIED
    assert top.quote_source == "market_data:live_quote"
    assert top.quote_age_seconds is not None
    assert top.is_actionable


def test_non_finite_quote_blocks_verified() -> None:
    rec = TradeRecommendation.from_dict(
        {
            "ticker": "X",
            "entry_price": 10,
            "stop_price": 9,
            "target_price": 12,
            "price_timestamp": _fresh_ts(),
            "price_source": "market_data:live_quote",
            "quote_price": float("nan"),
        }
    )
    d = trade_decision_from_recommendation(rec, regime=_tradeable_regime())
    assert d.data_freshness == DataFreshness.UNVERIFIED
    assert d.action != "BUY"


def test_high_score_cannot_override_missing_source() -> None:
    eng = DailyDecisionEngine()
    out = eng.build(
        [
            {
                "ticker": "ZZZ",
                "direction": "LONG",
                "score": 0.99,
                "confidence": 99,
                "entry_price": 50,
                "stop_price": 48,
                "target_price": 55,
                "price_timestamp": _fresh_ts(),
            }
        ],
        regime=_tradeable_regime(),
    )
    assert out.decisions[0].action != "BUY"
    assert out.no_trade is True


def test_index_to_utc_iso_rejects_garbage() -> None:
    assert index_to_utc_iso("not-a-date") is None


def test_quote_age_seconds_future_returns_none_or_zero() -> None:
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z"
    )
    prov = provenance_from_mapping({"price_timestamp": future, "price_source": "x"})
    assert prov.quote_timestamp == future
