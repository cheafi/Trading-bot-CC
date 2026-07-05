"""
TradingAI Bot - Core Module

NOTE: Models are lazy-imported to avoid pulling pydantic on every
config import.  Use ``from src.core.models import Signal`` directly
when you need model classes.
"""

from src.core.config import (  # noqa: F401 — always fast
    Settings,
    TradingConfig,
    get_settings,
    get_trading_config,
)


def __getattr__(name: str):
    """Lazy-import models on first access (avoids 250s pydantic load)."""
    _MODEL_NAMES = {
        "OHLCV", "BacktestResult", "BacktestTrade", "CalendarEvent",
        "DailyReport", "Direction", "Horizon", "MarketBreadth",
        "MarketRegime", "MarketSnapshot", "NewsArticle", "Quote",
        "RiskRegime", "Signal", "SignalStatus", "SocialPost",
        "StopType", "TechnicalFeatures", "TrendRegime",
        "VolatilityRegime",
    }
    if name in _MODEL_NAMES:
        import importlib
        mod = importlib.import_module("src.core.models")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_settings",
    "get_trading_config",
    "Settings",
    "TradingConfig",
    "Signal",
    "Direction",
    "Horizon",
    "StopType",
    "SignalStatus",
    "MarketRegime",
    "VolatilityRegime",
    "TrendRegime",
    "RiskRegime",
    "OHLCV",
    "Quote",
    "MarketSnapshot",
    "TechnicalFeatures",
    "MarketBreadth",
    "NewsArticle",
    "SocialPost",
    "CalendarEvent",
    "DailyReport",
    "BacktestResult",
    "BacktestTrade",
]
