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
    # Required by SEC rate-limit policy: 10 req/s, must identify client
    _HEADERS = {
        "User-Agent": "TradingAI-Bot research@example.com",
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }
    # ticker → CIK cache (populated lazily)
    _cik_cache: Dict[str, str] = {}

    def name(self) -> str:
        return "sec_edgar"

    def is_available(self) -> bool:
        return True  # No API key needed

    # ── helpers ──────────────────────────────────────────────────

    async def _get_cik(self, ticker: str) -> Optional[str]:
        """Resolve ticker → zero-padded 10-digit CIK via EDGAR company search."""
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]
        import asyncio, urllib.request, json as _json
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"
        # Use simpler company-tickers.json mapping first (fast, no rate limit)
        try:
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            req = urllib.request.Request(tickers_url, headers={"User-Agent": self._HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    self._cik_cache[ticker] = cik
                    return cik
        except Exception as e:
            logger.warning("SEC CIK lookup failed for %s: %s", ticker, e)
        return None

    async def _fetch_json(self, url: str, host_header: Optional[str] = None) -> Optional[Dict]:
        """Fetch JSON from SEC with proper headers and timeout."""
        import urllib.request, json as _json
        headers = dict(self._HEADERS)
        if host_header:
            headers["Host"] = host_header
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return _json.loads(resp.read())
        except Exception as e:
            logger.warning("SEC HTTP fetch failed (%s): %s", url, e)
            return None

    # ── public API ───────────────────────────────────────────────

    async def get_recent_filings(
        self, ticker: str, form_types: Optional[List[str]] = None, limit: int = 10
    ) -> List[SECFiling]:
        """Fetch recent filings for a ticker via data.sec.gov/submissions/."""
        logger.info("SEC EDGAR: fetching filings for %s", ticker)
        cik = await self._get_cik(ticker)
        if not cik:
            return []
        data = await self._fetch_json(
            f"{self.BASE_URL}/submissions/CIK{cik}.json",
            host_header="data.sec.gov",
        )
        if not data:
            return []
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        company_name = data.get("name", ticker)
        results: List[SECFiling] = []
        for i, form in enumerate(forms):
            if form_types and form not in form_types:
                continue
            acc = accessions[i] if i < len(accessions) else ""
            acc_path = acc.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/full-index/{acc_path}/{docs[i]}" if i < len(docs) else ""
            results.append(SECFiling(
                cik=cik,
                company_name=company_name,
                form_type=form,
                filing_date=dates[i] if i < len(dates) else "",
                accession_number=acc,
                primary_document=docs[i] if i < len(docs) else "",
                url=url,
            ))
            if len(results) >= limit:
                break
        return results

    async def get_insider_transactions(
        self, ticker: str, days_back: int = 90
    ) -> List[InsiderTransaction]:
        """Fetch Form 4 insider transactions via EDGAR full-text search."""
        logger.info("SEC EDGAR: fetching insider txns for %s", ticker)
        import urllib.parse
        from datetime import datetime, timedelta
        start = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        q = urllib.parse.quote(ticker)
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{q}%22"
            f"&dateRange=custom&startdt={start}&forms=4"
            f"&_source=file_date,period_of_report,entity_name,file_num"
        )
        data = await self._fetch_json(url, host_header="efts.sec.gov")
        if not data:
            return []
        results: List[InsiderTransaction] = []
        for hit in data.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            # Parse minimal fields available in search index
            results.append(InsiderTransaction(
                issuer_name=src.get("entity_name", ticker),
                transaction_date=src.get("period_of_report", src.get("file_date", "")),
                transaction_type="?",   # full XML parse needed for exact type
                owner_name=src.get("display_names", ["?"])[0] if src.get("display_names") else "?",
            ))
        return results

    async def get_13f_holdings(self, cik: str) -> List[Dict[str, Any]]:
        """Fetch 13F institutional holdings via data.sec.gov/submissions/."""
        logger.info("SEC EDGAR: fetching 13F for CIK %s", cik)
        padded = str(cik).zfill(10)
        data = await self._fetch_json(
            f"{self.BASE_URL}/submissions/CIK{padded}.json",
            host_header="data.sec.gov",
        )
        if not data:
            return []
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        holdings = []
        for i, form in enumerate(forms):
            if form != "13F-HR":
                continue
            holdings.append({
                "form": form,
                "filing_date": dates[i] if i < len(dates) else "",
                "accession": accessions[i] if i < len(accessions) else "",
                "cik": padded,
                "company": data.get("name", ""),
            })
            if len(holdings) >= 5:   # last 5 13F filings
                break
        return holdings


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


class CongressDisclosureProvider(EventDataProvider):
    """
    House Clerk / Senate eFD financial disclosure provider.

    Sources:
    - House: https://disclosures-clerk.house.gov/
    - Senate: https://efdsearch.senate.gov/

    LEGAL NOTE: House disclosure portal has explicit
    prohibited-use language for certain commercial uses.
    This provider is for research/context only.
    Data is lagged (up to 45 days after transaction).
    """

    def name(self) -> str:
        return "congress_disclosure"

    def is_available(self) -> bool:
        return True  # Public data

    async def get_recent_trades(
        self,
        chamber: str = "both",
        days_back: int = 90,
        ticker_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent congressional financial disclosures.

        Returns normalized transaction records.
        """
        logger.info(
            f"Congress: fetching {chamber} disclosures, "
            f"days_back={days_back}, ticker={ticker_filter}"
        )
        return []

    async def get_member_trades(
        self, member_name: str
    ) -> List[Dict[str, Any]]:
        """Fetch trades for a specific member of congress."""
        logger.info(
            f"Congress: fetching trades for {member_name}"
        )
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
        self._congress = CongressDisclosureProvider()

        self._providers["sec_edgar"] = self._sec
        self._providers["cftc_cot"] = self._cftc
        self._providers["congress"] = self._congress

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
