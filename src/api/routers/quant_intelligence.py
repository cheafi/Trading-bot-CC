"""
Quant / algo / execution intelligence — research and ops context only.

GET /api/v7/quant/strategy-health
GET /api/v7/quant/cost-ranked
GET /api/v7/quant/sleeve-allocation
GET /api/v7/quant/execution-analytics
GET /api/v7/quant/factor-exposure
GET /api/v7/quant/strategy-validity
GET /api/v7/quant/drawdown-sizing
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.cost_adjusted_ranker import build_cost_rank_context
from src.services.drawdown_sizer import build_drawdown_sizer_context
from src.services.execution_analytics import build_execution_analytics
from src.services.factor_exposure import build_factor_exposure
from src.services.strategy_allocator import build_allocator_context
from src.services.strategy_curve_health import build_strategy_curve_context
from src.services.strategy_validity import build_strategy_validity_context

router = APIRouter(prefix="/api/v7/quant", tags=["quant-intelligence"])
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")


def _validate_ticker(ticker: str) -> str:
    sym = ticker.upper().strip()
    if not _TICKER_RE.match(sym):
        sym = "AAPL"
    return sym


@router.get("/strategy-health")
async def quant_strategy_health(
    ticker: str = Query(..., min_length=1, max_length=12),
    strategy_id: Optional[str] = Query(None, max_length=64),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(
        build_strategy_curve_context(sym, strategy_id=strategy_id or "momentum_breakout_v2")
    )


@router.get("/cost-ranked")
async def quant_cost_ranked(
    ticker: str = Query(..., min_length=1, max_length=12),
    raw_score: float = Query(7.0, ge=0, le=10),
    tradeability: str = Query("SELECTIVE", max_length=24),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(
        build_cost_rank_context(sym, raw_score=raw_score, tradeability=tradeability)
    )


@router.get("/sleeve-allocation")
async def quant_sleeve_allocation(_=Depends(verify_api_key)):
    return sanitize_for_json(build_allocator_context())


@router.get("/execution-analytics")
async def quant_execution_analytics(
    ibkr_connected: bool = Query(False),
    _=Depends(verify_api_key),
):
    return sanitize_for_json(
        build_execution_analytics(ibkr_connected=ibkr_connected, degraded=not ibkr_connected)
    )


@router.get("/factor-exposure")
async def quant_factor_exposure(
    ticker: str = Query(..., min_length=1, max_length=12),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(build_factor_exposure(sym))


@router.get("/strategy-validity")
async def quant_strategy_validity(
    strategy_id: str = Query("momentum_breakout_v2", max_length=64),
    _=Depends(verify_api_key),
):
    return sanitize_for_json(build_strategy_validity_context(strategy_id))


@router.get("/drawdown-sizing")
async def quant_drawdown_sizing(
    current_dd_pct: float = Query(8.5, ge=0, le=100),
    dd_budget_pct: float = Query(15.0, ge=5, le=50),
    research_only: bool = Query(False),
    _=Depends(verify_api_key),
):
    return sanitize_for_json(
        build_drawdown_sizer_context(
            current_dd_pct=current_dd_pct,
            dd_budget_pct=dd_budget_pct,
            research_only=research_only,
        )
    )
