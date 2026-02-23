"""
TradingAI Bot - Ingestors Package

Data ingestion services:
- MarketDataIngestor: Polygon/Alpaca REST polling
- RealtimeFeedManager: WebSocket real-time feeds
- NewsIngestor: Financial news aggregation
- SocialIngestor: Social sentiment tracking
"""
from src.ingestors.base import BaseIngestor
from src.ingestors.market_data import MarketDataIngestor
from src.ingestors.news import NewsIngestor
from src.ingestors.social import SocialIngestor, SentimentAggregator
from src.ingestors.realtime_feed import RealtimeFeedManager

__all__ = [
    'BaseIngestor',
    'MarketDataIngestor',
    'NewsIngestor',
    'SocialIngestor',
    'SentimentAggregator',
    'RealtimeFeedManager',
]
