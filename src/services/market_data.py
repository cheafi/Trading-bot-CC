"""
Centralised market-data service
================================
All yfinance fetches go through here.

Features
--------
* Per-symbol/period/interval TTL cache — same symbol never fetched twice
  within the TTL window, regardless of how many background tasks request it.
* Async-safe — concurrent requests for the same key serialise on a per-key
  asyncio.Lock; the first caller fetches, the rest wait then read cache.
* yfinance runs in a thread-pool executor so it never blocks the Discord
  event loop.
* Exponential backoff + jitter on transient fetch errors.
* Frame validation: rejects empty frames, missing Close column, and frames
  with >20% NaN in the Close series.
* Stale-data markers — callers can force a re-fetch, and the service
  self-marks entries stale after permanent failures.
* cache_stats() exposes health data for /status.

Usage
-----
    from src.services.market_data import get_market_data_service

    svc = get_market_data_service()
    df  = await svc.get_history("NVDA", period="1y", interval="1d")
    if df is None:
        # unavailable — handle gracefully, do not crash the task
        return
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── tunables ─────────────────────────────────────────────────────────────────

# Cache TTL in seconds per interval type
DEFAULT_TTL: Dict[str, int] = {
    "1d":  300,    # 5 min  — daily bars update infrequently during the day
    "1h":  180,    # 3 min
    "5m":   60,    # 1 min
    "1m":   30,    # 30 s
}

# Minimum non-NaN rows before a frame is accepted
MIN_ROWS: Dict[str, int] = {
    "1d": 10,
    "1h": 10,
    "5m": 20,
    "1m": 10,
}

# Approximate max trading-day rows each period can deliver (daily interval)
_PERIOD_MAX_DAILY: Dict[str, int] = {
    "1d": 1, "5d": 5, "1mo": 22, "3mo": 66, "6mo": 132,
    "1y": 252, "2y": 504, "5y": 1260, "10y": 2520, "max": 99999,
}

MAX_NAN_FRACTION = 0.20     # reject if >20% of Close values are NaN
BACKOFF_BASE     = 1.5      # base for exponential back-off
BACKOFF_MAX = 10.0  # cap on back-off delay (seconds)
JITTER_FRAC      = 0.30     # ±30% random jitter applied to each delay
MAX_RETRIES = 2  # reduced: neg-cache handles persistent failures


# ── internal cache entry ──────────────────────────────────────────────────────

class _CacheEntry:
    """Single cached frame with metadata."""
    __slots__ = ("df", "fetched_at", "stale", "error_count", "key")

    def __init__(self, key: str, df: Optional[pd.DataFrame]):
        self.key         = key
        self.df          = df
        self.fetched_at  = time.monotonic()
        self.stale       = (df is None)
        self.error_count = 0 if df is not None else 1

    def is_fresh(self, ttl: int) -> bool:
        return (not self.stale) and (time.monotonic() - self.fetched_at) < ttl


# ── main service class ────────────────────────────────────────────────────────

class MarketDataService:
    """
    Async-safe, cached market-data service backed by yfinance.

    All 23 background tasks and 54 commands share a single instance
    so the same (ticker, period, interval) triplet is never fetched twice
    within the TTL window.
    """

    def __init__(self):
        self._cache: Dict[str, _CacheEntry] = {}
        self._per_key_locks: Dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()   # guards _per_key_locks dict

    # ── public API ────────────────────────────────────────────────────────────

    async def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """
        Return a validated OHLCV DataFrame.

        Returns None if the data is unavailable, fails validation, or all
        retries are exhausted.  Callers MUST handle the None case — never
        assume a valid frame.
        """
        key = _cache_key(ticker, period, interval)
        ttl = DEFAULT_TTL.get(interval, 300)

        # Fast path: check cache without locking (safe; Python GIL + monotonic read)
        entry = self._cache.get(key)
        if entry and entry.is_fresh(ttl):
            return entry.df

        # Serialise concurrent fetches for the same key
        lock = await self._get_lock(key)
        async with lock:
            # Re-check after acquiring the lock — another coroutine may have
            # populated the cache while we were waiting.
            entry = self._cache.get(key)
            if entry and entry.is_fresh(ttl):
                return entry.df

            df = await self._fetch_with_retry(ticker, period, interval)
            self._cache[key] = _CacheEntry(key, df)
            return df

    async def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Return a lightweight price snapshot dict for a ticker.

        Keys: ticker, price, change, change_pct, volume.
        Returns None on failure.
        """
        df = await self.get_history(ticker, period="5d", interval="1d")
        if df is None or df.empty:
            return None
        try:
            close_col  = "Close" if "Close" in df.columns else "close"
            vol_col    = "Volume" if "Volume" in df.columns else "volume"
            last       = df.iloc[-1]
            prev       = df.iloc[-2] if len(df) >= 2 else last
            close      = float(last[close_col])
            prev_close = float(prev[close_col])
            chg        = close - prev_close
            chg_pct    = (chg / prev_close * 100) if prev_close else 0.0
            return {
                "ticker":     ticker,
                "price":      round(close, 4),
                "change":     round(chg, 4),
                "change_pct": round(chg_pct, 2),
                "volume":     int(last.get(vol_col, 0)),
            }
        except Exception as exc:
            logger.warning(f"[MarketData] get_quote({ticker}) parse error: {exc}")
            return None

    async def get_multi_quotes(
        self, tickers: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch quotes for multiple tickers concurrently.
        Returns dict of ticker → quote (or None).
        """
        results = await asyncio.gather(
            *[self.get_quote(t) for t in tickers], return_exceptions=False
        )
        return dict(zip(tickers, results))

    def mark_stale(self, ticker: str, interval: str = "1d") -> None:
        """
        Force the next access for this ticker/interval to re-fetch.
        Use after a detected data quality issue.
        """
        for key, entry in self._cache.items():
            if key.startswith(f"{ticker}:") and f":{interval}" in key:
                entry.stale = True

    def invalidate(self, ticker: str) -> None:
        """Invalidate ALL cached data for a ticker across all periods/intervals."""
        keys_to_drop = [k for k in self._cache if k.startswith(f"{ticker}:")]
        for k in keys_to_drop:
            del self._cache[k]

    async def get_news(self, ticker: str, max_items: int = 5) -> list:
        """
        Fetch recent news for a ticker via yfinance.
        Returns list of dicts with title, url, publisher, time keys.
        Cached for 5 minutes via the standard cache.
        """
        cache_key = f"{ticker}:news"
        entry = self._cache.get(cache_key)
        if entry and entry.is_fresh(300) and entry.df is not None:
            return entry.df  # reuse df field to store list

        def _sync():
            try:
                import yfinance as yf
                t = yf.Ticker(ticker.upper())
                raw = t.news if hasattr(t, "news") else []
                out = []
                for item in (raw or []):
                    url = item.get("link", item.get("url", ""))
                    title = item.get("title", "")
                    if url and title and len(out) < max_items:
                        out.append({
                            "title": title[:200],
                            "url": url,
                            "publisher": item.get("publisher", ""),
                            "time": item.get("providerPublishTime", 0),
                        })
                return out
            except Exception as exc:
                logger.warning(f"[MarketData] get_news({ticker}) error: {exc}")
                return []

        result = await asyncio.to_thread(_sync)
        # Store in cache (abuse df field for list)
        self._cache[cache_key] = _CacheEntry(cache_key, result)
        return result

    # ── market-state helpers (used by ContextAssembler / regime) ────────────

    async def get_vix(self) -> float:
        """Return current VIX level.  Cached via standard get_history TTL."""
        q = await self.get_quote("^VIX")
        return q["price"] if q else 18.0

    async def get_spy_return(self, window: int = 20) -> float:
        """Return SPY % return over *window* trading days."""
        df = await self.get_history("SPY", period="3mo", interval="1d")
        if df is None or len(df) < window:
            return 0.0
        try:
            close = df["Close"]
            ret = (float(close.iloc[-1]) / float(close.iloc[-window]) - 1)
            return round(ret, 4)
        except Exception:
            return 0.0

    async def get_market_breadth(self) -> float:
        """Approximate breadth: fraction of 11 sector ETFs above SMA(20)."""
        sectors = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY",
                    "XLP", "XLU", "XLRE", "XLC", "XLB"]
        above = 0
        total = 0
        results = await asyncio.gather(
            *[self.get_history(s, period="2mo", interval="1d") for s in sectors],
            return_exceptions=True,
        )
        for df in results:
            if isinstance(df, Exception) or df is None or len(df) < 20:
                continue
            try:
                close = df["Close"]
                sma20 = float(close.rolling(20).mean().iloc[-1])
                total += 1
                if float(close.iloc[-1]) > sma20:
                    above += 1
            except Exception:
                continue
        return round(above / total, 2) if total > 0 else 0.50

    async def get_market_state(self) -> Dict[str, Any]:
        """
        One-shot helper: fetch VIX, SPY return, breadth concurrently.
        Returns dict ready for RegimeRouter.classify().
        """
        vix, spy_ret, breadth, spy_hist = await asyncio.gather(
            self.get_vix(),
            self.get_spy_return(20),
            self.get_market_breadth(),
            self.get_history("SPY", period="1mo", interval="1d"),
        )
        # Compute 20-day annualised realised vol from SPY daily log-returns (live, no look-ahead)
        realized_vol = 0.15  # fallback when data unavailable
        try:
            import numpy as _np
            if spy_hist is not None and not spy_hist.empty:
                c_col = "Close" if "Close" in spy_hist.columns else "close"
                closes = spy_hist[c_col].dropna().values.astype(float)
                if len(closes) >= 5:
                    log_rets = _np.diff(_np.log(closes))[-20:]
                    if len(log_rets) > 1:
                        realized_vol = round(float(_np.std(log_rets) * (252 ** 0.5)), 4)
        except Exception:
            pass
        return {
            "vix": vix,
            "spy_return_20d": spy_ret,
            "breadth_pct": breadth,
            "hy_spread": 0.0,
            "realized_vol_20d": realized_vol,
            "vix_term_slope": 0.0,
        }

    def cache_stats(self) -> Dict[str, Any]:
        """
        Health snapshot for /status command.
        Returns entry counts, freshness, and cumulative error count.
        """
        now    = time.monotonic()
        total  = len(self._cache)
        fresh  = sum(1 for e in self._cache.values() if e.is_fresh(300))
        stale  = sum(1 for e in self._cache.values() if e.stale)
        errors = sum(e.error_count for e in self._cache.values())
        return {
            "entries":      total,
            "fresh":        fresh,
            "stale":        stale,
            "total_errors": errors,
        }

    # ── internal helpers ──────────────────────────────────────────────────────

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Return (and lazily create) a per-key asyncio.Lock."""
        async with self._registry_lock:
            if key not in self._per_key_locks:
                self._per_key_locks[key] = asyncio.Lock()
            return self._per_key_locks[key]

    async def _fetch_with_retry(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch from yfinance with retries, exponential back-off, and jitter.
        yfinance is synchronous; run_in_executor prevents blocking the loop.
        """
        import yfinance as yf

        last_exc: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None,
                    lambda: yf.Ticker(ticker).history(
                        period=period, interval=interval, auto_adjust=True
                    ),
                )
                validated = _validate_frame(df, ticker, interval, period)
                if validated is not None:
                    return validated
                # Validation failed — may be transient (partial data); retry
                logger.warning(
                    f"[MarketData] {ticker}/{period}/{interval} "
                    f"validation failed (attempt {attempt + 1}/{MAX_RETRIES})"
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    f"[MarketData] {ticker} fetch error "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}): {exc}"
                )

            if attempt < MAX_RETRIES - 1:
                base_delay = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                jitter     = base_delay * JITTER_FRAC * (2 * random.random() - 1)
                delay      = max(0.5, base_delay + jitter)
                logger.debug(f"[MarketData] {ticker} retry in {delay:.1f}s")
                await asyncio.sleep(delay)

        logger.error(
            f"[MarketData] {ticker}/{period}/{interval} failed after "
            f"{MAX_RETRIES} attempts. Last error: {last_exc}"
        )
        return None


# ── frame validation (module-level, stateless) ───────────────────────────────

def _validate_frame(
    df: Any, ticker: str, interval: str, period: str = "1y"
) -> Optional[pd.DataFrame]:
    """
    Accept a DataFrame only if it passes all quality gates:
      1. Is a non-empty DataFrame.
      2. Has a recognised Close column.
      3. NaN fraction in Close ≤ MAX_NAN_FRACTION.
      4. Has at least MIN_ROWS non-NaN Close values (capped by period).
    Returns the validated (possibly column-normalised) df, or None.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        logger.debug(f"[MarketData] {ticker}: empty or non-DataFrame result")
        return None

    # Normalise column name capitalisation
    col_map = {c.strip().lower(): c.strip() for c in df.columns}
    rename  = {}
    for orig, normalised in col_map.items():
        if orig == "close" and "Close" not in df.columns:
            rename[normalised] = "Close"
        elif orig == "volume" and "Volume" not in df.columns:
            rename[normalised] = "Volume"
    if rename:
        df = df.rename(columns=rename)

    if "Close" not in df.columns:
        logger.debug(f"[MarketData] {ticker}: no Close column after normalisation")
        return None

    close     = df["Close"]
    nan_frac  = close.isna().mean()
    min_valid = MIN_ROWS.get(interval, 10)
    # Cap min_valid by what the period can actually deliver.
    # E.g. period="5d" + interval="1d" → max 5 rows; don't require 10.
    period_max = _PERIOD_MAX_DAILY.get(period, 99999)
    min_valid = min(min_valid, max(1, period_max - 2))   # 2-row slack for holidays

    if nan_frac > MAX_NAN_FRACTION:
        logger.warning(
            f"[MarketData] {ticker}: NaN fraction {nan_frac:.1%} "
            f"> {MAX_NAN_FRACTION:.0%} — rejected"
        )
        return None

    valid_rows = int(close.notna().sum())
    if valid_rows < min_valid:
        logger.warning(
            f"[MarketData] {ticker}: only {valid_rows} valid rows "
            f"(need {min_valid}) — rejected"
        )
        return None

    return df


# ── cache key helper ──────────────────────────────────────────────────────────

def _cache_key(ticker: str, period: str, interval: str) -> str:
    return f"{ticker.upper()}:{period}:{interval}"


# ── module-level singleton ────────────────────────────────────────────────────

_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Return (lazily creating) the global MarketDataService singleton."""
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
