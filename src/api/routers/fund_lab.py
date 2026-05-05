"""
Fund Lab Router — Sprint 78 / 89
==================================
AI self-run fund sleeves vs benchmark using updated market data.

Sprint 89 additions:
  GET /api/v7/fund-lab/live  — lightweight 5-min cached status for 24/7 dashboard
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.fund_lab_service import get_fund_lab_service

router = APIRouter(prefix="/api/v7/fund-lab", tags=["fund-lab"])

# ── 24/7 live cache — refreshed at most every 5 min ──────────────────────────
_live_cache: Optional[Dict[str, Any]] = None
_live_cache_time: float = 0.0
_LIVE_TTL: float = 300.0  # 5 minutes
_live_lock = asyncio.Lock()


@router.get("/live")
async def fund_lab_live(
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    """
    Lightweight 24/7 fund monitor — returns the three active funds with key
    metrics.  Results are cached for 5 minutes so the dashboard can poll
    frequently without hammering yfinance.
    No auth required (read-only market data, same as market-intel).
    """
    global _live_cache, _live_cache_time

    now = time.time()
    if _live_cache and (now - _live_cache_time) < _LIVE_TTL:
        return {
            **_live_cache,
            "cached": True,
            "cache_age_s": int(now - _live_cache_time),
        }

    async with _live_lock:
        # double-check after acquiring lock
        now = time.time()
        if _live_cache and (now - _live_cache_time) < _LIVE_TTL:
            return {
                **_live_cache,
                "cached": True,
                "cache_age_s": int(now - _live_cache_time),
            }

        mds = getattr(
            getattr(request, "app", None) and request.app.state, "market_data", None
        )
        if mds is None:
            return {"error": "market_data service not initialised", "funds": []}

        service = get_fund_lab_service()
        result = await service.run(
            mds, period="1y", benchmark=benchmark.upper(), top_n=5
        )
        payload = sanitize_for_json(result)
        payload["as_of"] = int(time.time())
        _live_cache = payload
        _live_cache_time = time.time()
        return {**payload, "cached": False, "cache_age_s": 0}


@router.get("/self-run")
async def fund_lab_self_run(
    request: Request,
    period: str = Query(default="1y", description="1mo,3mo,6mo,1y,2y,5y"),
    benchmark: str = Query(default="SPY", description="Benchmark ticker"),
    top_n: int = Query(default=5, ge=3, le=8),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Build FUND_ALPHA/FUND_PENDA/FUND_CAT from latest data and compare vs index."""
    mds = getattr(
        getattr(request, "app", None) and request.app.state, "market_data", None
    )
    if mds is None:
        return {"error": "market_data service not initialised"}

    service = get_fund_lab_service()
    result = await service.run(mds, period=period, benchmark=benchmark, top_n=top_n)
    # Bust the live cache so next /live call reflects updated data
    global _live_cache, _live_cache_time
    _live_cache = None
    _live_cache_time = 0.0
    return sanitize_for_json(result)
