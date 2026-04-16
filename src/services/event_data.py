"""
CC — Event & Positioning Data Layer

Structured interfaces for official event/positioning data sources.
Each provider returns a canonical schema so consumers don't care about
the underlying API.

Priority order (Section 11 of review):
1. SEC EDGAR / data.sec.gov  — filings, insider, 13F (no API key)
2. FRED / ALFRED             — macro data, real-time vintages
3. CFTC COT                  — weekly positioning (Tues data, Fri release)
4. House/Senate disclosures  — lagged, legal-gated
5. Alpaca streaming          — WebSocket for trades, orders, news

Design rule: external data affects timing, conviction, or risk —
it does NOT directly fire trades.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# CANONICAL EVENT SCHEMAS
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SECFiling:
    """A single SEC filing (10-K, 10-Q, 8-K, etc.)."""

    cik: str = ""
    company_name: str = ""
    form_type: str = ""
    filing_date: str = ""
    accession_number: str = ""
    primary_document: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cik": self.cik,
            "company_name": self.company_name,
            "form_type": self.form_type,
            "filing_date": self.filing_date,
            "url": self.url,
        }


@dataclass
class InsiderTransaction:
    """SEC insider buy/sell transaction."""

    cik: str = ""
    issuer_name: str = ""
    owner_name: str = ""
    owner_title: str = ""
    transaction_type: str = ""  # P=Purchase, S=Sale
    transaction_date: str = ""
    shares: float = 0.0
    price_per_share: float = 0.0
    total_value: float = 0.0

    @property
    def is_buy(self) -> bool:
        return self.transaction_type in ("P", "A")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issuer": self.issuer_name,
            "owner": self.owner_name,
            "type": self.transaction_type,
            "date": self.transaction_date,
            "shares": self.shares,
            "value": self.total_value,
        }


@dataclass
class MacroDataPoint:
    """FRED/ALFRED macro observation."""

    series_id: str = ""
    series_name: str = ""
    observation_date: str = ""
    value: Optional[float] = None
    vintage_date: Optional[str] = None  # ALFRED real-time period

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_id": self.series_id,
            "name": self.series_name,
            "date": self.observation_date,
            "value": self.value,
            "vintage": self.vintage_date,
        }


@dataclass
class COTPosition:
    """CFTC Commitments of Traders report entry."""

    report_date: str = ""
    market_name: str = ""
    commercial_long: int = 0
    commercial_short: int = 0
    non_commercial_long: int = 0
    non_commercial_short: int = 0
    non_reportable_long: int = 0
    non_reportable_short: int = 0

    @property
    def speculative_net(self) -> int:
        return self.non_commercial_long - self.non_commercial_short

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.report_date,
            "market": self.market_name,
            "spec_net": self.speculative_net,
            "commercial_net": self.commercial_long - self.commercial_short,
        }


# ═══════════════════════════════════════════════════════════════════
# PROVIDER INTERFACES
# ═══════════════════════════════════════════════════════════════════


class EventDataProvider(ABC):
    """Base interface for event data providers."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class SECEdgarProvider(EventDataProvider):
    """
    SEC EDGAR / data.sec.gov provider.

    Public API — no API key required.
    Rate limit: 10 requests/second with User-Agent header.

    Endpoints:
    - Full-text search: https://efts.sec.gov/LATEST/search-index?q=...
    - Company filings: https://data.sec.gov/submissions/CIK{cik}.json
    - Insider: https://data.sec.gov/api/xbrl/...
    """

    BASE_URL = "https://data.sec.gov"
    SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

    def name(self) -> str:
        return "sec_edgar"

    def is_available(self) -> bool:
        return True  # No API key needed

    async def get_recent_filings(
        self, ticker: str, form_types: Optional[List[str]] = None, limit: int = 10
    ) -> List[SECFiling]:
        """Fetch recent filings for a ticker."""
        # TODO: implement HTTP call to data.sec.gov
        logger.info(f"SEC EDGAR: fetching filings for {ticker}")
        return []

    async def get_insider_transactions(
        self, ticker: str, days_back: int = 90
    ) -> List[InsiderTransaction]:
        """Fetch insider transactions."""
        logger.info(f"SEC EDGAR: fetching insider txns for {ticker}")
        return []

    async def get_13f_holdings(self, cik: str) -> List[Dict[str, Any]]:
        """Fetch 13F institutional holdings."""
        logger.info(f"SEC EDGAR: fetching 13F for CIK {cik}")
        return []


