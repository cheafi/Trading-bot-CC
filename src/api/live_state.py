"""Shared live-market caches, symbols, and quote helpers."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import Request

logger = logging.getLogger(__name__)

LIVE_INDICES = [
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("IWM", "Russell 2000"),
    ("DIA", "Dow Jones"),
]
LIVE_MACRO = [
    ("^VIX", "VIX"),
    ("GLD", "Gold"),
    ("TLT", "Bonds 20Y"),
    ("BTC-USD", "Bitcoin"),
    ("ETH-USD", "Ethereum"),
    ("USO", "Oil"),
]
LIVE_SECTORS = [
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLV", "Healthcare"),
    ("XLE", "Energy"),
    ("XLI", "Industrials"),
    ("XLY", "Consumer Disc"),
    ("XLP", "Consumer Staples"),
    ("XLU", "Utilities"),
    ("XLRE", "Real Estate"),
    ("XLC", "Communication"),
    ("XLB", "Materials"),
]
LIVE_ASIA = [
    ("EWJ", "Japan (EWJ)"),
    ("EWH", "Hong Kong (EWH)"),
    ("MCHI", "China (MCHI)"),
    ("EWY", "Korea (EWY)"),
    ("EWT", "Taiwan (EWT)"),
    ("EWA", "Australia (EWA)"),
    ("INDA", "India (INDA)"),
]

MARKET_CACHE_TTL = 120
OVERVIEW_CACHE_TTL = 90

_market_cache: Dict[str, Dict[str, Any]] = {}
_market_overview_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_prewarm_done: bool = False


def set_prewarm_done(value: bool = True) -> None:
    global _prewarm_done
    _prewarm_done = value


def is_prewarm_done() -> bool:
    return _prewarm_done


def get_overview_cache() -> Dict[str, Any]:
    return _market_overview_cache


async def mds_quote(request: Request, symbol: str) -> dict:
    """Fetch a single quote via MarketDataService (with TTL cache)."""
    now = time.time()
    cached = _market_cache.get(symbol)
    if cached and (now - cached["ts"]) < MARKET_CACHE_TTL:
        return cached["data"]

    mds = request.app.state.market_data
    try:
        q = await mds.get_quote(symbol)
        if q is None:
            return {
                "symbol": symbol,
                "price": 0,
                "change_pct": 0,
                "error": True,
            }
        prev = q["price"] - q.get("change", 0)
        result = {
            "symbol": symbol,
            "price": round(q["price"], 2),
            "change_pct": round(q["change_pct"], 2),
            "prev_close": round(prev, 2),
            "high": round(q.get("high", q["price"]), 2),
            "low": round(q.get("low", q["price"]), 2),
            "volume": q.get("volume", 0),
            "market_cap": q.get("market_cap", 0),
            "high_52w": round(q.get("high_52w", 0), 2),
            "low_52w": round(q.get("low_52w", 0), 2),
        }
        _market_cache[symbol] = {"data": result, "ts": now}
        return result
    except Exception:
        logger.debug("mds_quote failed for %s", symbol, exc_info=True)
        return {
            "symbol": symbol,
            "price": 0,
            "change_pct": 0,
            "error": True,
        }


async def mds_quote_for_app(app, symbol: str) -> dict:
    """Quote helper for startup paths without a real HTTP request."""
    from starlette.requests import Request

    request = Request({"type": "http", "app": app})
    return await mds_quote(request, symbol)


async def fetch_regime_state(request: Request):
    """Return cached RegimeState from app, refreshing every 60s."""
    now = time.monotonic()
    if (
        request.app.state.regime_cache
        and (now - request.app.state.regime_cache_ts) < 60
    ):
        return request.app.state.regime_cache

    try:
        mkt = await request.app.state.market_data.get_market_state()
        state = request.app.state.regime_router.classify(mkt)
        request.app.state.regime_cache = state
        request.app.state.regime_cache_ts = now
        return state
    except Exception as exc:
        logger.warning("[Regime] classify error: %s", exc)
        if request.app.state.regime_cache:
            return request.app.state.regime_cache
        from src.engines.regime_router import RegimeState

        return RegimeState()
