"""GET /api/v7/stock-intel/{ticker} — aggregated Dossier command center payload."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.services.stock_intel import build_stock_intel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE_TTL_SEC = 60
_CORE_CACHE_TTL_SEC = 30


@router.get("/stock-intel/{ticker}")
async def stock_intel(
    ticker: str,
    request: Request,
    lite: bool = Query(False, description="Core dossier only (fast path)"),
    enrichments: bool = Query(False, description="Enrichment modules only (second-phase async load)"),
):
    """
    Single-stock aggregate for Clarity Console Dossier.
    Bundles dossier, conviction, peers, P9 engines, options, catalysts, ownership.
    """
    ticker = validate_ticker(ticker)
    cache: Dict[str, Any] = getattr(request.app.state, "stock_intel_cache", None) or {}
    if cache is None:
        cache = {}
        request.app.state.stock_intel_cache = cache

    cache_key = f"{ticker}:enrich" if enrichments else (f"{ticker}:lite" if lite else ticker)
    ttl = _CORE_CACHE_TTL_SEC if lite else _CACHE_TTL_SEC
    now = time.time()
    entry = cache.get(cache_key)
    if entry and (now - entry.get("ts", 0)) < ttl:
        return entry["payload"]

    try:
        payload = await build_stock_intel(
            request,
            ticker,
            lite=lite,
            enrichments_only=enrichments,
        )
    except ValueError as exc:
        msg = str(exc)
        if "could not convert string to float" in msg:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid research input: expected numeric value, "
                    f"received ratio or non-numeric field ({msg})"
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("stock-intel failed for %s", ticker)
        try:
            from src.services.platform_error_log import log_dossier_timeout

            log_dossier_timeout(ticker=ticker, reason=str(exc))
        except Exception:
            logger.debug("platform error log append failed", exc_info=True)
        raise HTTPException(status_code=503, detail="Stock intel aggregation failed") from exc

    cache[cache_key] = {"ts": now, "payload": payload}
    return sanitize_for_json(payload)
