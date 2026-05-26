"""
Catalyst Summarizer
====================

Aggregates recent news headlines and market events into
structured catalyst narratives for portfolio brief surfaces.

Uses MarketDataService for news fetches and provides:
  - per-ticker headline clusters
  - sector-level summary
  - ``follow_up_questions`` for drill-down UX
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CatalystSummarizer:
    """Build catalyst narrative from MarketDataService news."""

    def __init__(self, market_data_service: Any):
        self._mds = market_data_service

    async def summarize(
        self,
        tickers: List[str],
        *,
        max_items_per_ticker: int = 5,
    ) -> Dict[str, Any]:
        """Fetch news for tickers, cluster by theme, produce narrative.

        Returns
        -------
        dict
            ``catalysts``: list of catalyst items
            ``sector_summary``: string narrative
            ``follow_up_questions``: list of strings
        """
        import asyncio

        catalysts: List[Dict[str, Any]] = []
        all_headlines: List[str] = []

        # Fetch news concurrently
        results = await asyncio.gather(
            *[self._mds.get_news(t, max_items=max_items_per_ticker)
              for t in tickers],
            return_exceptions=True,
        )

        ts_now = datetime.now(timezone.utc).timestamp()

        for ticker, news_result in zip(tickers, results):
            if isinstance(news_result, Exception) or not news_result:
                continue
            for item in news_result[:max_items_per_ticker]:
                title = item.get("title", "")
                url = item.get("link", item.get("url", ""))
                publisher = item.get("publisher", "Unknown")
                pub_time = item.get("providerPublishTime", 0)
                age_h = (ts_now - pub_time) / 3600 if pub_time else None

                if not title:
                    continue

                catalysts.append({
                    "ticker": ticker,
                    "headline": title[:200],
                    "publisher": publisher,
                    "url": url,
                    "age_hours": round(age_h, 1) if age_h else None,
                    "sentiment": self._quick_sentiment(title),
                })
                all_headlines.append(f"[{ticker}] {title}")

        # Sector summary — simple aggregation
        sector_summary = self._build_sector_summary(catalysts, tickers)

        # Follow-up questions
        follow_ups = self._generate_follow_ups(catalysts, tickers)

        return {
            "catalysts": catalysts[:20],
            "sector_summary": sector_summary,
            "follow_up_questions": follow_ups,
            "source": "market_data_service",
            "ticker_count": len(tickers),
            "headline_count": len(catalysts),
        }

    @staticmethod
    def _quick_sentiment(headline: str) -> str:
        """Ultra-simple keyword sentiment for headlines."""
        h = headline.lower()
        bullish = [
            "surge", "rally", "beat", "upgrade", "record",
            "boost", "gain", "soar", "breakout", "bullish",
            "growth", "profit", "positive",
        ]
        bearish = [
            "crash", "plunge", "miss", "downgrade", "warning",
            "drop", "loss", "fear", "risk", "bearish",
            "decline", "cut", "negative", "layoff",
        ]
        b_score = sum(1 for w in bullish if w in h)
        s_score = sum(1 for w in bearish if w in h)
        if b_score > s_score:
            return "bullish"
        if s_score > b_score:
            return "bearish"
        return "neutral"

    @staticmethod
    def _build_sector_summary(
        catalysts: List[Dict], tickers: List[str],
    ) -> str:
        """Build a one-paragraph sector summary from catalysts."""
        if not catalysts:
            return "No recent catalysts detected for the watchlist."

        # Group by sentiment
        sentiments = {"bullish": 0, "bearish": 0, "neutral": 0}
        for c in catalysts:
            sentiments[c.get("sentiment", "neutral")] += 1

        total = sum(sentiments.values())
        dominant = max(sentiments, key=sentiments.get)  # type: ignore[arg-type]

        parts = []
        parts.append(
            f"Across {len(tickers)} tickers, {total} recent headlines detected.",
        )
        if sentiments["bullish"] > 0:
            parts.append(
                f"{sentiments['bullish']} bullish",
            )
        if sentiments["bearish"] > 0:
            parts.append(
                f"{sentiments['bearish']} bearish",
            )
        if sentiments["neutral"] > 0:
            parts.append(
                f"{sentiments['neutral']} neutral",
            )

        tone = {
            "bullish": "Tone skews positive — upgrades and beats dominate.",
            "bearish": "Tone skews cautious — downgrades and risk headlines dominate.",
            "neutral": "Tone is mixed — no dominant narrative.",
        }
        parts.append(tone[dominant])

        return " ".join(parts)

    @staticmethod
    def _generate_follow_ups(
        catalysts: List[Dict], tickers: List[str],
    ) -> List[str]:
        """Generate follow-up questions for the brief UI."""
        questions: List[str] = []

        # Ticker-specific drill-downs
        tickers_with_news = {c["ticker"] for c in catalysts}
        for t in list(tickers_with_news)[:3]:
            questions.append(f"What are the key catalysts for {t} this week?")

        # Sentiment questions
        bearish_tickers = {
            c["ticker"] for c in catalysts
            if c.get("sentiment") == "bearish"
        }
        if bearish_tickers:
            bt = ", ".join(list(bearish_tickers)[:3])
            questions.append(f"Should I reduce exposure to {bt}?")

        # General
        questions.append(
            "How does sector rotation affect my portfolio this week?",
        )
        questions.append(
            "What earnings dates should I watch in the next 5 days?",
        )

        return questions[:5]
