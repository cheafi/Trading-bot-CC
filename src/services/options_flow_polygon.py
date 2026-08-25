"""Polygon.io options-flow provider — chain snapshot normalization."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from src.services.options_flow_provider import (
    OptionsFlowEvent,
    OptionsFlowProvider,
    OptionsFlowTrust,
    OptionsProviderStatus,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.polygon.io"
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")

# Bounded scan universe when caller does not pass tickers
_DEFAULT_UNIVERSE = [
    "NVDA",
    "AAPL",
    "MSFT",
    "META",
    "AMD",
    "TSLA",
    "PLTR",
    "SOFI",
    "SOUN",
    "CRWD",
    "PANW",
    "AVGO",
]

_MAX_UNDERLYINGS_PER_SCAN = 10
_CHAIN_LIMIT = 80
_MIN_CONTRACT_VOLUME = 50
_MIN_DAY_PREMIUM = 25_000


class PolygonOptionsFlowProvider(OptionsFlowProvider):
    """Polygon options chain snapshot → normalized flow events."""

    name = "polygon"

    def __init__(self, api_key: Optional[str] = None, realtime: bool = False):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY", "")
        self.realtime = realtime
        self._last_update: Optional[str] = None
        self._last_error: Optional[str] = None

    async def fetch_recent_events(
        self,
        universe: Optional[List[str]] = None,
        *,
        limit: int = 500,
    ) -> List[OptionsFlowEvent]:
        if not self.api_key:
            return []

        tickers = self._sanitize_universe(universe)[:_MAX_UNDERLYINGS_PER_SCAN]
        events: List[OptionsFlowEvent] = []
        timeout = aiohttp.ClientTimeout(total=20)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = [
                    self._fetch_underlying_chain(session, ticker)
                    for ticker in tickers
                ]
                chunks = await asyncio.gather(*tasks, return_exceptions=True)
                for chunk in chunks:
                    if isinstance(chunk, Exception):
                        logger.debug("polygon chain fetch error: %s", chunk)
                        continue
                    events.extend(chunk)
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("Polygon options flow scan failed: %s", exc)
            return []

        events.sort(key=lambda e: e.premium, reverse=True)
        self._last_update = datetime.now(timezone.utc).isoformat()
        self._last_error = None
        return events[:limit]

    async def health(self) -> OptionsProviderStatus:
        if not self.api_key:
            return OptionsProviderStatus(
                provider=self.name,
                enabled=False,
                mode="unavailable",
                status="unavailable",
                message=(
                    "POLYGON_API_KEY is not set; options radar will use "
                    "mock fallback if configured."
                ),
            )
        status: str = "ok" if self._last_update else "degraded"
        message = "Polygon chain snapshot provider active."
        if self._last_error:
            status = "degraded"
            message = f"Last scan error: {self._last_error}"
        return OptionsProviderStatus(
            provider=self.name,
            enabled=True,
            mode="realtime" if self.realtime else "delayed",
            status=status,
            message=message,
            last_update=self._last_update,
            delay_seconds=0 if self.realtime else 900,
        )

    def _sanitize_universe(self, universe: Optional[List[str]]) -> List[str]:
        if not universe:
            return list(_DEFAULT_UNIVERSE)
        clean: List[str] = []
        for raw in universe:
            ticker = raw.upper().strip()
            if _TICKER_RE.match(ticker):
                clean.append(ticker)
        return clean or list(_DEFAULT_UNIVERSE)

    async def _fetch_underlying_chain(
        self,
        session: aiohttp.ClientSession,
        underlying: str,
    ) -> List[OptionsFlowEvent]:
        url = f"{_BASE_URL}/v3/snapshot/options/{underlying}"
        params = {
            "apiKey": self.api_key,
            "limit": _CHAIN_LIMIT,
            "sort": "volume",
            "order": "desc",
        }
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"Polygon options snapshot {underlying} "
                    f"HTTP {resp.status}: {text[:120]}"
                )
            payload = await resp.json()

        results = payload.get("results") or []
        stock_price = self._underlying_price(results, payload)
        events: List[OptionsFlowEvent] = []
        for row in results:
            event = self._normalize_contract(
                underlying, row, stock_price=stock_price
            )
            if event is not None:
                events.append(event)
        return events

    @staticmethod
    def _underlying_price(
        results: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> Optional[float]:
        for row in results:
            ua = row.get("underlying_asset") or {}
            price = ua.get("price")
            if price is not None:
                return float(price)
        return None

    def _normalize_contract(
        self,
        underlying: str,
        row: Dict[str, Any],
        *,
        stock_price: Optional[float],
    ) -> Optional[OptionsFlowEvent]:
        details = row.get("details") or {}
        day = row.get("day") or {}
        quote = row.get("last_quote") or {}
        greeks = row.get("greeks") or {}

        volume = int(day.get("volume") or 0)
        if volume < _MIN_CONTRACT_VOLUME:
            return None

        contract_type = str(details.get("contract_type") or "").lower()
        call_put = "C" if contract_type == "call" else "P"
        strike = float(details.get("strike_price") or 0.0)
        expiry_raw = details.get("expiration_date") or ""
        try:
            expiry_date = date.fromisoformat(str(expiry_raw)[:10])
        except ValueError:
            return None

        today = datetime.now(timezone.utc).date()
        dte = max(0, (expiry_date - today).days)
        price = float(day.get("vwap") or quote.get("midpoint") or 0.0)
        bid = float(quote.get("bid") or 0.0)
        ask = float(quote.get("ask") or 0.0)
        premium = price * volume * 100
        if premium < _MIN_DAY_PREMIUM:
            return None

        oi = int(row.get("open_interest") or 0)
        vol_oi = (volume / oi) if oi > 0 else 0.0
        change_pct = float(day.get("change_percent") or 0.0)
        iv = greeks.get("implied_volatility")
        iv_val = float(iv) if iv is not None else None

        side_bias = self._infer_side_bias(
            call_put, change_pct, price, bid, ask
        )
        contract_symbol = str(
            details.get("ticker")
            or f"O:{underlying}{expiry_date:%y%m%d}{call_put}"
        )

        return OptionsFlowEvent(
            underlying=underlying,
            contract_symbol=contract_symbol,
            side_bias=side_bias,
            call_put=call_put,
            strike=strike,
            expiry=expiry_date,
            dte=dte,
            trade_timestamp=datetime.now(timezone.utc),
            premium=premium,
            price=price,
            size=volume,
            bid=bid,
            ask=ask,
            volume=volume,
            open_interest=oi,
            volume_oi_ratio=vol_oi,
            volume_vs_avg_ratio=min(10.0, vol_oi * 2.0) if vol_oi else 1.0,
            block_flag=volume >= 500,
            repeated_directional_prints=min(10, volume // 200),
            iv=iv_val,
            iv_change=None,
            stock_price=stock_price,
            stock_move_pct=change_pct,
            underlying_dollar_volume=None,
            trust=OptionsFlowTrust(
                source="polygon",
                mode="realtime" if self.realtime else "delayed",
                delay_seconds=0 if self.realtime else 900,
                stale=False,
                synthetic=False,
            ),
        )

    @staticmethod
    def _infer_side_bias(
        call_put: str,
        change_pct: float,
        price: float,
        bid: float,
        ask: float,
    ) -> str:
        near_ask = ask > 0 and price >= (bid + ask) * 0.55
        if call_put == "C":
            if change_pct > 0 and near_ask:
                return "CALL_BUYING"
            if change_pct < 0:
                return "CALL_SELLING"
            return "BALANCED"
        if change_pct < 0 and near_ask:
            return "PUT_BUYING"
        if change_pct > 0:
            return "PUT_SELLING"
        return "BALANCED"
