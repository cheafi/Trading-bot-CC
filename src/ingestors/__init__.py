"""
TradingAI Bot - Ingestors Package

Data ingestion services:
- MarketDataIngestor: Polygon/Alpaca REST polling
- RealtimeFeedManager: WebSocket real-time feeds
- NewsIngestor: Financial news aggregation
- SocialIngestor: Social sentiment tracking
"""
_LAZY = {
    "BaseIngestor": "src.ingestors.base",
    "MarketDataIngestor": "src.ingestors.market_data",
    "NewsIngestor": "src.ingestors.news",
    "SocialIngestor": "src.ingestors.social",
    "SentimentAggregator": "src.ingestors.social",
    "RealtimeFeedManager": "src.ingestors.realtime_feed",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
