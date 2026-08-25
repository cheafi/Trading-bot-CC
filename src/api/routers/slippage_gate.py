"""
Slippage Gate Router — POST /api/slippage/check
================================================
Pre-trade verdict (PASS/WARN/BLOCK) for an intended order.
Frontend calls before sending bracket to IBKR.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.deps import optional_api_key
from src.services.slippage_gate_service import check_slippage

logger = logging.getLogger(__name__)
router = APIRouter()


class SlippageCheckRequest(BaseModel):
    ticker: str
    size_shares: int
    current_price: float
    side: str = "BUY"


@router.post("/api/slippage/check", tags=["execution"])
async def slippage_check(
    req: SlippageCheckRequest, request: Request, _=optional_api_key
):
    """Pre-trade slippage verdict — call before sending bracket order."""
    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        return {
            "verdict": "WARN",
            "reasons": ["market_data service unavailable — proceeding without gate."],
        }
    try:
        return await check_slippage(
            ticker=req.ticker,
            size_shares=req.size_shares,
            current_price=req.current_price,
            market_data=mds,
            side=req.side,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("slippage_check failed: %s", exc)
        return {
            "verdict": "WARN",
            "reasons": [f"Gate error: {exc} — proceed at own risk."],
        }
