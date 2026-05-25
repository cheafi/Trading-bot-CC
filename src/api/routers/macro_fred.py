"""FRED macro data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.ingestors.fred import FRED_SERIES, FredClient

router = APIRouter(prefix="/api/macro/fred", tags=["data-layer"])
_fred_client = FredClient()


@router.get("")
async def fred_macro_snapshot():
    """Get FRED macro snapshot — yields, inflation, labor, credit."""
    snapshot = await _fred_client.fetch_snapshot()
    return {
        "configured": _fred_client.is_configured,
        "snapshot": snapshot.to_dict(),
        "available_series": list(FRED_SERIES.keys()),
        "note": (
            "Set FRED_API_KEY env var for live data. "
            "Free key: https://fred.stlouisfed.org/docs/api/api_key.html"
            if not _fred_client.is_configured
            else "Live FRED data"
        ),
    }


@router.get("/{series_id}")
async def fred_series(series_id: str, limit: int = Query(10, ge=1, le=100)):
    """Get specific FRED series observations."""
    meta = FRED_SERIES.get(series_id)
    if not meta:
        raise HTTPException(
            404,
            f"Unknown series: {series_id}. "
            f"Available: {list(FRED_SERIES.keys())}",
        )
    obs = await _fred_client.fetch_series(series_id, limit=limit)
    return {
        "series_id": series_id,
        "meta": meta,
        "observations": obs,
        "configured": _fred_client.is_configured,
    }
