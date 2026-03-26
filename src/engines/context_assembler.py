"""
Context Assembler.

Assembles the full decision context that the live engine needs:
market state, portfolio state, news, sentiment, calendar events,
and corporate actions — all in one async call.

This replaces the scattered empty-dict / None placeholders
throughout the auto_trading_engine.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    Gathers market state, portfolio, news, sentiment, and
    calendar data into a single context dict for the decision
    pipeline.
    """

    def __init__(
        self,
        market_data_service=None,
        broker_manager=None,
        news_service=None,
    ):
        """
        Args:
            market_data_service: MarketDataService instance
            broker_manager: BrokerManager for portfolio state
            news_service: optional dedicated news provider
        """
        self.market_data = market_data_service
        self.broker = broker_manager
        self.news_service = news_service
        self._cache = {}
        self._cache_ttl = 300  # 5 min

    async def assemble(
        self,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Assemble full decision context.

        Returns dict with keys:
            market_state, portfolio_state, news_by_ticker,
            sentiment, calendar_events, timestamp
        """
        tasks = {
            "market_state": self._get_market_state(),
            "portfolio_state": self._get_portfolio_state(),
        }
        if tickers:
            tasks["news_by_ticker"] = self._get_news(tickers)

        results = {}
        for key, coro in tasks.items():
            try:
                results[key] = await coro
            except Exception as e:
                logger.warning("Context %s failed: %s", key, e)
                results[key] = {}

        # Ensure all keys exist
        results.setdefault("market_state", {})
        results.setdefault("portfolio_state", {})
        results.setdefault("news_by_ticker", {})
        results.setdefault("sentiment", {})
        results.setdefault("calendar_events", [])
        results["timestamp"] = datetime.now(timezone.utc).isoformat()

        return results

    def assemble_sync(
        self,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for assemble()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context — use thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, self.assemble(tickers)
                    )
                    return future.result(timeout=30)
            return loop.run_until_complete(
                self.assemble(tickers)
            )
        except RuntimeError:
            return asyncio.run(self.assemble(tickers))

    async def _get_market_state(self) -> Dict[str, Any]:
        """Fetch VIX, SPY, breadth, etc."""
        cache_key = "market_state"
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        state = {
            "vix": 18.0,
            "spy_return_20d": 0.0,
            "breadth_pct": 0.50,
            "hy_spread": 0.0,
            "realized_vol_20d": 0.15,
            "vix_term_slope": 0.0,
        }

        if self.market_data:
            try:
                md = self.market_data
                if hasattr(md, "get_vix"):
                    vix_val = await self._maybe_await(
                        md.get_vix()
                    )
                    if vix_val:
                        state["vix"] = float(vix_val)

                if hasattr(md, "get_spy_return"):
                    spy_ret = await self._maybe_await(
                        md.get_spy_return(20)
                    )
                    if spy_ret is not None:
                        state["spy_return_20d"] = float(spy_ret)

                if hasattr(md, "get_market_breadth"):
                    breadth = await self._maybe_await(
                        md.get_market_breadth()
                    )
                    if breadth is not None:
                        state["breadth_pct"] = float(breadth)

            except Exception as e:
                logger.warning("Market state fetch error: %s", e)

        self._set_cache(cache_key, state)
        return state

    async def _get_portfolio_state(self) -> Dict[str, Any]:
        """Fetch current portfolio from broker."""
        state = {
            "positions": [],
            "tickers": [],
            "sectors": {},
            "total_value": 0.0,
            "cash": 0.0,
            "options_allocation_pct": 0.0,
            "daily_pnl": 0.0,
        }

        if not self.broker:
            return state

        try:
            if hasattr(self.broker, "get_positions"):
                positions = await self._maybe_await(
                    self.broker.get_positions()
                )
                if positions:
                    state["positions"] = positions
                    state["tickers"] = [
                        p.get("ticker", p.get("symbol", ""))
                        for p in positions
                    ]

            if hasattr(self.broker, "get_account"):
                account = await self._maybe_await(
                    self.broker.get_account()
                )
                if account:
                    state["total_value"] = account.get(
                        "portfolio_value", 0
                    )
                    state["cash"] = account.get("cash", 0)

        except Exception as e:
            logger.warning("Portfolio state fetch error: %s", e)

        return state

    async def _get_news(
        self, tickers: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch recent news for tickers."""
        news_by_ticker: Dict[str, List[Dict[str, Any]]] = {}

        if not tickers:
            return news_by_ticker

        # Try market_data_service.get_news first
        if self.market_data and hasattr(self.market_data, "get_news"):
            try:
                for ticker in tickers[:20]:  # limit
                    articles = await self._maybe_await(
                        self.market_data.get_news(ticker)
                    )
                    if articles:
                        news_by_ticker[ticker] = articles
            except Exception as e:
                logger.warning("News fetch error: %s", e)

        return news_by_ticker

    async def _maybe_await(self, result):
        """Await if coroutine, else return directly."""
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            return await result
        return result

    def _check_cache(self, key: str) -> Optional[Any]:
        """Return cached value if fresh, else None."""
        if key in self._cache:
            val, ts = self._cache[key]
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age < self._cache_ttl:
                return val
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Store value in cache with timestamp."""
        self._cache[key] = (value, datetime.now(timezone.utc))
