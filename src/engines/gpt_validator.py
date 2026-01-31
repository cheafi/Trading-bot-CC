"""
TradingAI Bot - GPT Signal Validator
Uses Azure OpenAI or OpenAI GPT for signal validation and sentiment analysis.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from src.core.config import get_settings
from src.core.models import Signal

settings = get_settings()


def get_openai_client():
    """
    Get the appropriate OpenAI client based on configuration.
    Prefers Azure OpenAI if configured, falls back to standard OpenAI.
    
    Azure OpenAI supports two auth methods:
    1. API Key (simpler, recommended for dev)
    2. Azure AD / Service Principal (for production)
    """
    if settings.use_azure_openai:
        from openai import AsyncAzureOpenAI
        
        # Check if we have an API key for Azure OpenAI
        azure_api_key = getattr(settings, 'azure_openai_api_key', None)
        
        if azure_api_key:
            # Use API key authentication (simpler)
            return AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=azure_api_key,
                api_version=settings.azure_openai_api_version,
            )
        else:
            # Use Azure AD / Service Principal authentication
            from azure.identity import ClientSecretCredential, get_bearer_token_provider
            
            credential = ClientSecretCredential(
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
                client_secret=settings.azure_client_secret
            )
            
            token_provider = get_bearer_token_provider(
                credential, 
                "https://cognitiveservices.azure.com/.default"
            )
            
            return AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=settings.azure_openai_api_version,
            )
    else:
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=settings.openai_api_key)


class GPTSignalValidator:
    """
    Uses GPT to validate trading signals by checking for news/events
    that the quantitative model might have missed.
    
    Important: GPT is NOT the source of signals - it's a sanity check layer.
    """
    
    VALIDATION_PROMPT = """You are a trading signal validator. Given a trading signal and recent news/social sentiment data, assess whether there are any red flags that should block or reduce confidence in this signal.

Signal Details:
- Ticker: {ticker}
- Direction: {direction}
- Strategy: {strategy}
- Entry Price: {entry_price}
- Take Profit: {take_profit}
- Stop Loss: {stop_loss}
- Confidence: {confidence}

Recent News Headlines:
{news_headlines}

Social Sentiment Summary:
{social_sentiment}

Respond in JSON format:
{{
    "validation_result": "PASS" | "WARN" | "FAIL",
    "confidence_adjustment": -0.3 to 0.1,  // How much to adjust signal confidence
    "reason": "Brief explanation",
    "red_flags": ["list", "of", "concerns"],
    "supporting_factors": ["list", "of", "positive", "factors"]
}}

Rules:
1. FAIL only for critical issues: pending FDA decision, earnings tomorrow, litigation risk, bankruptcy
2. WARN for moderate concerns: sector rotation, mixed analyst sentiment, unusual option activity
3. PASS when no significant concerns found
4. Never recommend trades - only validate/flag existing signals
"""

    SENTIMENT_PROMPT = """Analyze the sentiment of the following text related to stock {ticker}. 

Text:
{text}

