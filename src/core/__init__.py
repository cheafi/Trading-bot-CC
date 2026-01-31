"""
TradingAI Bot - Core Module
"""
from src.core.config import get_settings, get_trading_config, Settings, TradingConfig
from src.core.models import (
    Signal, Direction, Horizon, StopType, SignalStatus,
    MarketRegime, VolatilityRegime, TrendRegime, RiskRegime,
    OHLCV, Quote, MarketSnapshot,
    TechnicalFeatures, MarketBreadth,
    NewsArticle, SocialPost, CalendarEvent,
    DailyReport, BacktestResult, BacktestTrade
)
from src.core.database import get_session, check_database_health

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
    
    # Database
    "get_session",
    "check_database_health",
]
