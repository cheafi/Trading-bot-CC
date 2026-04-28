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

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RegimeService:
    """Singleton regime provider with caching."""

    _cache: Dict[str, Any] = {}
    _cache_time: float = 0
    CACHE_TTL = 4 * 3600  # 4 hours

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
        return regime

    @classmethod
    def _fetch_closes(cls) -> Dict[str, list]:
        """Fetch 60-day closes for benchmarks."""
        tickers = ["SPY", "QQQ", "^VIX", "IWM", "HYG"]
        closes: Dict[str, list] = {}

        # Try MarketDataService first (async → sync bridge)
        try:
            import asyncio

            from src.services.market_data import get_market_data_service

            mds = get_market_data_service()

            async def _fetch_all():
                results = {}
                for t in tickers:
                    try:
                        hist = await mds.get_history(t, period="3mo", interval="1d")
                        if hist and "closes" in hist:
                            results[t] = hist["closes"]
                        elif hist and isinstance(hist, list):
                            results[t] = [bar.get("close", 0) for bar in hist]
                    except Exception:
                        pass
                return results

            try:
                loop = asyncio.get_running_loop()
                # Already in async context — can't nest
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    closes = pool.submit(asyncio.run, _fetch_all()).result(timeout=30)
            except RuntimeError:
                closes = asyncio.run(_fetch_all())

        except Exception as e:
            logger.debug("MarketDataService failed: %s", e)

        # Fallback to yfinance
        if not closes.get("SPY"):
            try:
                import yfinance as yf

                for t in tickers:
                    try:
                        data = yf.download(
                            t,
                            period="3mo",
                            interval="1d",
                            progress=False,
                        )
                        if data is not None and len(data) > 0:
                            closes[t] = data["Close"].tolist()
                    except Exception:
                        pass
            except ImportError:
                logger.warning("yfinance not installed")

        # Final fallback: synthetic
        if not closes.get("SPY"):
            logger.warning("No market data — using synthetic")
            closes = cls._synthetic_closes()

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
        }
