"""
Portfolio VaR Router — historical-simulation 1-day 95% VaR.
Endpoint: POST /api/portfolio/var-historical
Body: { positions: [...], equity: float, lookback_period?: '1y'|'6mo'|'3mo' }
Falls back gracefully — never raises 500 for missing data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.deps import optional_api_key
from src.services.var_historical_service import compute_historical_var

logger = logging.getLogger(__name__)
router = APIRouter()


class VarHistRequest(BaseModel):
    positions: List[Dict[str, Any]] = []
    equity: float = 100000.0
    lookback_period: str = "1y"


@router.post("/api/portfolio/var-historical", tags=["portfolio"])
async def var_historical(req: VarHistRequest, request: Request, _=optional_api_key):
    """Compute historical-sim VaR from real 1y daily returns of supplied positions."""
    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        return {
            "method": "insufficient",
            "warning": "market_data service unavailable on app state.",
            "sample_size": 0,
            "tier": "NO_SERVICE",
        }
    try:
        result = await compute_historical_var(
            positions=req.positions or [],
            market_data=mds,
            equity=req.equity or 100000.0,
            lookback_period=req.lookback_period or "1y",
        )
        return result
    except Exception as exc:  # pragma: no cover
        logger.exception("var_historical failed: %s", exc)
        return {
            "method": "insufficient",
            "warning": f"VaR computation error: {exc}",
            "sample_size": 0,
            "tier": "ERROR",
        }
