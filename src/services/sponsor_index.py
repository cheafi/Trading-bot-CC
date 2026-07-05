"""Curated institutional sponsor index — 13F overlap for conviction stack."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Quality / track-record managers (CIK + canonical name for EDGAR entity match)
KNOWN_SPONSORS: List[Dict[str, str]] = [
    {"cik": "1067983", "name": "BERKSHIRE HATHAWAY", "tier": "A"},
    {"cik": "1103804", "name": "VIKING GLOBAL", "tier": "A"},
    {"cik": "1167483", "name": "TIGER GLOBAL", "tier": "A"},
    {"cik": "1535392", "name": "COATUE", "tier": "A"},
    {"cik": "1423053", "name": "CITADEL", "tier": "A"},
    {"cik": "1037389", "name": "RENAISSANCE", "tier": "A"},
    {"cik": "1350694", "name": "BRIDGEWATER", "tier": "B"},
    {"cik": "1410789", "name": "APPALOOSA", "tier": "A"},
    {"cik": "1336528", "name": "PERSHING SQUARE", "tier": "A"},
    {"cik": "1061768", "name": "BAUPOST", "tier": "A"},
    {"cik": "1649339", "name": "SCION ASSET", "tier": "B"},
    {"cik": "1079114", "name": "GREENLIGHT", "tier": "B"},
    {"cik": "1273087", "name": "MILLENNIUM", "tier": "B"},
    {"cik": "1000275", "name": "D E SHAW", "tier": "B"},
]

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TS: Dict[str, float] = {}
_CACHE_TTL = 3600  # 1h — 13F is quarterly; don't hammer SEC


def _normalize_name(value: str) -> str:
    return " ".join((value or "").upper().split())


def _match_sponsor(entity_name: str) -> Optional[Dict[str, str]]:
    norm = _normalize_name(entity_name)
    if not norm:
        return None
    for sponsor in KNOWN_SPONSORS:
        key = sponsor["name"]
        if key in norm or norm.startswith(key.split()[0]):
            return sponsor
    return None


async def lookup_13f_sponsor_overlap(ticker: str) -> Dict[str, Any]:
    """Search recent 13F-HR filings mentioning *ticker*; match sponsors."""
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 12:
        return {
            "status": "invalid",
            "matched_sponsors": [],
            "filing_hits": 0,
            "crowding_risk": None,
            "trust": {"source": "sec_edgar_13f", "mode": "search_index"},
        }

    now = time.time()
    if ticker in _CACHE and now - _CACHE_TS.get(ticker, 0) < _CACHE_TTL:
        return _CACHE[ticker]

    start = (
        datetime.now(timezone.utc) - timedelta(days=180)
    ).strftime("%Y-%m-%d")
    url = (
        "https://efts.sec.gov/LATEST/search-index"
        f"?q=%22{quote(ticker)}%22"
        f"&dateRange=custom&startdt={start}&forms=13F-HR"
        "&_source=file_date,entity_name,display_names"
    )
    headers = {
        "User-Agent": os.environ.get(
            "SEC_USER_AGENT",
            "CC-MarketIntelligence support@example.com",
        ),
        "Host": "efts.sec.gov",
    }

    matched: List[Dict[str, Any]] = []
    hits = 0
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                if resp.status != 200:
                    payload = {
                        "status": "unavailable",
                        "matched_sponsors": [],
                        "filing_hits": 0,
                        "crowding_risk": None,
                        "trust": {
                            "source": "sec_edgar_13f",
                            "mode": "search_index",
                            "message": f"SEC search HTTP {resp.status}",
                        },
                    }
                    return payload
                data = await resp.json()

        seen: set[str] = set()
        for hit in (data.get("hits") or {}).get("hits") or []:
            hits += 1
            src = hit.get("_source") or {}
            names = src.get("display_names") or []
            entity = src.get("entity_name") or (names[0] if names else "")
            sponsor = _match_sponsor(str(entity))
            if sponsor and sponsor["cik"] not in seen:
                seen.add(sponsor["cik"])
                matched.append(
                    {
                        "name": sponsor["name"],
                        "cik": sponsor["cik"],
                        "tier": sponsor["tier"],
                        "filing_date": src.get("file_date", ""),
                        "entity_label": entity,
                    }
                )
    except Exception as exc:
        logger.debug("13F sponsor lookup failed for %s: %s", ticker, exc)
        return {
            "status": "unavailable",
            "matched_sponsors": [],
            "filing_hits": 0,
            "crowding_risk": None,
            "trust": {
                "source": "sec_edgar_13f",
                "mode": "search_index",
                "message": str(exc),
            },
        }

    tier_a = sum(1 for m in matched if m.get("tier") == "A")
    crowding = "low"
    if len(matched) >= 5 or tier_a >= 3:
        crowding = "high"
    elif len(matched) >= 2:
        crowding = "medium"

    payload = {
        "status": "ok" if matched else "none",
        "matched_sponsors": matched,
        "filing_hits": hits,
        "sponsor_count": len(matched),
        "tier_a_count": tier_a,
        "crowding_risk": crowding if matched else "unknown",
        "trust": {
            "source": "sec_edgar_13f",
            "mode": "search_index",
            "note": (
                "13F overlap via SEC full-text search (last ~6mo). "
                "Holdings size / adds vs trims not parsed in Phase 4."
            ),
        },
    }
    _CACHE[ticker] = payload
    _CACHE_TS[ticker] = now
    return payload
