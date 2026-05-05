"""
Regime Service — Sprint 67
============================
Singleton that fetches SPY/QQQ/VIX/IWM/HYG via MarketDataService,
runs MacroRegimeEngine.compute(), and caches for 4 hours.

Usage:
    from src.services.regime_service import RegimeService
    regime = RegimeService.get()  # dict compatible with pipeline
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RegimeService:
    """Singleton regime provider with caching."""

    _cache: Dict[str, Any] = {}
    _cache_time: float = 0
    CACHE_TTL = 4 * 3600  # 4 hours
    _refresh_lock: asyncio.Lock = asyncio.Lock()  # prevents duplicate concurrent fetches

    @classmethod
    def get(cls) -> Dict[str, Any]:
        """
        Get current regime dict. Returns cached if fresh,
        otherwise fetches and computes.
        """
        now = time.time()
        if cls._cache and (now - cls._cache_time) < cls.CACHE_TTL:
            return cls._cache

        try:
            result = cls._fetch_and_compute()
            cls._cache = result
            cls._cache_time = now
            return result
        except Exception as e:
            logger.error("RegimeService fetch failed: %s", e)
            if cls._cache:
                return cls._cache
            return cls._default_regime()

    @classmethod
    async def aget(cls) -> Dict[str, Any]:
        """
        Async-safe regime getter.  Runs the blocking _fetch_and_compute()
        in a thread so the FastAPI event loop is never stalled.
        Returns cached value immediately when still fresh.
        Lock prevents duplicate concurrent fetches when multiple requests
        hit a stale cache simultaneously (thundering-herd guard).
        """
        now = time.time()
        if cls._cache and (now - cls._cache_time) < cls.CACHE_TTL:
            return cls._cache
        async with cls._refresh_lock:
            # Re-check inside the lock — another waiter may have already refreshed
            now = time.time()
            if cls._cache and (now - cls._cache_time) < cls.CACHE_TTL:
                return cls._cache
            return await asyncio.to_thread(cls.get)

    @classmethod
    def invalidate(cls) -> None:
        """Force refresh on next call."""
        cls._cache_time = 0

    @classmethod
    def _fetch_and_compute(cls) -> Dict[str, Any]:
        """Fetch market data and run MacroRegimeEngine."""
        from src.engines.macro_regime_engine import MacroRegimeEngine

        closes = cls._fetch_closes()
        engine = MacroRegimeEngine()
        result = engine.compute(
            spy_closes=closes.get("SPY", []),
            qqq_closes=closes.get("QQQ", []),
            vix_closes=closes.get("^VIX", []),
            iwm_closes=closes.get("IWM", []),
            hyg_closes=closes.get("HYG", []),
        )

        regime = result.to_dict()
        # Add pipeline-compatible fields
        regime["should_trade"] = result.risk_score < 75
        regime["vix"] = result.vix_level
        regime["source"] = "regime_service"
        regime["synthetic"] = getattr(cls, "_is_synthetic", False)
        return regime

    @classmethod
    def _fetch_closes(cls) -> Dict[str, list]:
        """Fetch 60-day closes for benchmarks via yfinance (sync, thread-safe)."""

        tickers = ["SPY", "QQQ", "^VIX", "IWM", "HYG"]
        closes: Dict[str, list] = {}

        # Direct yfinance fetch (synchronous — RegimeService.get() is always called sync).
        try:
            import yfinance as yf

            for t in tickers:
                try:
                    data = yf.download(
                        t,
                        period="3mo",
                        interval="1d",
                        progress=False,
                        auto_adjust=True,
                    )
                    if data is not None and len(data) > 0:
                        c_col = "Close" if "Close" in data.columns else "close"
                        closes[t] = data[c_col].dropna().tolist()
                except Exception as exc:
                    logger.debug("yfinance fetch %s failed: %s", t, exc)
        except ImportError:
            logger.warning("yfinance not installed")

        # Final fallback: synthetic
        if not closes.get("SPY"):
            logger.warning("No market data — using synthetic")
            closes = cls._synthetic_closes()
            cls._is_synthetic = True
        else:
            cls._is_synthetic = False

        return closes

    @classmethod
    def _synthetic_closes(cls) -> Dict[str, list]:
        """Generate neutral synthetic data when no source available."""
        flat = [100.0] * 60
        return {
            "SPY": flat,
            "QQQ": flat,
            "^VIX": [18.0] * 60,
            "IWM": flat,
            "HYG": flat,
        }

    @classmethod
    def _default_regime(cls) -> Dict[str, Any]:
        """Default regime when everything fails."""
        return {
            "trend": "SIDEWAYS",
            "risk_score": 50.0,
            "vix_level": 18.0,
            "vix_regime": "NORMAL",
            "spy_trend": "FLAT",
            "breadth": "neutral",
            "confidence": 0.3,
            "signals": ["no data available"],
            "should_trade": True,
            "vix": 18.0,
            "source": "default",
            "synthetic": True,
        }


# ── P3: request-scoped regime accessor ───────────────────────────────────────
# Routers import this instead of ``from src.api.main import _get_regime``.
# Reads the 60-second cache that ``_init_shared_services`` wires onto app.state.

import time as _time  # noqa: E402  (placed after class to keep class at top)

_REGIME_CACHE_TTL = 60  # mirrors main.py


async def get_regime(request):  # type: ignore[type-arg]
    """Return cached RegimeState from app.state, refreshing every 60 s.

    Works with any FastAPI ``Request`` object.  No import from main.py needed.
    """
    now = _time.monotonic()
    cache = getattr(request.app.state, "regime_cache", None)
    cache_ts = getattr(request.app.state, "regime_cache_ts", 0.0)

    if cache is not None and (now - cache_ts) < _REGIME_CACHE_TTL:
        return cache

    try:
        mkt = await request.app.state.market_data.get_market_state()
        state = request.app.state.regime_router.classify(mkt)
        request.app.state.regime_cache = state
        request.app.state.regime_cache_ts = now
        logger.debug("[RegimeService] refreshed: %s", getattr(state, "regime", "?"))
        return state
    except Exception as exc:
        logger.warning("[RegimeService] error: %s", exc)
        if cache is not None:
            return cache
        from src.engines.regime_router import RegimeState  # noqa: PLC0415
        return RegimeState()
