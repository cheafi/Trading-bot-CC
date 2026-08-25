"""Data freshness watchdog router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from src.api.deps import optional_api_key
from src.services.data_freshness_service import freshness_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/data/freshness", tags=["ops"])
async def data_freshness(request: Request, _=optional_api_key):
    """Last-bar age per critical stream. Use in dashboard banner."""
    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        return {
            "worst_tier": "UNKNOWN",
            "streams": [],
            "error": "market_data service unavailable",
        }
    try:
        return await freshness_report(mds)
    except Exception as exc:  # pragma: no cover
        logger.exception("freshness_report failed: %s", exc)
        return {"worst_tier": "UNKNOWN", "streams": [], "error": str(exc)}
