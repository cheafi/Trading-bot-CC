"""
AI-Powered News Analyzer

Scans and summarizes financial news into actionable trading briefs.
Uses GPT to extract sentiment, key events, and trading implications.
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class NewsCategory(str, Enum):
    """News categories for classification."""
    EARNINGS = "earnings"
    ANALYST = "analyst"
    MACRO = "macro"
    SECTOR = "sector"
    COMPANY = "company"
    FDA = "fda"
    MERGER = "merger"
    LEGAL = "legal"
    INSIDER = "insider"
    PRODUCT = "product"
    MANAGEMENT = "management"
    GUIDANCE = "guidance"


class NewsSentiment(str, Enum):
    """News sentiment classification."""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class NewsItem:
    """Individual news item."""
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    
    # Extracted data
    tickers: List[str] = field(default_factory=list)
    category: NewsCategory = NewsCategory.COMPANY
    sentiment: NewsSentiment = NewsSentiment.NEUTRAL
    sentiment_score: float = 0.0  # -1 to 1
    
    # AI analysis
    ai_summary: str = ""
    key_points: List[str] = field(default_factory=list)
    trading_implications: str = ""
    price_impact_estimate: str = ""  # "high", "medium", "low"
    time_sensitivity: str = "normal"  # "urgent", "important", "normal"
    
    # Metadata
    relevance_score: float = 0.0
    credibility_score: float = 0.0


@dataclass
class NewsBrief:
    """Condensed news brief for quick consumption."""
    generated_at: datetime
    period: str  # "morning", "midday", "closing", "overnight"
    
    # Summary
    headline: str
    market_mood: str  # "risk_on", "risk_off", "mixed"
    
    # Categorized news
    top_stories: List[NewsItem] = field(default_factory=list)
    earnings_news: List[NewsItem] = field(default_factory=list)
    analyst_actions: List[NewsItem] = field(default_factory=list)
    macro_events: List[NewsItem] = field(default_factory=list)
    sector_news: Dict[str, List[NewsItem]] = field(default_factory=dict)
    
    # Actionable insights
    bullish_catalysts: List[str] = field(default_factory=list)
    bearish_catalysts: List[str] = field(default_factory=list)
    stocks_to_watch: List[str] = field(default_factory=list)
    
    # AI-generated summary
    executive_summary: str = ""
    trading_focus: str = ""


class NewsAnalyzer:
    """
    AI-powered news analysis and summarization.
    
    Features:
    - Real-time news monitoring
    - Sentiment analysis
    - Event extraction
    - Actionable brief generation
    """
    
    # Keywords for category classification
    CATEGORY_KEYWORDS = {
        NewsCategory.EARNINGS: [
            'earnings', 'eps', 'revenue', 'quarterly', 'q1', 'q2', 'q3', 'q4',
            'profit', 'loss', 'beat', 'miss', 'guidance', 'outlook'
        ],
        NewsCategory.ANALYST: [
            'upgrade', 'downgrade', 'price target', 'rating', 'analyst',
            'buy', 'sell', 'hold', 'outperform', 'underperform'
        ],
        NewsCategory.MACRO: [
            'fed', 'inflation', 'gdp', 'employment', 'jobs', 'rates',
            'treasury', 'fomc', 'powell', 'cpi', 'ppi', 'interest rate'
        ],
        NewsCategory.FDA: [
            'fda', 'approval', 'clinical', 'trial', 'drug', 'phase',
            'biotech', 'pharmaceutical'
        ],
        NewsCategory.MERGER: [
            'merger', 'acquisition', 'buyout', 'takeover', 'deal',
            'combine', 'purchase'
        ],
        NewsCategory.INSIDER: [
            'insider', 'ceo buy', 'director', 'form 4', 'stock purchase',
            'executive buy', 'insider buying'
        ],
        NewsCategory.MANAGEMENT: [
            'ceo', 'cfo', 'resignation', 'appointment', 'steps down',
            'new leadership', 'management change'
        ]
    }
    
    # Sentiment keywords
    BULLISH_KEYWORDS = [
        'surge', 'soar', 'jump', 'rally', 'beat', 'exceed', 'record',
        'growth', 'upgrade', 'buy', 'breakthrough', 'expansion', 'accelerate',
        'outperform', 'strong', 'bullish', 'optimistic', 'upside'
    ]
    
    BEARISH_KEYWORDS = [
        'plunge', 'crash', 'tumble', 'fall', 'miss', 'disappoint', 'decline',
        'downgrade', 'sell', 'cut', 'layoff', 'warning', 'concern', 'risk',
        'bearish', 'weak', 'downside', 'underperform', 'recession'
    ]
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.openai_client = None
        self._init_openai()
        
    def _init_openai(self):
        """Initialize OpenAI client if available."""
        try:
            from openai import AsyncOpenAI
            import os
            
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.openai_client = AsyncOpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"OpenAI not available: {e}")
    
    async def analyze_news_batch(
        self,
        news_items: List[Dict]
    ) -> List[NewsItem]:
        """
        Analyze a batch of news items.
        
        Args:
            news_items: List of raw news dicts with title, summary, source, url, published_at
            
        Returns:
            List of analyzed NewsItem objects
        """
        analyzed = []
        
        for item in news_items:
            try:
                news = await self._analyze_single(item)
                analyzed.append(news)
            except Exception as e:
                logger.error(f"Error analyzing news: {e}")
                continue
        
        # Sort by relevance
        analyzed.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return analyzed
    
    async def _analyze_single(self, raw: Dict) -> NewsItem:
        """Analyze a single news item."""
        title = raw.get('title', '')
        summary = raw.get('summary', raw.get('description', ''))
        content = f"{title} {summary}".lower()
        
        # Extract tickers
        tickers = self._extract_tickers(title + ' ' + summary)
        
        # Classify category
        category = self._classify_category(content)
        
        # Analyze sentiment
        sentiment, sentiment_score = self._analyze_sentiment(content)
        
        # Calculate relevance
        relevance = self._calculate_relevance(raw, tickers, category)
        
        news = NewsItem(
            id=raw.get('id', str(hash(title))),
            title=title,
            summary=summary,
            source=raw.get('source', 'Unknown'),
            url=raw.get('url', ''),
            published_at=raw.get('published_at', datetime.now()),
            tickers=tickers,
            category=category,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            relevance_score=relevance,
            credibility_score=self._get_source_credibility(raw.get('source', ''))
        )
        
        # AI enhancement if available
        if self.openai_client:
            try:
                await self._enhance_with_ai(news)
            except Exception as e:
                logger.warning(f"AI enhancement failed: {e}")
        
        return news
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from text."""
        # Pattern for stock tickers: $AAPL or (AAPL) or AAPL:
        patterns = [
            r'\$([A-Z]{1,5})\b',  # $AAPL
            r'\(([A-Z]{1,5})\)',  # (AAPL)
            r'\b([A-Z]{1,5}):\s',  # AAPL:
        ]
        
        tickers = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            tickers.update(matches)
        
        # Filter common false positives
        false_positives = {'CEO', 'CFO', 'IPO', 'FDA', 'SEC', 'ETF', 'GDP', 'CPI', 'EPS', 'P/E', 'AI', 'US', 'UK', 'EU'}
        tickers = [t for t in tickers if t not in false_positives]
        
        return list(tickers)[:10]  # Limit to 10 tickers
    
    def _classify_category(self, content: str) -> NewsCategory:
        """Classify news into category."""
        content = content.lower()
        
        category_scores = {}
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                category_scores[cat] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return NewsCategory.COMPANY
    
    def _analyze_sentiment(self, content: str) -> tuple:
        """Analyze sentiment of news content."""
        content = content.lower()
        
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in content)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in content)
        
        total = bullish_count + bearish_count
        if total == 0:
            return NewsSentiment.NEUTRAL, 0.0
        
        score = (bullish_count - bearish_count) / total
        
        if score > 0.5:
            return NewsSentiment.VERY_BULLISH, score
        elif score > 0.2:
            return NewsSentiment.BULLISH, score
        elif score < -0.5:
            return NewsSentiment.VERY_BEARISH, score
        elif score < -0.2:
            return NewsSentiment.BEARISH, score
        else:
            return NewsSentiment.NEUTRAL, score
    
    def _calculate_relevance(
        self,
        raw: Dict,
        tickers: List[str],
        category: NewsCategory
    ) -> float:
        """Calculate relevance score for news item."""
        score = 50
        
        # Ticker presence
        if tickers:
            score += min(20, len(tickers) * 5)
        
        # Category importance
        important_categories = [
            NewsCategory.EARNINGS,
            NewsCategory.FDA,
            NewsCategory.MERGER,
            NewsCategory.ANALYST
        ]
        if category in important_categories:
            score += 15
        
        # Source credibility
        score += self._get_source_credibility(raw.get('source', '')) / 5
        
        # Recency
        pub_time = raw.get('published_at', datetime.now())
        if isinstance(pub_time, datetime):
            hours_old = (datetime.now() - pub_time).total_seconds() / 3600
            if hours_old < 1:
                score += 10
            elif hours_old < 4:
                score += 5
        
        return min(100, score)
    
    def _get_source_credibility(self, source: str) -> float:
        """Get credibility score for news source."""
        source = source.lower()
        
        high_credibility = ['bloomberg', 'reuters', 'wsj', 'wall street journal', 
                          'financial times', 'cnbc', 'sec', 'company pr']
        medium_credibility = ['yahoo finance', 'marketwatch', 'barrons', 
                            'investor business daily', 'seeking alpha']
        
        if any(s in source for s in high_credibility):
            return 90
        elif any(s in source for s in medium_credibility):
            return 70
        else:
            return 50
    
    async def _enhance_with_ai(self, news: NewsItem):
        """Enhance news analysis with AI."""
        if not self.openai_client:
            return
            
        prompt = f"""Analyze this financial news and provide:
1. A one-sentence trading summary
2. Key points (2-3 bullet points)
3. Trading implications
4. Expected price impact (high/medium/low)

Title: {news.title}
Summary: {news.summary}
Category: {news.category.value}
Tickers: {', '.join(news.tickers) if news.tickers else 'None specified'}

Respond in JSON format:
{{
    "ai_summary": "...",
    "key_points": ["...", "..."],
    "trading_implications": "...",
    "price_impact": "high|medium|low"
}}"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-5.2-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            news.ai_summary = result.get('ai_summary', '')
            news.key_points = result.get('key_points', [])
            news.trading_implications = result.get('trading_implications', '')
            news.price_impact_estimate = result.get('price_impact', 'medium')
            
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
    
    async def generate_brief(
        self,
        news_items: List[NewsItem],
        period: str = "morning"
    ) -> NewsBrief:
        """
        Generate condensed news brief.
        
        Args:
            news_items: List of analyzed news items
            period: Time period (morning, midday, closing, overnight)
            
        Returns:
            NewsBrief with summarized and categorized news
        """
        brief = NewsBrief(
            generated_at=datetime.now(),
            period=period,
            headline="",
            market_mood="mixed"
        )
        
        if not news_items:
            brief.headline = "No significant news today"
            return brief
        
        # Sort by relevance
        sorted_news = sorted(news_items, key=lambda x: x.relevance_score, reverse=True)
        
        # Top stories
        brief.top_stories = sorted_news[:5]
        
        # Categorize
        brief.earnings_news = [n for n in news_items if n.category == NewsCategory.EARNINGS][:5]
        brief.analyst_actions = [n for n in news_items if n.category == NewsCategory.ANALYST][:5]
        brief.macro_events = [n for n in news_items if n.category == NewsCategory.MACRO][:5]
        
        # Extract catalysts
        bullish_items = [n for n in news_items if n.sentiment in [NewsSentiment.BULLISH, NewsSentiment.VERY_BULLISH]]
        bearish_items = [n for n in news_items if n.sentiment in [NewsSentiment.BEARISH, NewsSentiment.VERY_BEARISH]]
        
        brief.bullish_catalysts = [n.title[:100] for n in bullish_items[:5]]
        brief.bearish_catalysts = [n.title[:100] for n in bearish_items[:5]]
        
        # Stocks to watch
        all_tickers = []
        for n in sorted_news[:10]:
            all_tickers.extend(n.tickers)
        brief.stocks_to_watch = list(set(all_tickers))[:10]
        
        # Determine market mood
        bullish_ratio = len(bullish_items) / len(news_items) if news_items else 0.5
        if bullish_ratio > 0.6:
            brief.market_mood = "risk_on"
        elif bullish_ratio < 0.4:
            brief.market_mood = "risk_off"
        else:
            brief.market_mood = "mixed"
        
        # Generate headline
        if brief.top_stories:
            brief.headline = brief.top_stories[0].title
        
        # AI summary
        if self.openai_client:
            await self._generate_ai_summary(brief, news_items)
        else:
            brief.executive_summary = self._generate_basic_summary(brief, news_items)
        
        return brief
    
    async def _generate_ai_summary(
        self,
        brief: NewsBrief,
        news_items: List[NewsItem]
    ):
        """Generate AI-powered executive summary."""
        if not self.openai_client:
            return
            
        headlines = "\n".join([f"- {n.title}" for n in news_items[:10]])
        
        prompt = f"""Generate a brief market intelligence summary for traders.

