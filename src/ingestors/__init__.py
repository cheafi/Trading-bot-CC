"""
TradingAI Bot - Ingestors Package
Data ingestion services for market data, news, and social sentiment.
"""
from src.ingestors.base import BaseIngestor
from src.ingestors.market_data import MarketDataIngestor
from src.ingestors.news import NewsIngestor
from src.ingestors.social import SocialIngestor, SentimentAggregator

__all__ = [
    'BaseIngestor',
    'MarketDataIngestor',
    'NewsIngestor',
    'SocialIngestor',
    'SentimentAggregator',
]