Respond in JSON format:
{{
    "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL" | "MIXED",
    "confidence": 0.0 to 1.0,
    "key_topics": ["topic1", "topic2"],
    "summary": "One sentence summary"
}}
"""

    def __init__(
        self,
        model: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 30.0
    ):
        # Use Azure deployment name if Azure, otherwise default model
        if settings.use_azure_openai:
            self.model = settings.azure_openai_deployment or "gpt-4o-mini"
        else:
            self.model = model or "gpt-4o-mini"
        
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Initialize appropriate OpenAI client (Azure or standard)
        self.client = get_openai_client()
    
    async def validate_signal(
        self,
        signal: Signal,
        news_headlines: List[str],
        social_sentiment: str = "No social sentiment data available"
    ) -> Dict[str, Any]:
        """
        Validate a trading signal using GPT.
        
        Args:
            signal: The trading signal to validate
            news_headlines: Recent news headlines for the ticker
            social_sentiment: Summary of social media sentiment
        
        Returns:
            Validation result dict with adjusted confidence
        """
        prompt = self.VALIDATION_PROMPT.format(
            ticker=signal.ticker,
            direction=signal.direction,
            strategy=signal.strategy,
            entry_price=signal.entry_price,
            take_profit=signal.take_profit,
            stop_loss=signal.stop_loss,
            confidence=signal.confidence,
            news_headlines="\n".join(f"- {h}" for h in news_headlines[:10]),
            social_sentiment=social_sentiment
        )
        
        try:
            response = await self._call_gpt(prompt)
            result = self._parse_json_response(response)
            
            # Apply validation result
            original_confidence = signal.confidence
            adjustment = result.get('confidence_adjustment', 0)
            new_confidence = max(0, min(1, original_confidence + adjustment))
            
            return {
                'validation_result': result.get('validation_result', 'PASS'),
                'original_confidence': original_confidence,
                'adjusted_confidence': new_confidence,
                'reason': result.get('reason', ''),
                'red_flags': result.get('red_flags', []),
                'supporting_factors': result.get('supporting_factors', []),
                'validated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"GPT validation failed for {signal.ticker}: {e}")
            # On failure, return neutral result (don't block signals)
            return {
                'validation_result': 'PASS',
                'original_confidence': signal.confidence,
                'adjusted_confidence': signal.confidence,
                'reason': 'Validation service unavailable',
                'red_flags': [],
                'supporting_factors': [],
                'error': str(e),
                'validated_at': datetime.utcnow().isoformat()
            }
    
    async def analyze_sentiment(
        self,
        ticker: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text using GPT.
        
        Args:
            ticker: Stock ticker symbol
            text: Text to analyze
        
        Returns:
            Sentiment analysis result
        """
        prompt = self.SENTIMENT_PROMPT.format(ticker=ticker, text=text[:2000])
        
        try:
            response = await self._call_gpt(prompt)
            result = self._parse_json_response(response)
            
            return {
                'sentiment': result.get('sentiment', 'NEUTRAL'),
                'confidence': result.get('confidence', 0.5),
                'key_topics': result.get('key_topics', []),
                'summary': result.get('summary', ''),
                'analyzed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed for {ticker}: {e}")
            return {
                'sentiment': 'NEUTRAL',
                'confidence': 0.0,
                'key_topics': [],
                'summary': 'Analysis failed',
                'error': str(e),
                'analyzed_at': datetime.utcnow().isoformat()
            }
    
    async def validate_batch(
        self,
        signals: List[Signal],
        news_by_ticker: Dict[str, List[str]],
        sentiment_by_ticker: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple signals in parallel.
        
        Args:
            signals: List of signals to validate
            news_by_ticker: Dict mapping ticker to news headlines
            sentiment_by_ticker: Dict mapping ticker to sentiment summary
        
        Returns:
            List of validation results
        """
        tasks = []
        for signal in signals:
            news = news_by_ticker.get(signal.ticker, [])
            sentiment = sentiment_by_ticker.get(signal.ticker, "No data")
            tasks.append(self.validate_signal(signal, news, sentiment))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Validation failed: {result}")
                processed_results.append({
                    'validation_result': 'PASS',
                    'original_confidence': signals[i].confidence,
                    'adjusted_confidence': signals[i].confidence,
                    'reason': 'Validation error',
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _call_gpt(self, prompt: str) -> str:
        """Make API call to GPT with retries."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a financial analyst assistant. Always respond in valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        max_tokens=500,
                        response_format={"type": "json_object"}
                    ),
                    timeout=self.timeout
                )
                return response.choices[0].message.content
                
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                self.logger.warning(f"GPT timeout on attempt {attempt + 1}")
            except Exception as e:
                # Handle rate limits with exponential backoff
                if "rate" in str(e).lower() or "429" in str(e):
                    last_error = "Rate limit exceeded"
                    await asyncio.sleep(2 ** attempt)
                else:
                    last_error = str(e)
                    self.logger.warning(f"GPT error on attempt {attempt + 1}: {e}")
        
        raise Exception(f"GPT call failed after {self.max_retries} attempts: {last_error}")
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from GPT response."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse JSON from response: {response[:200]}")


class GPTSummarizer:
    """
    Uses GPT for market summarization and report generation.
    """
    
    MARKET_SUMMARY_PROMPT = """Summarize today's market activity based on the following data:

Market Data:
{market_data}

News Headlines:
{news_headlines}

Generate a 2-3 paragraph professional market summary covering:
1. Overall market direction and major index performance
2. Key sector movements and notable movers
3. Important themes or catalysts driving the market

Be concise, professional, and factual. Avoid speculation.
"""

    def __init__(self, model: Optional[str] = None):
        # Use Azure deployment name if Azure, otherwise default model
        if settings.use_azure_openai:
            self.model = settings.azure_openai_deployment or "gpt-4o"
        else:
            self.model = model or "gpt-4o"
        
        # Initialize appropriate OpenAI client (Azure or standard)
        self.client = get_openai_client()
        self.logger = logging.getLogger(__name__)
    
    async def generate_market_summary(
        self,
        market_data: Dict[str, Any],
        news_headlines: List[str]
    ) -> str:
        """Generate daily market summary."""
        prompt = self.MARKET_SUMMARY_PROMPT.format(
            market_data=json.dumps(market_data, indent=2),
            news_headlines="\n".join(f"- {h}" for h in news_headlines[:20])
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional financial market analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Failed to generate market summary: {e}")
            return "Market summary unavailable due to technical issues."
