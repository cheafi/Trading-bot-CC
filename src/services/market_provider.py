"""
MarketDataProvider — thin abstraction over market data sources.

Phase 1: wraps yfinance with caching and rate-limiting.
Phase 2+: swap backend to Alpaca / Polygon / Databento without
          changing any call sites.

All Discord bot hot-paths should call this instead of yfinance directly.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """Async-safe provider that wraps yfinance behind a clean API."""

    def __init__(self, cache_ttl: int = 300):
        self._cache_ttl = cache_ttl
        self._quote_cache: Dict[str, tuple] = {}  # ticker -> (ts, data)
        self._news_cache: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()
        self._yf = None

    def _get_yf(self):
        if self._yf is None:
            try:
                import yfinance as yf
                self._yf = yf
            except ImportError:
                logger.error("yfinance not installed")
        return self._yf

    # ── Quotes ────────────────────────────────────────────────

    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get latest quote data for a ticker (cached)."""
        now = time.time()
        cached = self._quote_cache.get(ticker)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        data = await asyncio.to_thread(self._sync_quote, ticker)
        self._quote_cache[ticker] = (now, data)
        return data

    def _sync_quote(self, ticker: str) -> Dict[str, Any]:
        yf = self._get_yf()
        if not yf:
            return {"price": 0, "change_pct": 0, "volume": 0}
        try:
            t = yf.Ticker(ticker.upper())
            fi = getattr(t, "fast_info", None) or {}
            info = t.info if not fi else {}
            price = (
                fi.get("lastPrice", 0)
                or fi.get("last_price", 0)
                or info.get("regularMarketPrice", 0)
                or info.get("currentPrice", 0)
            )
            prev = (
                fi.get("previousClose", 0)
                or fi.get("previous_close", 0)
                or info.get("previousClose", 0)
            )
            pct = (
                ((price - prev) / prev * 100) if prev else 0
            )
            vol = (
                fi.get("lastVolume", 0)
                or fi.get("last_volume", 0)
                or info.get("volume", 0)
            )
            mktcap = (
                fi.get("marketCap", 0)
                or fi.get("market_cap", 0)
                or info.get("marketCap", 0)
            )
            return {
                "price": float(price),
                "change_pct": round(float(pct), 2),
                "volume": int(vol),
                "market_cap": float(mktcap),
                "name": info.get("shortName", ticker),
                "prev_close": float(prev),
            }
        except Exception as exc:
            logger.warning(f"Quote fetch failed for {ticker}: {exc}")
            return {"price": 0, "change_pct": 0, "volume": 0}

    # ── Historical data ───────────────────────────────────────

    async def get_history(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data."""
        return await asyncio.to_thread(
            self._sync_history, ticker, period, interval
        )

    def _sync_history(
        self, ticker: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        yf = self._get_yf()
        if not yf:
            return None
        try:
            t = yf.Ticker(ticker.upper())
            df = t.history(period=period, interval=interval)
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
                return df
            return None
        except Exception as exc:
            logger.warning(
                f"History fetch failed for {ticker}: {exc}"
            )
            return None

    # ── News ──────────────────────────────────────────────────

    async def get_news(
        self, ticker: str, max_items: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent news for a ticker (cached)."""
        now = time.time()
        cached = self._news_cache.get(ticker)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        items = await asyncio.to_thread(
            self._sync_news, ticker, max_items
        )
        self._news_cache[ticker] = (now, items)
        return items

    def _sync_news(
        self, ticker: str, max_items: int
    ) -> List[Dict[str, Any]]:
        yf = self._get_yf()
        if not yf:
            return []
        try:
            t = yf.Ticker(ticker.upper())
            news = getattr(t, "news", None)
            if not news:
                return []
            return news[:max_items]
        except Exception as exc:
            logger.warning(
                f"News fetch failed for {ticker}: {exc}"
            )
            return []

    # ── Batch operations ──────────────────────────────────────

    async def get_quotes_batch(
        self, tickers: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get quotes for multiple tickers concurrently."""
        tasks = [self.get_quote(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                out[ticker] = {"price": 0, "change_pct": 0}
            else:
                out[ticker] = result
        return out

    # ── Cache management ──────────────────────────────────────

    def clear_cache(self):
        """Clear all caches."""
        self._quote_cache.clear()
        self._news_cache.clear()

    def cache_stats(self) -> Dict[str, int]:
        return {
            "quote_entries": len(self._quote_cache),
            "news_entries": len(self._news_cache),
        }


# Singleton
_provider: Optional[MarketDataProvider] = None


def get_market_data_provider() -> MarketDataProvider:
    global _provider
    if _provider is None:
        _provider = MarketDataProvider()
    return _provider
