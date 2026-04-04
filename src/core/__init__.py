"""
TradingAI Bot - Core Module

NOTE: database imports are NOT auto-loaded here to avoid coupling
every simple model/config import to SQLAlchemy + asyncpg.
Use `from src.core.database import get_session` explicitly when needed.
"""

from src.core.config import Settings, TradingConfig, get_settings, get_trading_config
from src.core.models import (
    OHLCV,
    BacktestResult,
    BacktestTrade,
    CalendarEvent,
    DailyReport,
    Direction,
    Horizon,
    MarketBreadth,
    MarketRegime,
    MarketSnapshot,
    NewsArticle,
    Quote,
    RiskRegime,
    Signal,
    SignalStatus,
    SocialPost,
    StopType,
    TechnicalFeatures,
    TrendRegime,
    VolatilityRegime,
)

__all__ = [
    # Config
    "get_settings",
    "get_trading_config",
    "Settings",
    "TradingConfig",
    # Models
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
