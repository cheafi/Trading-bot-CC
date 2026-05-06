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

# ── 24/7 live cache — refreshed at most every 30 min ────────────────────────
_live_cache: Optional[Dict[str, Any]] = None
_live_cache_time: float = 0.0
_LIVE_TTL: float = 1800.0  # 30 minutes — reduces yfinance load 6×
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

        # Resolve current regime for fund gating (BULL/BEAR/SIDEWAYS)
        regime = "unknown"
        try:
            regime_svc = getattr(request.app.state, "regime_service", None)
            if regime_svc is not None:
                r = await regime_svc.get()
                regime = (r or {}).get("trend", "unknown")
        except Exception:
            pass

        service = get_fund_lab_service()
        result = await service.run(
            mds, period="1y", benchmark=benchmark.upper(), top_n=5, regime=regime
        )
        payload = sanitize_for_json(result)
        payload["as_of"] = int(time.time())
        _live_cache = payload
        _live_cache_time = time.time()

        # Persist holdings + performance to SQLite (non-blocking best-effort)
        try:
            from src.services.fund_persistence import (
                upsert_holdings,
                upsert_performance,
            )

            bm = payload.get("benchmark", "SPY")
            for fund in payload.get("funds", []):
                fid = fund.get("name", "")
                if fid:
                    upsert_holdings(fid, fund.get("picks", []))
                    upsert_performance(fid, fund.get("metrics", {}), benchmark=bm)
        except Exception as _pe:
            import logging

            logging.getLogger(__name__).warning(
                "fund persistence write failed: %s", _pe
            )

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