Period: {brief.period}
Market Mood: {brief.market_mood}

Top Headlines:
{headlines}

Provide:
1. Executive Summary (2-3 sentences)
2. Trading Focus (what to watch today)

Keep it concise and actionable."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-5.2-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.5
            )
            
            content = response.choices[0].message.content
            
            # Parse response
            if "Executive Summary:" in content:
                parts = content.split("Trading Focus:")
                brief.executive_summary = parts[0].replace("Executive Summary:", "").strip()
                if len(parts) > 1:
                    brief.trading_focus = parts[1].strip()
            else:
                brief.executive_summary = content
                
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            brief.executive_summary = self._generate_basic_summary(brief, news_items)
    
    def _generate_basic_summary(
        self,
        brief: NewsBrief,
        news_items: List[NewsItem]
    ) -> str:
        """Generate basic summary without AI."""
        lines = []
        
        lines.append(f"📰 **{brief.period.title()} Brief** - {brief.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"**Market Mood:** {brief.market_mood.replace('_', ' ').title()}")
        lines.append("")
        
        if brief.top_stories:
            lines.append("**Top Stories:**")
            for story in brief.top_stories[:3]:
                emoji = "🟢" if story.sentiment_score > 0 else "🔴" if story.sentiment_score < 0 else "⚪"
                lines.append(f"  {emoji} {story.title[:80]}")
        
        if brief.stocks_to_watch:
            lines.append("")
            lines.append(f"**Watch:** {', '.join(brief.stocks_to_watch[:5])}")
        
        return "\n".join(lines)
    
    def format_brief_telegram(self, brief: NewsBrief) -> str:
        """Format brief for Telegram."""
        lines = []
        
        mood_emoji = {"risk_on": "🟢", "risk_off": "🔴", "mixed": "🟡"}.get(brief.market_mood, "⚪")
        
        lines.append(f"📰 **{brief.period.upper()} BRIEF** {mood_emoji}")
        lines.append(f"_{brief.generated_at.strftime('%Y-%m-%d %H:%M')}_")
        lines.append("")
        
        if brief.executive_summary:
            lines.append(brief.executive_summary)
            lines.append("")
        
        if brief.top_stories:
            lines.append("**🔥 Top Stories:**")
            for i, story in enumerate(brief.top_stories[:3], 1):
                sentiment = "📈" if story.sentiment_score > 0 else "📉" if story.sentiment_score < 0 else "➡️"
                tickers = f"({', '.join(story.tickers[:3])})" if story.tickers else ""
                lines.append(f"{i}. {sentiment} {story.title[:60]}... {tickers}")
        
        if brief.bullish_catalysts:
            lines.append("")
            lines.append("**✅ Bullish:**")
            for cat in brief.bullish_catalysts[:2]:
                lines.append(f"  • {cat[:50]}...")
        
        if brief.bearish_catalysts:
            lines.append("")
            lines.append("**⚠️ Bearish:**")
            for cat in brief.bearish_catalysts[:2]:
                lines.append(f"  • {cat[:50]}...")
        
        if brief.stocks_to_watch:
            lines.append("")
            lines.append(f"**👀 Watch:** `{' '.join(brief.stocks_to_watch[:8])}`")
        
        if brief.trading_focus:
            lines.append("")
            lines.append(f"**🎯 Focus:** {brief.trading_focus}")
        
        return "\n".join(lines)
