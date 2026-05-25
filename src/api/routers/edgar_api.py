"""SEC EDGAR filings and insider endpoints."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.ingestors.edgar import EdgarClient

router = APIRouter(prefix="/api/edgar", tags=["data-layer"])
_edgar_client = EdgarClient()
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")


def _validate_ticker(ticker: str) -> str:
    symbol = ticker.upper().strip()
    if not _TICKER_RE.match(symbol):
        raise HTTPException(400, "Invalid ticker")
    return symbol


@router.get("/{ticker}/filings")
async def edgar_filings(
    ticker: str,
    form_type: Optional[str] = Query(
        None, description="Filter: 10-K, 10-Q, 8-K, 4"
    ),
    limit: int = Query(10, ge=1, le=50),
):
    """Get recent SEC filings for a ticker."""
    symbol = _validate_ticker(ticker)
    form_types = [form_type] if form_type else None
    filings = await _edgar_client.get_recent_filings(
        symbol,
        form_types=form_types,
        limit=limit,
    )
    return {
        "ticker": symbol,
        "filings": [f.to_dict() for f in filings],
        "count": len(filings),
    }


@router.get("/{ticker}/insider")
async def edgar_insider(ticker: str):
    """Get insider transaction summary for a ticker."""
    symbol = _validate_ticker(ticker)
    return await _edgar_client.get_insider_summary(symbol)


@router.get("/{ticker}/earnings")
async def edgar_earnings(ticker: str):
    """Get recent earnings-related filings (10-K, 10-Q, 8-K)."""
    symbol = _validate_ticker(ticker)
    filings = await _edgar_client.get_earnings_filings(symbol)
    return {"ticker": symbol, "filings": filings}
