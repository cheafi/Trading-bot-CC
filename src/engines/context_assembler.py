"""
Context Assembler.

Assembles the full decision context that the live engine needs:
market state, portfolio state, news, sentiment, calendar events,
and corporate actions — all in one async call.

Sprint 25: _get_market_state now fetches **real** VIX, SPY return,
and market breadth via yfinance instead of returning hardcoded
defaults.  Falls back gracefully to defaults on any fetch failure.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
        self._cache: Dict[str, Any] = {}
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

        results: Dict[str, Any] = {}
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

        # Cross-asset analysis (wired to live data)
        try:
            from src.engines.cross_asset_monitor import CrossAssetMonitor

            ms = results.get("market_state", {})
            ca_data = await self._fetch_cross_asset_data(ms)
            cam = CrossAssetMonitor()
            report = cam.analyse(**ca_data)
            results["cross_asset"] = report.to_dict()
        except Exception as e:
            logger.debug("Cross-asset analysis skipped: %s", e)
            results["cross_asset"] = {}

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
                        asyncio.run, self.assemble(tickers),
                    )
                    return future.result(timeout=30)
            return loop.run_until_complete(
                self.assemble(tickers),
            )
        except RuntimeError:
            return asyncio.run(self.assemble(tickers))

    # ------------------------------------------------------------------
    # Sprint 25: real market-state data via yfinance
    # ------------------------------------------------------------------

    async def _get_market_state(self) -> Dict[str, Any]:
        """Fetch VIX, SPY 20-day return, breadth, etc.

        Priority order:
          1. Injected ``market_data_service`` (if it has the methods)
          2. yfinance direct fetch (Sprint 25)
          3. Hardcoded safe defaults (last resort)
        """
        cache_key = "market_state"
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        # Safe defaults — used only when *everything* fails
        state: Dict[str, Any] = {
            "vix": 18.0,
            "spy_return_20d": 0.0,
            "breadth_pct": 0.50,
            "hy_spread": 0.0,
            "realized_vol_20d": 0.15,
            "vix_term_slope": 0.0,
            "data_source": "defaults",
        }

        # --- Try injected market_data_service first ---
        if self.market_data:
            try:
                md = self.market_data
                if hasattr(md, "get_vix"):
                    vix_val = await self._maybe_await(md.get_vix())
                    if vix_val:
                        state["vix"] = float(vix_val)
                        state["data_source"] = "market_data_service"

                if hasattr(md, "get_spy_return"):
                    spy_ret = await self._maybe_await(md.get_spy_return(20))
                    if spy_ret is not None:
                        state["spy_return_20d"] = float(spy_ret)

                if hasattr(md, "get_market_breadth"):
                    breadth = await self._maybe_await(md.get_market_breadth())
                    if breadth is not None:
                        state["breadth_pct"] = float(breadth)

            except Exception as e:
                logger.warning("Market data service error: %s", e)

        # --- Fallback: yfinance (Sprint 25) ---
        if state["data_source"] == "defaults":
            yf_state = await self._fetch_market_state_yfinance()
            if yf_state:
                state.update(yf_state)
                state["data_source"] = "yfinance"

        self._set_cache(cache_key, state)
        return state

    async def _fetch_market_state_yfinance(self) -> Optional[Dict[str, Any]]:
        """Fetch VIX, SPY return, and breadth proxy via yfinance.

        Runs the blocking yfinance calls in a thread-pool so we
        don't block the async event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._yfinance_market_state_sync,
            )
        except Exception as e:
            logger.warning("yfinance market-state fetch failed: %s", e)
            return None

    @staticmethod
    def _yfinance_market_state_sync() -> Optional[Dict[str, Any]]:
        """Synchronous helper — called inside an executor.

        Fetches:
          - ^VIX last close → ``vix``
          - SPY 25-day history → 20-day return + realized vol
          - Breadth proxy via sector ETF performance (% of 9
            Select Sector SPDRs above their 50-day SMA)
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.debug("yfinance not installed — skipping live market state")
            return None

        result: Dict[str, Any] = {}

        # ── VIX ──────────────────────────────────────────────
        try:
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")
            if len(vix_hist) > 0:
                result["vix"] = round(float(vix_hist["Close"].iloc[-1]), 2)
        except Exception as e:
            logger.debug("VIX fetch error: %s", e)

        # ── SPY return + realized vol ────────────────────────
        try:
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period="30d")
            if len(spy_hist) >= 20:
                closes = spy_hist["Close"]
                # 20-day return (%)
                ret_20d = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
                result["spy_return_20d"] = round(float(ret_20d), 2)

                # 20-day realized volatility (annualised)
                daily_returns = closes.pct_change().dropna().tail(20)
                if len(daily_returns) >= 10:
                    import math
                    rvol = float(daily_returns.std() * math.sqrt(252))
                    result["realized_vol_20d"] = round(rvol, 4)
        except Exception as e:
            logger.debug("SPY fetch error: %s", e)

        # ── Market breadth proxy ─────────────────────────────
        # % of 9 Select Sector SPDRs whose last close > 50-day SMA
        try:
            sectors = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLU", "XLB"]
            above = 0
            checked = 0
            data = yf.download(sectors, period="60d", progress=False, group_by="ticker", threads=True)
            for etf in sectors:
                try:
                    if len(sectors) > 1:
                        df = data[etf]
                    else:
                        df = data
                    closes = df["Close"].dropna()
                    if len(closes) >= 50:
                        sma50 = closes.rolling(50).mean().iloc[-1]
                        if closes.iloc[-1] > sma50:
                            above += 1
                        checked += 1
                except (KeyError, IndexError):
                    continue
            if checked > 0:
                result["breadth_pct"] = round(above / checked, 2)
        except Exception as e:
            logger.debug("Breadth fetch error: %s", e)

        return result if result else None

    async def _get_portfolio_state(self) -> Dict[str, Any]:
        """Fetch current portfolio from broker.

        Returns canonical portfolio schema with both list and dict
        forms so downstream consumers (RiskModel, ensembler) work.
        """
        state: Dict[str, Any] = {
            "positions": [],
            "positions_by_ticker": {},
            "tickers": [],
            "sectors": {},
            "equity": 0.0,
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
                    self.broker.get_positions(),
                )
                if positions:
                    state["positions"] = positions
                    by_ticker: Dict[str, Any] = {}
                    tickers_list: List[str] = []
                    for p in positions:
                        tk = getattr(
                            p, "ticker",
                            getattr(p, "symbol", ""),
                        )
                        if not tk:
                            tk = p.get("ticker", p.get("symbol", ""))
                        tickers_list.append(tk)
                        by_ticker[tk] = p
                    state["positions_by_ticker"] = by_ticker
                    state["tickers"] = tickers_list

            if hasattr(self.broker, "get_account"):
                account = await self._maybe_await(
                    self.broker.get_account(),
                )
                if account:
                    val = getattr(
                        account, "portfolio_value",
                        account.get("portfolio_value", 0)
                        if isinstance(account, dict) else 0,
                    )
                    cash = getattr(
                        account, "cash",
                        account.get("cash", 0)
                        if isinstance(account, dict) else 0,
                    )
                    state["total_value"] = val
                    state["equity"] = val
                    state["cash"] = cash

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
                        self.market_data.get_news(ticker),
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

    async def _fetch_cross_asset_data(
        self,
        market_state: Dict[str, Any],
    ) -> Dict[str, float]:
        """Fetch daily changes for cross-asset tickers."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._cross_asset_sync,
        )
        # Merge with existing market state
        data["vix"] = market_state.get("vix", 20.0)
        data["breadth_pct"] = (
            market_state.get(
                "breadth_pct",
                50.0,
            )
            * 100
        )  # CrossAssetMonitor expects 0-100
        return data

    @staticmethod
    def _cross_asset_sync() -> Dict[str, float]:
        """Fetch daily changes for SPY, QQQ, IWM, TLT, GLD, DX-Y.NYB."""
        result: Dict[str, float] = {
            "spy_change_pct": 0.0,
            "qqq_change_pct": 0.0,
            "iwm_change_pct": 0.0,
            "tlt_change_pct": 0.0,
            "gld_change_pct": 0.0,
            "dxy_change_pct": 0.0,
        }
        try:
            import yfinance as yf
        except ImportError:
            return result

        mapping = {
            "SPY": "spy_change_pct",
            "QQQ": "qqq_change_pct",
            "IWM": "iwm_change_pct",
            "TLT": "tlt_change_pct",
            "GLD": "gld_change_pct",
            "DX-Y.NYB": "dxy_change_pct",
        }

        try:
            tickers = list(mapping.keys())
            data = yf.download(
                tickers,
                period="5d",
                progress=False,
                group_by="ticker",
                threads=True,
            )
            for sym, key in mapping.items():
                try:
                    df = data[sym] if len(tickers) > 1 else data
                    closes = df["Close"].dropna()
                    if len(closes) >= 2:
                        chg = float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100)
                        result[key] = round(chg, 2)
                except (KeyError, IndexError):
                    pass
        except Exception as e:
            logger.debug("Cross-asset fetch error: %s", e)

        return result
