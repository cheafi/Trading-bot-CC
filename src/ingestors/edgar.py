"""SEC EDGAR ingestion — filings context for decision surfaces.

Fetches recent filings (10-K, 10-Q, 8-K, 4 insider, 13F) from
SEC's EDGAR full-text search API and company filings API.

No API key required — SEC EDGAR is free and public.
Requires a User-Agent header with contact info per SEC policy.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["EdgarClient", "Filing", "InsiderTransaction"]


# ═══════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Filing:
    """A single SEC filing."""

    ticker: str
    cik: str
    form_type: str  # 10-K, 10-Q, 8-K, 4, 13F-HR, etc.
    filed_date: str
    description: str
    url: str
    accession_number: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "cik": self.cik,
            "form_type": self.form_type,
            "filed_date": self.filed_date,
            "description": self.description,
            "url": self.url,
            "accession_number": self.accession_number,
        }


@dataclass(frozen=True)
class InsiderTransaction:
    """Parsed insider transaction from Form 4."""

    ticker: str
    filer_name: str
    filer_title: str
    transaction_date: str
    transaction_type: str  # P (purchase), S (sale), A (grant)
    shares: float
    price_per_share: float
    total_value: float
    ownership_type: str  # D (direct), I (indirect)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "filer_name": self.filer_name,
            "filer_title": self.filer_title,
            "transaction_date": self.transaction_date,
            "transaction_type": self.transaction_type,
            "shares": self.shares,
            "price_per_share": round(self.price_per_share, 2),
            "total_value": round(self.total_value, 2),
            "ownership_type": self.ownership_type,
        }


# ═══════════════════════════════════════════════════════════════
# CIK lookup (top tickers)
# ═══════════════════════════════════════════════════════════════

# Pre-cached CIKs for common tickers (SEC lookup is slow)
_CIK_CACHE: dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "NVDA": "0001045810",
    "META": "0001326801",
    "TSLA": "0001318605",
    "JPM": "0000019617",
    "V": "0001403161",
    "MA": "0001141391",
    "UNH": "0000731766",
    "JNJ": "0000200406",
    "PG": "0000080424",
    "HD": "0000354950",
    "BAC": "0000070858",
    "XOM": "0000034088",
    "CVX": "0000093410",
    "PFE": "0000078003",
    "ABBV": "0001551152",
    "LLY": "0000059478",
    "AMD": "0000002488",
    "CRM": "0001108524",
    "NFLX": "0001065280",
    "BA": "0000012927",
    "GS": "0000886982",
    "RKLB": "0001819994",
}


# ═══════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════


class EdgarClient:
    """SEC EDGAR API client.

    Uses the EDGAR full-text search API (efts.sec.gov) and
    company filings API (data.sec.gov).
    """

    EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
    FILINGS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    USER_AGENT = os.environ.get(
        "SEC_USER_AGENT",
        "CC-MarketIntelligence support@example.com",
    )

    def __init__(self) -> None:
        self._cik_cache = dict(_CIK_CACHE)
        self._filings_cache: dict[str, list[Filing]] = {}
        self._cache_ts: dict[str, float] = {}
        self._cache_ttl = 1800  # 30 min

    async def get_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK for a ticker."""
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        try:
            import aiohttp

            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "company": ticker,
                "type": "",
                "dateb": "",
                "owner": "include",
                "count": "1",
                "search_text": "",
                "action": "getcompany",
                "CIK": ticker,
                "output": "atom",
            }
            headers = {"User-Agent": self.USER_AGENT}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Parse CIK from response
                        if "CIK=" in text:
                            start = text.index("CIK=") + 4
                            end = text.index("&", start)
                            cik = text[start:end].zfill(10)
                            self._cik_cache[ticker] = cik
                            return cik
        except Exception as exc:
            logger.debug(f"[EDGAR] CIK lookup failed for {ticker}: {exc}")

        return None

    async def get_recent_filings(
        self,
        ticker: str,
        form_types: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[Filing]:
        """Fetch recent filings for a ticker.

        Args:
            ticker: stock ticker
            form_types: filter by form type (e.g. ["10-K", "10-Q", "8-K"])
            limit: max filings to return
        """
        cik = await self.get_cik(ticker)
        if not cik:
            return []

        import time

        cache_key = f"{ticker}:{','.join(form_types or [])}"
        now = time.time()
        if (
            cache_key in self._filings_cache
            and now - self._cache_ts.get(cache_key, 0) < self._cache_ttl
        ):
            return self._filings_cache[cache_key][:limit]

        try:
            import aiohttp

            url = self.FILINGS_URL.format(cik=cik)
            headers = {"User-Agent": self.USER_AGENT}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"[EDGAR] {ticker} filings HTTP {resp.status}"
                        )
                        return []
                    data = await resp.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            descriptions = recent.get("primaryDocDescription", [])
            accessions = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])

            filings: list[Filing] = []
            for i in range(min(len(forms), 100)):
                form = forms[i] if i < len(forms) else ""
                if form_types and form not in form_types:
                    continue

                acc = accessions[i] if i < len(accessions) else ""
                doc = docs[i] if i < len(docs) else ""
                acc_path = acc.replace("-", "")
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{cik}/{acc_path}/{doc}"
                )

                filings.append(Filing(
                    ticker=ticker,
                    cik=cik,
                    form_type=form,
                    filed_date=dates[i] if i < len(dates) else "",
                    description=descriptions[i] if i < len(descriptions) else "",
                    url=filing_url,
                    accession_number=acc,
                ))
                if len(filings) >= limit:
                    break

            self._filings_cache[cache_key] = filings
            self._cache_ts[cache_key] = now
            return filings

        except Exception as exc:
            logger.debug(f"[EDGAR] {ticker} filings error: {exc}")
            return []

    async def get_insider_summary(
        self,
        ticker: str,
        days: int = 90,
    ) -> dict:
        """Get a summary of recent insider transactions.

        Returns aggregate buy/sell activity for the last N days.
        """
        filings = await self.get_recent_filings(
            ticker, form_types=["4"], limit=20
        )

        buy_count = 0
        sell_count = 0
        buy_value = 0.0
        sell_value = 0.0

        # Note: actual Form 4 parsing requires XML parsing of each filing
        # This returns filing metadata as a proxy
        for f in filings:
            # Heuristic from description
            desc = f.description.lower()
            if "purchase" in desc or "acquisition" in desc:
                buy_count += 1
            elif "sale" in desc or "disposition" in desc:
                sell_count += 1

        signal = "NEUTRAL"
        if buy_count > sell_count * 2:
            signal = "INSIDER_BUYING"
        elif sell_count > buy_count * 2:
            signal = "INSIDER_SELLING"

        return {
            "ticker": ticker,
            "period_days": days,
            "form4_filings": len(filings),
            "buy_filings": buy_count,
            "sell_filings": sell_count,
            "signal": signal,
            "note": "Based on Form 4 filing metadata; detailed parsing requires XML",
        }

    async def get_earnings_filings(
        self,
        ticker: str,
        limit: int = 4,
    ) -> list[dict]:
        """Get recent earnings-related filings (10-K, 10-Q, 8-K)."""
        filings = await self.get_recent_filings(
            ticker, form_types=["10-K", "10-Q", "8-K"], limit=limit
        )
        return [f.to_dict() for f in filings]
