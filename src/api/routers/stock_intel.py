"""GET /api/v7/stock-intel/{ticker} — aggregated Dossier command center payload."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.services.stock_intel import build_stock_intel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE_TTL_SEC = 60


@router.get("/stock-intel/{ticker}")
async def stock_intel(ticker: str, request: Request):
    """
    Single-stock aggregate for Clarity Console Dossier.
    Bundles dossier, conviction, peers, P9 engines, options, catalysts, ownership.
    """
    ticker = validate_ticker(ticker)
    cache: Dict[str, Any] = getattr(request.app.state, "stock_intel_cache", None) or {}
    if cache is None:
        cache = {}
        request.app.state.stock_intel_cache = cache

    now = time.time()
    entry = cache.get(ticker)
    if entry and (now - entry.get("ts", 0)) < _CACHE_TTL_SEC:
        return entry["payload"]

    try:
        payload = await build_stock_intel(request, ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("stock-intel failed for %s", ticker)
        raise HTTPException(status_code=503, detail="Stock intel aggregation failed") from exc

    cache[ticker] = {"ts": now, "payload": payload}
    return sanitize_for_json(payload)
