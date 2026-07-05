"""
TradingAI Bot - Social Media Ingestor
Fetches and analyzes social sentiment from X (Twitter), Reddit, and other platforms.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp
import hashlib
import re

from src.core.config import get_settings
from src.core.database import get_session
from src.ingestors.base import BaseIngestor

settings = get_settings()


class SocialIngestor(BaseIngestor):
    """
    Ingests social media posts and analyzes sentiment:
    - X (Twitter) API v2
    - Reddit API
    
    Focuses on:
    - Cashtag mentions ($AAPL)
    - Retail sentiment indicators
    - Trending topics
    """
    
    # X (Twitter) API v2
    X_BASE_URL = "https://api.twitter.com/2"
    
    # Reddit API
    REDDIT_BASE_URL = "https://oauth.reddit.com"
    
    # Finance subreddits to monitor
    FINANCE_SUBREDDITS = [
        "wallstreetbets", "stocks", "investing", "options",
        "stockmarket", "pennystocks", "smallstreetbets"
    ]
    
    def __init__(self):
        super().__init__("social")
        self.x_bearer_token = getattr(settings, 'x_bearer_token', None)
        self.reddit_client_id = getattr(settings, 'reddit_client_id', None)
        self.reddit_client_secret = getattr(settings, 'reddit_client_secret', None)
        self._reddit_access_token: Optional[str] = None
        self._rate_limit_delay = 1.0
    
    async def fetch(
        self,
        tickers: Optional[List[str]] = None,
        hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Fetch social media posts mentioning tickers.
        
        Args:
            tickers: Ticker symbols to search for
            hours_back: How many hours of history to fetch
        
        Returns:
            List of social post records
        """
        all_posts = []
        
        # Fetch from X (Twitter)
        if self.x_bearer_token and tickers:
            posts = await self._fetch_x_posts(tickers, hours_back)
            all_posts.extend(posts)
        
        # Fetch from Reddit
        if self.reddit_client_id and self.reddit_client_secret:
            posts = await self._fetch_reddit_posts(tickers, hours_back)
            all_posts.extend(posts)
        
        return all_posts
    
    async def _fetch_x_posts(
        self,
        tickers: List[str],
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Fetch posts from X (Twitter)."""
        posts = []
        
        # Build query with cashtags
        cashtags = " OR ".join([f"${t}" for t in tickers[:10]])
        query = f"({cashtags}) lang:en -is:retweet"
        
        start_time = (
            datetime.utcnow() - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"{self.X_BASE_URL}/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.x_bearer_token}"}
        params = {
            "query": query,
            "max_results": 100,
            "start_time": start_time,
            "tweet.fields": "created_at,author_id,public_metrics,context_annotations",
            "expansions": "author_id",
            "user.fields": "public_metrics,verified"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    self.logger.warning(f"X API error: {response.status}")
                    return []
                
                data = await response.json()
                
                # Build user lookup
                users = {}
                for user in data.get("includes", {}).get("users", []):
                    users[user["id"]] = user
                
                for tweet in data.get("data", []):
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    
                    posts.append({
                        "id": tweet["id"],
                        "platform": "x",
                        "text": tweet.get("text", ""),
                        "author_id": tweet.get("author_id"),
                        "author_username": author.get("username"),
                        "author_followers": author.get("public_metrics", {}).get("followers_count", 0),
                        "author_verified": author.get("verified", False),
                        "created_at": tweet.get("created_at"),
                        "likes": metrics.get("like_count", 0),
                        "replies": metrics.get("reply_count", 0),
                        "retweets": metrics.get("retweet_count", 0),
                        "tickers": self._extract_cashtags(tweet.get("text", ""))
                    })
        
        return posts
    
    async def _fetch_reddit_posts(
        self,
        tickers: Optional[List[str]],
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Fetch posts from Reddit finance subreddits."""
        posts = []
        
        # Authenticate with Reddit
        await self._authenticate_reddit()
        
        if not self._reddit_access_token:
            return []
        
        headers = {
            "Authorization": f"Bearer {self._reddit_access_token}",
            "User-Agent": "TradingAI Bot v1.0"
        }
        
        async with aiohttp.ClientSession() as session:
            for subreddit in self.FINANCE_SUBREDDITS[:5]:  # Limit subreddits
                await self._respect_rate_limit()
                
                url = f"{self.REDDIT_BASE_URL}/r/{subreddit}/hot"
                params = {"limit": 50}
                
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            continue
                        
                        data = await response.json()
                        
                        for post in data.get("data", {}).get("children", []):
                            post_data = post.get("data", {})
                            
                            # Filter by time
                            created = datetime.fromtimestamp(post_data.get("created_utc", 0))
                            if created < datetime.utcnow() - timedelta(hours=hours_back):
                                continue
                            
                            text = (
                                post_data.get("title", "") + " " + 
                                post_data.get("selftext", "")
                            )
                            
                            # Extract mentioned tickers
                            mentioned = self._extract_cashtags(text)
                            if tickers:
                                # Also look for ticker symbols without $
                                for ticker in tickers:
                                    if re.search(rf'\b{ticker}\b', text, re.IGNORECASE):
                                        if ticker not in mentioned:
                                            mentioned.append(ticker)
                            
                            posts.append({
                                "id": post_data.get("id"),
                                "platform": "reddit",
                                "subreddit": subreddit,
                                "text": text[:5000],
                                "author_id": post_data.get("author"),
                                "author_username": post_data.get("author"),
                                "created_at": created.isoformat(),
                                "likes": post_data.get("ups", 0),
                                "comments": post_data.get("num_comments", 0),
                                "url": f"https://reddit.com{post_data.get('permalink', '')}",
                                "tickers": mentioned,
                                "flair": post_data.get("link_flair_text")
                            })
                            
                except Exception as e:
                    self.logger.warning(f"Failed to fetch r/{subreddit}: {e}")
        
        return posts
    
    async def _authenticate_reddit(self):
        """Get Reddit OAuth access token."""
        if self._reddit_access_token:
            return
        
        url = "https://www.reddit.com/api/v1/access_token"
        auth = aiohttp.BasicAuth(
            self.reddit_client_id,
            self.reddit_client_secret
        )
        data = {
            "grant_type": "client_credentials"
        }
        headers = {"User-Agent": "TradingAI Bot v1.0"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, auth=auth, data=data, headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self._reddit_access_token = result.get("access_token")
    
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform social posts and calculate sentiment."""
        transformed = []
        
        for post in raw_data:
            text = post.get("text", "")
            
            if not text:
                continue
            
            # Calculate engagement score
            engagement = self._calculate_engagement(post)
            
            # Basic sentiment analysis
            sentiment_score = self._analyze_sentiment(text)
            
            # Create record
            transformed.append({
                "id": f"{post['platform']}_{post['id']}",
                "platform": post["platform"],
                "text": text[:5000],
                "author_id": post.get("author_id"),
                "author_username": post.get("author_username"),
                "author_followers": post.get("author_followers", 0),
                "created_at": self._parse_datetime(post.get("created_at")),
                "tickers": post.get("tickers", []),
                "sentiment_score": sentiment_score,
                "sentiment_label": self._sentiment_label(sentiment_score),
                "engagement_score": engagement,
                "likes": post.get("likes", 0),
                "comments": post.get("comments") or post.get("replies", 0),
                "shares": post.get("retweets", 0),
                "subreddit": post.get("subreddit"),
                "url": post.get("url"),
                "flair": post.get("flair")
            })
        
        return transformed
    
    async def store(self, records: List[Dict[str, Any]]) -> int:
        """Store social posts in database."""
        if not records:
            return 0
        
        stored_count = 0
        
        async with get_session() as session:
            try:
                from sqlalchemy import text
                
                for record in records:
                    # Escape text
                    text_escaped = record["text"].replace("'", "''")
                    author = (record.get("author_username") or "").replace("'", "''")
                    tickers_str = ",".join(record.get("tickers", []))
                    
                    sql = f"""
                        INSERT INTO social_posts (
                            id, platform, text, author_id, author_username,
                            author_followers, created_at, tickers,
                            sentiment_score, sentiment_label, engagement_score,
                            likes, comments, shares, subreddit
                        )
                        VALUES (
                            '{record["id"]}', '{record["platform"]}', 
                            '{text_escaped}', '{record.get("author_id") or ""}',
                            '{author}', {record.get("author_followers", 0)},
                            '{record["created_at"]}', '{tickers_str}',
                            {record["sentiment_score"]}, '{record["sentiment_label"]}',
                            {record["engagement_score"]}, {record.get("likes", 0)},
                            {record.get("comments", 0)}, {record.get("shares", 0)},
                            '{record.get("subreddit") or ""}'
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            sentiment_score = EXCLUDED.sentiment_score,
                            engagement_score = EXCLUDED.engagement_score,
                            likes = EXCLUDED.likes,
                            comments = EXCLUDED.comments,
                            shares = EXCLUDED.shares,
                            updated_at = NOW()
                    """
                    
                    await session.execute(text(sql))
                    stored_count += 1
                
                await session.commit()
                
            except Exception as e:
                self.logger.error(f"Failed to store social posts: {e}")
                await session.rollback()
                raise
        
        return stored_count
    
    def _extract_cashtags(self, text: str) -> List[str]:
        """Extract $TICKER cashtags from text."""
        pattern = r'\$([A-Z]{1,5})\b'
        matches = re.findall(pattern, text.upper())
        return list(set(matches))
    
    def _calculate_engagement(self, post: Dict[str, Any]) -> float:
        """Calculate normalized engagement score (0-100)."""
        likes = post.get("likes", 0)
        comments = post.get("comments") or post.get("replies", 0)
        shares = post.get("retweets", 0)
        
        # Weight: shares > comments > likes
        raw_score = likes + (comments * 2) + (shares * 3)
        
        # Normalize with log scale
        import math
        normalized = min(100, math.log1p(raw_score) * 10)
        
        return round(normalized, 2)
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text (-1 to 1)."""
        text_lower = text.lower()
        
        # Bullish indicators
        bullish_words = [
            "moon", "rocket", "🚀", "buy", "calls", "bull", "long",
            "undervalued", "squeeze", "breakout", "gains", "tendies",
            "diamond hands", "💎", "hold", "hodl", "yolo", "pump"
        ]
        
        # Bearish indicators
        bearish_words = [
            "puts", "bear", "short", "sell", "crash", "dump",
            "overvalued", "bubble", "bag holder", "📉", "rip",
            "loss", "tanking", "falling", "red", "drilling"
        ]
        
        bullish_count = sum(1 for w in bullish_words if w in text_lower)
        bearish_count = sum(1 for w in bearish_words if w in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.0
        
        return (bullish_count - bearish_count) / total
    
    def _sentiment_label(self, score: float) -> str:
        """Convert score to label."""
        if score >= 0.3:
            return "BULLISH"
        elif score <= -0.3:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse datetime string."""
        if not dt_str:
            return datetime.utcnow()
        
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.utcnow()


class SentimentAggregator:
    """
    Aggregates sentiment from multiple social sources
    to produce ticker-level sentiment scores.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def aggregate_sentiment(
        self,
        ticker: str,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Aggregate sentiment for a ticker from database.
        
        Returns:
            Aggregated sentiment data
        """
        async with get_session() as session:
            from sqlalchemy import text
            
            # Get social sentiment
            social_sql = f"""
                SELECT 
                    COUNT(*) as post_count,
                    AVG(sentiment_score) as avg_sentiment,
                    SUM(engagement_score) as total_engagement,
                    AVG(engagement_score) as avg_engagement
                FROM social_posts
                WHERE tickers LIKE '%{ticker}%'
                AND created_at > NOW() - INTERVAL '{hours_back} hours'
            """
            
            result = await session.execute(text(social_sql))
            social = result.fetchone()
            
            # Get news sentiment
            news_sql = f"""
                SELECT 
                    COUNT(*) as article_count,
                    AVG(sentiment_score) as avg_sentiment
                FROM news_articles
                WHERE tickers LIKE '%{ticker}%'
                AND published_at > NOW() - INTERVAL '{hours_back} hours'
            """
            
            result = await session.execute(text(news_sql))
            news = result.fetchone()
        
        # Combine scores (news weighted higher)
        social_weight = 0.3
        news_weight = 0.7
        
        social_sent = float(social.avg_sentiment or 0)
        news_sent = float(news.avg_sentiment or 0)
        
        combined = (social_sent * social_weight) + (news_sent * news_weight)
        
        return {
            "ticker": ticker,
            "combined_sentiment": combined,
            "sentiment_label": self._label(combined),
            "social": {
                "post_count": int(social.post_count or 0),
                "avg_sentiment": social_sent,
                "total_engagement": float(social.total_engagement or 0)
            },
            "news": {
                "article_count": int(news.article_count or 0),
                "avg_sentiment": news_sent
            },
            "period_hours": hours_back,
            "calculated_at": datetime.utcnow().isoformat()
        }
    
    def _label(self, score: float) -> str:
        if score >= 0.3:
            return "BULLISH"
        elif score <= -0.3:
            return "BEARISH"
        else:
            return "NEUTRAL"


# Import logging at module level
import logging
