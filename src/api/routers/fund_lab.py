"""
Fund Lab Router — Sprint 78
===========================
AI self-run fund sleeves vs benchmark using updated market data.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.fund_lab_service import get_fund_lab_service

router = APIRouter(prefix="/api/v7/fund-lab", tags=["fund-lab"])


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
    return sanitize_for_json(result)
