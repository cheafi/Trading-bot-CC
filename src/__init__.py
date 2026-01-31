"""
TradingAI Bot - Main Package
AI-powered US equities market intelligence system.
"""

__version__ = "1.0.0"
__author__ = "TradingAI Team"

# Lazy imports to avoid circular dependency issues
# Import specific modules when needed:
#   from src.core.config import get_settings
#   from src.core.models import Signal
#   from src.engines import FeatureEngine, SignalEngine

__all__ = [
    "__version__",
    "__author__",
]

__all__ = [
    # Version
    '__version__',
    
    # Core
    'settings',
    'Signal',
    'MarketOverview',
    'TechnicalFeatures',
    'get_db_session',
    'AsyncSessionLocal',
    
    # Engines
    'FeatureEngine',
    'SignalEngine',
    'GPTSignalValidator',
    'GPTSummarizer',
    
    # Strategies
    'get_strategy',
    'get_all_strategies',
    
    # Ingestors
    'MarketDataIngestor',
    'NewsIngestor',
    'SocialIngestor',
    'SentimentAggregator',
    
    # Backtesting
    'Backtester',
]