class FREDProvider(EventDataProvider):
    """
    FRED / ALFRED macro data provider.

    Requires API key from https://fred.stlouisfed.org/docs/api/api_key.html
    ALFRED vintage dates prevent look-ahead bias in macro modeling.

    Key series:
    - GDP, CPI, PCE, unemployment, retail sales
    - Fed funds rate, 10Y/2Y yields, yield curve
    - ISM manufacturing, consumer confidence
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    def name(self) -> str:
        return "fred"

    def is_available(self) -> bool:
        return self._api_key is not None

    async def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[MacroDataPoint]:
        """Fetch FRED series observations."""
        logger.info(f"FRED: fetching {series_id}")
        return []

    async def get_vintage(
        self,
        series_id: str,
        vintage_date: str,
    ) -> List[MacroDataPoint]:
        """Fetch ALFRED vintage (point-in-time) data."""
        logger.info(f"ALFRED: fetching {series_id} vintage {vintage_date}")
        return []

    # Key macro series for regime context
    REGIME_SERIES = {
        "VIXCLS": "VIX Close",
        "DGS10": "10-Year Treasury",
        "DGS2": "2-Year Treasury",
        "T10Y2Y": "10Y-2Y Spread",
        "DTWEXBGS": "Trade-Weighted Dollar",
        "GOLDAMGBD228NLBM": "Gold Price",
        "DCOILWTICO": "WTI Crude Oil",
        "UNRATE": "Unemployment Rate",
        "CPIAUCSL": "CPI All Urban",
        "FEDFUNDS": "Fed Funds Rate",
    }


class CFTCProvider(EventDataProvider):
    """
    CFTC Commitments of Traders data.

    Weekly data (Tuesday), released Friday 3:30 PM ET.
    Public CSV download — no API key.
    Source: https://www.cftc.gov/dea/futures/deacmelf.htm
    """

    def name(self) -> str:
        return "cftc_cot"

    def is_available(self) -> bool:
        return True  # Public data

    async def get_latest_cot(
        self, market_filter: Optional[str] = None
    ) -> List[COTPosition]:
        """Fetch latest COT report."""
        logger.info("CFTC: fetching latest COT report")
        return []


# ═══════════════════════════════════════════════════════════════════
# EVENT DATA AGGREGATOR
# ═══════════════════════════════════════════════════════════════════


class EventDataService:
    """
    Aggregates all event data sources into a unified interface.
    Consumers call this, never individual providers.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, EventDataProvider] = {}
        self._sec = SECEdgarProvider()
        self._fred: Optional[FREDProvider] = None
        self._cftc = CFTCProvider()

        self._providers["sec_edgar"] = self._sec
        self._providers["cftc_cot"] = self._cftc

    def configure_fred(self, api_key: str) -> None:
        self._fred = FREDProvider(api_key=api_key)
        self._providers["fred"] = self._fred

    def available_providers(self) -> List[str]:
        return [name for name, p in self._providers.items() if p.is_available()]

    async def get_ticker_events(self, ticker: str) -> Dict[str, Any]:
        """Get all event context for a ticker."""
        result: Dict[str, Any] = {
            "ticker": ticker,
            "filings": [],
            "insider_transactions": [],
            "macro_context": [],
            "positioning": [],
            "providers_used": self.available_providers(),
        }

        # SEC filings
        try:
            result["filings"] = [
                f.to_dict() for f in await self._sec.get_recent_filings(ticker)
            ]
        except Exception as e:
            logger.warning(f"SEC filing fetch failed: {e}")

        # Insider
        try:
            txns = await self._sec.get_insider_transactions(ticker)
            result["insider_transactions"] = [t.to_dict() for t in txns]
            # Clustered buying signal
            buys = sum(1 for t in txns if t.is_buy)
            sells = len(txns) - buys
            result["insider_sentiment"] = {
                "buys": buys,
                "sells": sells,
                "net": buys - sells,
                "signal": (
                    "bullish"
                    if buys > sells + 2
                    else "bearish" if sells > buys + 2 else "neutral"
                ),
            }
        except Exception as e:
            logger.warning(f"Insider fetch failed: {e}")

        return result

    async def get_macro_context(self) -> Dict[str, Any]:
        """Get macro context for regime/risk decisions."""
        result: Dict[str, Any] = {"series": {}}
        if self._fred and self._fred.is_available():
            for sid, name in FREDProvider.REGIME_SERIES.items():
                try:
                    points = await self._fred.get_series(sid)
                    if points:
                        latest = points[-1]
                        result["series"][sid] = {
                            "name": name,
                            "value": latest.value,
                            "date": latest.observation_date,
                        }
                except Exception as e:
                    logger.warning(f"FRED {sid} fetch failed: {e}")
        return result


# ── Module singleton ──────────────────────────────────────────
_event_service: Optional[EventDataService] = None


def get_event_data_service() -> EventDataService:
    global _event_service
    if _event_service is None:
        _event_service = EventDataService()
    return _event_service
