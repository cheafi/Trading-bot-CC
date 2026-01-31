"""
TradingAI Bot - News Ingestor
Fetches news articles from various providers and analyzes sentiment.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp
import hashlib

from src.core.config import get_settings
from src.core.database import get_session
from src.ingestors.base import BaseIngestor

settings = get_settings()


class NewsIngestor(BaseIngestor):
    """
    Ingests news articles from multiple providers:
    - NewsAPI
    - Benzinga (if API key available)
    - Finnhub
    
    Includes GPT-based sentiment analysis.
    """
    
    NEWSAPI_BASE_URL = "https://newsapi.org/v2"
    BENZINGA_BASE_URL = "https://api.benzinga.com/api/v2"
    FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self):
        super().__init__("news")
        self.newsapi_key = settings.newsapi_key
        self.benzinga_key = getattr(settings, 'benzinga_api_key', None)
        self.finnhub_key = settings.finnhub_api_key
        self._rate_limit_delay = 1.0  # NewsAPI has strict rate limits
    
    async def fetch(
        self,
        tickers: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch news articles for specified tickers or keywords.
        
        Args:
            tickers: List of ticker symbols to search for
            keywords: Additional keywords to search
            start_date: Start date for news search
            end_date: End date for news search
        
        Returns:
            List of news article records
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        all_articles = []
        
        # Fetch from NewsAPI
        if self.newsapi_key:
            articles = await self._fetch_newsapi(tickers, keywords, start_date, end_date)
            all_articles.extend(articles)
        
        # Fetch from Finnhub (company news)
        if self.finnhub_key and tickers:
            for ticker in tickers[:20]:  # Limit to avoid rate limits
                await self._respect_rate_limit()
                articles = await self._fetch_finnhub(ticker, start_date, end_date)
                all_articles.extend(articles)
        
        # Deduplicate by URL/title hash
        seen = set()
        unique_articles = []
        for article in all_articles:
            article_hash = self._hash_article(article)
            if article_hash not in seen:
                seen.add(article_hash)
                unique_articles.append(article)
        
        return unique_articles
    
    async def _fetch_newsapi(
        self,
        tickers: Optional[List[str]],
        keywords: Optional[List[str]],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch articles from NewsAPI."""
        # Build query
        search_terms = []
        if tickers:
            search_terms.extend(tickers[:5])  # Limit to avoid too long query
        if keywords:
            search_terms.extend(keywords)
        
        if not search_terms:
            search_terms = ["stock market", "S&P 500", "NASDAQ", "earnings"]
        
        query = " OR ".join(search_terms)
        
        url = f"{self.NEWSAPI_BASE_URL}/everything"
        params = {
            "q": query,
            "from": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "to": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": 100,
            "apiKey": self.newsapi_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    self.logger.warning(f"NewsAPI error: {response.status}")
                    return []
                
                data = await response.json()
                
                if data.get("status") != "ok":
                    return []
                
                articles = []
                for article in data.get("articles", []):
                    articles.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "content": article.get("content", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "published_at": article.get("publishedAt"),
                        "author": article.get("author"),
                        "image_url": article.get("urlToImage"),
                        "provider": "newsapi",
                        "tickers": self._extract_tickers(
                            article.get("title", "") + " " + article.get("description", ""),
                            tickers or []
                        )
                    })
                
                return articles
    
    async def _fetch_finnhub(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch company news from Finnhub."""
        url = f"{self.FINNHUB_BASE_URL}/company-news"
        params = {
            "symbol": ticker,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "token": self.finnhub_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                
                articles = []
                for item in data[:50]:  # Limit articles per ticker
                    articles.append({
                        "title": item.get("headline", ""),
                        "description": item.get("summary", ""),
                        "content": item.get("summary", ""),
                        "url": item.get("url", ""),
                        "source": item.get("source", ""),
                        "published_at": datetime.fromtimestamp(
                            item.get("datetime", 0)
                        ).isoformat(),
                        "author": None,
                        "image_url": item.get("image"),
                        "provider": "finnhub",
                        "tickers": [ticker],
                        "category": item.get("category")
                    })
                
                return articles
    
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform and enrich news articles with sentiment."""
        transformed = []
        
        for article in raw_data:
            # Skip articles without title
            if not article.get("title"):
                continue
            
            # Parse published date
            published_at = article.get("published_at")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    published_at = datetime.utcnow()
            
            # Basic sentiment from keywords (GPT analysis done separately)
            content = (
                article.get("title", "") + " " + 
                article.get("description", "")
            ).lower()
            
            sentiment_score = self._basic_sentiment(content)
            
            transformed.append({
                "id": self._hash_article(article),
                "title": article["title"][:500],
                "description": (article.get("description") or "")[:2000],
                "content": (article.get("content") or "")[:10000],
                "url": article.get("url", ""),
                "source": article.get("source", "unknown"),
                "author": article.get("author"),
                "published_at": published_at,
                "image_url": article.get("image_url"),
                "provider": article.get("provider", "unknown"),
                "tickers": article.get("tickers", []),
                "category": article.get("category"),
                "sentiment_score": sentiment_score,
                "sentiment_label": self._sentiment_label(sentiment_score)
            })
        
        return transformed
    
    async def store(self, records: List[Dict[str, Any]]) -> int:
        """Store news articles in database."""
        if not records:
            return 0
        
        stored_count = 0
        
        async with get_session() as session:
            try:
                from sqlalchemy import text
                
                for record in records:
                    # Escape single quotes in text fields
                    title = record["title"].replace("'", "''")
                    description = (record.get("description") or "").replace("'", "''")
                    content = (record.get("content") or "").replace("'", "''")
                    source = record["source"].replace("'", "''")
                    author = (record.get("author") or "").replace("'", "''")
                    tickers_str = ",".join(record.get("tickers", []))
                    
                    sql = f"""
                        INSERT INTO news_articles (
                            id, title, description, content, url, source,
                            author, published_at, provider, tickers,
                            sentiment_score, sentiment_label
                        )
                        VALUES (
                            '{record["id"]}', '{title}', '{description}', 
                            '{content}', '{record["url"]}', '{source}',
                            '{author}', '{record["published_at"]}', 
                            '{record["provider"]}', '{tickers_str}',
                            {record["sentiment_score"]}, '{record["sentiment_label"]}'
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            sentiment_score = EXCLUDED.sentiment_score,
                            sentiment_label = EXCLUDED.sentiment_label,
                            updated_at = NOW()
                    """
                    
                    await session.execute(text(sql))
                    stored_count += 1
                
                await session.commit()
                
            except Exception as e:
                self.logger.error(f"Failed to store news: {e}")
                await session.rollback()
                raise
        
        return stored_count
    
    def _hash_article(self, article: Dict[str, Any]) -> str:
        """Generate unique hash for article deduplication."""
        content = article.get("url", "") or article.get("title", "")
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _extract_tickers(self, text: str, known_tickers: List[str]) -> List[str]:
        """Extract ticker symbols mentioned in text."""
        found = []
        text_upper = text.upper()
        
        for ticker in known_tickers:
            # Look for ticker as whole word
            if f" {ticker} " in f" {text_upper} " or f"${ticker}" in text_upper:
                found.append(ticker)
        
        return found
    
    def _basic_sentiment(self, text: str) -> float:
        """Basic keyword-based sentiment scoring (-1 to 1)."""
        positive_words = [
            "surge", "rally", "gain", "up", "rise", "bullish", "beat", 
            "exceeds", "strong", "growth", "upgrade", "outperform",
            "record high", "breakthrough", "success", "profit"
        ]
        negative_words = [
            "fall", "drop", "down", "decline", "bearish", "miss",
            "weak", "cut", "downgrade", "underperform", "crash",
            "plunge", "loss", "warning", "concern", "risk"
        ]
        
        text_lower = text.lower()
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        
        return (pos_count - neg_count) / total
    
    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score >= 0.3:
            return "BULLISH"
        elif score <= -0.3:
            return "BEARISH"
        else:
            return "NEUTRAL"
