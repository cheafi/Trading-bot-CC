"""
Opportunity intelligence — insider / 13F / events / strategy curve (research-only).

GET /api/v7/intelligence/insider?ticker=
GET /api/v7/intelligence/institutional?ticker=
GET /api/v7/intelligence/events?ticker=
GET /api/v7/intelligence/strategy-health?ticker=&strategy_id=
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.event_noise_filter import build_event_risk_context
from src.services.insider_tracker import build_insider_context
from src.services.institutional_13f import build_institutional_context
from src.services.strategy_curve_health import build_strategy_curve_context

router = APIRouter(prefix="/api/v7/intelligence", tags=["opportunity-intelligence"])
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")


def _validate_ticker(ticker: str) -> str:
    sym = ticker.upper().strip()
    if not _TICKER_RE.match(sym):
        sym = "AAPL"  # safe default for bad input in research endpoints
    return sym


@router.get("/insider")
async def intelligence_insider(
    ticker: str = Query(..., min_length=1, max_length=12),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(build_insider_context(sym, degraded=False))


@router.get("/institutional")
async def intelligence_institutional(
    ticker: str = Query(..., min_length=1, max_length=12),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(build_institutional_context(sym))


@router.get("/events")
async def intelligence_events(
    ticker: str = Query(..., min_length=1, max_length=12),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(build_event_risk_context(sym))


@router.get("/strategy-health")
async def intelligence_strategy_health(
    ticker: str = Query(..., min_length=1, max_length=12),
    strategy_id: Optional[str] = Query(None, max_length=64),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(
        build_strategy_curve_context(sym, strategy_id=strategy_id or "momentum_breakout_v2")
    )
