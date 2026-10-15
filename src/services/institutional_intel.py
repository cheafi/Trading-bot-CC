"""Institutional read-only intel — 13F, ETF books, OpenAlex factors."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from src.services.research_safety import sanitize_research_payload

logger = logging.getLogger(__name__)

_OPENALEX = "https://api.openalex.org/works"
_USER_AGENT = "CC-X-Research/1.0 (mailto:research@localhost)"


async def fetch_openalex_factors(
    query: str, *, limit: int = 8
) -> Dict[str, Any]:
    q = str(query or "").strip()[:200]
    if not q:
        raise ValueError("query required")
    params = {
        "search": q,
        "per_page": min(max(limit, 1), 25),
        "mailto": "research@localhost",
    }
    headers = {"User-Agent": _USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(_OPENALEX, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.debug("OpenAlex fetch failed: %s", exc)
        return sanitize_research_payload(
            {
                "ok": False,
                "source": "openalex",
                "query": q,
                "error": type(exc).__name__,
                "authority": "research_only",
            }
        )
    works: List[Dict[str, Any]] = []
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        works.append(
            {
                "title": row.get("display_name"),
                "year": row.get("publication_year"),
                "doi": row.get("doi"),
                "cited_by": (row.get("cited_by_count") or 0),
                "concepts": [
                    c.get("display_name")
                    for c in (row.get("concepts") or [])[:3]
                    if isinstance(c, dict)
                ],
            }
        )
    return sanitize_research_payload(
        {
            "ok": True,
            "source": "openalex",
            "query": q,
            "works": works,
            "note": "Academic factor papers — read-only; not trading signals.",
            "authority": "research_only",
        }
    )


def etf_constituents_across_markets(etf: str) -> Dict[str, Any]:
    """ETF → sector proxy constituents (free public mapping, not live holdings file."""
    from src.scanners.sector_scanner import SECTOR_ETFS, SECTOR_STOCKS

    sym = str(etf or "SPY").upper().strip()
    sector = None
    for sec, etf_sym in SECTOR_ETFS.items():
        if etf_sym.upper() == sym:
            sector = sec
            break
    constituents: List[str] = []
    if sector is not None:
        constituents = list(SECTOR_STOCKS.get(sector, []))
    if sym == "SPY":
        constituents = constituents or ["AAPL", "MSFT", "NVDA", "AMZN", "META"]
    return sanitize_research_payload(
        {
            "ok": True,
            "etf": sym,
            "sector_proxy": sector.value if sector else None,
            "constituents": constituents[:25],
            "note": "Proxy list from sector scanner — not official fund holdings.",
            "authority": "research_only",
        }
    )


async def fetch_13f_manager_context(ticker: str) -> Dict[str, Any]:
    from src.services.filing_13f_qoq import qoq_sponsor_diffs
    from src.services.sponsor_index import lookup_13f_sponsor_overlap

    overlap = await lookup_13f_sponsor_overlap(ticker.upper())
    sponsors = (overlap.get("matched_sponsors") or overlap.get("sponsors") or [])[:10]
    qoq = qoq_sponsor_diffs(overlap.get("matched_sponsors") or [])
    holdings_qoq = None
    holdings_managers: List[Dict[str, Any]] = []
    from src.services.filing_13f_cache import fetch_holdings_qoq_cached

    for sp in overlap.get("matched_sponsors") or []:
        if not isinstance(sp, dict) or not sp.get("cik"):
            continue
        if sp.get("tier") != "A":
            continue
        if len(holdings_managers) >= 3:
            break
        row = await fetch_holdings_qoq_cached(str(sp["cik"]), ticker.upper())
        if not row.get("ok"):
            continue
        row = dict(row)
        row["manager"] = sp.get("name")
        row["cik"] = sp.get("cik")
        holdings_managers.append(row)
        if holdings_qoq is None:
            holdings_qoq = row
    return sanitize_research_payload(
        {
            "ok": True,
            "ticker": ticker.upper(),
            "source": "sec_edgar_13f",
            "sponsors": sponsors,
            "qoq_position_diffs": qoq,
            "holdings_share_qoq": holdings_qoq,
            "holdings_share_qoq_managers": holdings_managers,
            "trust": overlap.get("trust"),
            "authority": "research_only",
        }
    )


async def fetch_arxiv_factors(query: str, *, limit: int = 6) -> Dict[str, Any]:
    import xml.etree.ElementTree as ET

    q = str(query or "").strip()[:200]
    if not q:
        raise ValueError("query required")
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{q}",
        "start": 0,
        "max_results": min(max(limit, 1), 15),
    }
    headers = {"User-Agent": _USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
    except Exception as exc:
        logger.debug("arXiv fetch failed: %s", exc)
        return sanitize_research_payload(
            {
                "ok": False,
                "source": "arxiv",
                "query": q,
                "error": type(exc).__name__,
                "authority": "research_only",
            }
        )
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers: List[Dict[str, Any]] = []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        published = entry.findtext("a:published", default="", namespaces=ns)
        link = ""
        for ln in entry.findall("a:link", ns):
            if ln.attrib.get("type") == "text/html":
                link = ln.attrib.get("href") or link
        papers.append({"title": title, "published": published[:10], "link": link})
    return sanitize_research_payload(
        {
            "ok": True,
            "source": "arxiv",
            "query": q,
            "papers": papers,
            "authority": "research_only",
        }
    )


async def fetch_event_contract_probability(topic: str) -> Dict[str, Any]:
    """Read-only Polymarket gamma search when reachable (no auth)."""
    q = str(topic or "").strip()[:120]
    url = "https://gamma-api.polymarket.com/markets"
    params = {"limit": 5, "active": "true", "closed": "false"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params, headers={"User-Agent": _USER_AGENT})
            if resp.status_code != 200:
                raise RuntimeError(f"http_{resp.status_code}")
            markets = resp.json()
    except Exception as exc:
        return sanitize_research_payload(
            {
                "ok": False,
                "topic": q,
                "implied_probability": None,
                "source": "event_contracts",
                "error": type(exc).__name__,
                "authority": "research_only",
            }
        )
    hits: List[Dict[str, Any]] = []
    if isinstance(markets, list):
        for m in markets[:20]:
            if not isinstance(m, dict):
                continue
            question = str(m.get("question") or "")
            if q and q.lower() not in question.lower():
                continue
            prob = m.get("outcomePrices") or m.get("bestBid")
            hits.append(
                {
                    "question": question[:200],
                    "implied_probability": prob,
                    "slug": m.get("slug"),
                }
            )
    return sanitize_research_payload(
        {
            "ok": bool(hits),
            "topic": q,
            "markets": hits[:5],
            "source": "polymarket_gamma",
            "note": "Descriptive implied prob — not a trade signal.",
            "authority": "research_only",
        }
    )


async def institutional_intel_bundle(
    *,
    ticker: str,
    factor_query: Optional[str] = None,
    etf: Optional[str] = None,
) -> Dict[str, Any]:
    t = str(ticker or "SPY").upper()
    fq = factor_query or f"momentum factor equity {t}"
    return sanitize_research_payload(
        {
            "ok": True,
            "ticker": t,
            "filings_13f": await fetch_13f_manager_context(t),
            "etf_book": etf_constituents_across_markets(etf or "SPY"),
            "openalex_factors": await fetch_openalex_factors(fq),
            "arxiv_factors": await fetch_arxiv_factors(fq),
            "event_contracts": await fetch_event_contract_probability(
                f"Fed rate {t} recession"
            ),
            "authority": "research_only",
        }
    )
