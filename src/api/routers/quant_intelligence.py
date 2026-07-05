"""
Quant / algo / execution intelligence — research and ops context only.

GET /api/v7/quant/strategy-health
GET /api/v7/quant/cost-ranked
GET /api/v7/quant/sleeve-allocation
GET /api/v7/quant/execution-analytics
GET /api/v7/quant/factor-exposure
GET /api/v7/quant/strategy-validity
GET /api/v7/quant/drawdown-sizing
GET /api/v7/quant/tracker-wave
GET /api/v7/quant/cc-os
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.cc_operating_system import (
    TOP_10_BUILD_PRIORITY,
    authority_matrix_entry,
    build_cc_operating_system_context,
)
from src.services.cc_tracker_wave import TRACKER_FEATURE_REGISTRY, build_tracker_wave_context
from src.services.cost_adjusted_ranker import build_cost_rank_context
from src.services.drawdown_sizer import build_drawdown_sizer_context
from src.services.execution_algo_selector import build_execution_algo_context
from src.services.execution_analytics import (
    build_execution_analytics,
    build_execution_analytics_from_ibkr,
    build_empty_execution_analytics_state,
)
from src.services.factor_exposure import build_factor_exposure
from src.services.index_regime import build_index_regime_summary
from src.services.ai_intelligence import build_ai_intelligence_for_today
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
    if ibkr_connected:
        try:
            from src.services.ibkr_service import get_ibkr_service

            svc = get_ibkr_service()
            if svc.is_connected:
                fills = svc.get_recent_fills()
                return sanitize_for_json(
                    build_execution_analytics_from_ibkr(fills, ibkr_connected=True)
                )
        except Exception:
            pass
        return sanitize_for_json(build_empty_execution_analytics_state())
    return sanitize_for_json(
        build_execution_analytics(ibkr_connected=False, degraded=True)
    )


@router.get("/tracker-wave")
async def quant_tracker_wave(
    tradeability: str = Query("WAIT", max_length=24),
    ibkr_connected: bool = Query(False),
    degraded: bool = Query(False),
    _=Depends(verify_api_key),
):
    execution_analytics = build_execution_analytics(ibkr_connected=False, degraded=True)
    if ibkr_connected:
        try:
            from src.services.ibkr_service import get_ibkr_service

            svc = get_ibkr_service()
            if svc.is_connected:
                execution_analytics = build_execution_analytics_from_ibkr(
                    svc.get_recent_fills(),
                    ibkr_connected=True,
                )
        except Exception:
            pass
    from src.services.drawdown_sizer import evaluate_drawdown_sizing

    sizing = evaluate_drawdown_sizing(
        current_dd_pct=8.5,
        fallback_or_stale=degraded,
    )
    return sanitize_for_json(
        {
            "registry": TRACKER_FEATURE_REGISTRY,
            "console": build_tracker_wave_context(
                tradeability=tradeability,
                execution_analytics=execution_analytics,
                drawdown_sizing=sizing,
                degraded=degraded,
                ibkr_connected=ibkr_connected,
            ),
        }
    )


@router.get("/cc-os")
async def quant_cc_operating_system(
    tradeability: str = Query("WAIT", max_length=24),
    ibkr_connected: bool = Query(False),
    degraded: bool = Query(False),
    _=Depends(verify_api_key),
):
    from src.services.drawdown_sizer import evaluate_drawdown_sizing

    sizing = evaluate_drawdown_sizing(current_dd_pct=8.5, fallback_or_stale=degraded)
    return sanitize_for_json(
        {
            "top_10_priority": TOP_10_BUILD_PRIORITY,
            "registry": TRACKER_FEATURE_REGISTRY,
            "authority_sample": [
                authority_matrix_entry(fid)
                for fid in TOP_10_BUILD_PRIORITY
                if authority_matrix_entry(fid)
            ],
            "console": build_cc_operating_system_context(
                tradeability=tradeability,
                drawdown_sizing=sizing,
                degraded=degraded,
                ibkr_connected=ibkr_connected,
            ),
        }
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


@router.get("/index-regime")
async def quant_index_regime(
    trend: str = Query("SIDEWAYS", max_length=24),
    vix: Optional[float] = Query(None, ge=0, le=100),
    breadth: Optional[float] = Query(None, ge=0, le=100),
    tradeability: str = Query("WAIT", max_length=24),
    _=Depends(verify_api_key),
):
    return sanitize_for_json(
        build_index_regime_summary(
            trend=trend,
            vix=vix,
            breadth=breadth,
            tradeability=tradeability,
            should_trade=tradeability not in ("WAIT", "NO_TRADE"),
            degraded=vix is None,
        )
    )


@router.get("/execution-algo")
async def quant_execution_algo(
    ticker: str = Query("AAPL", min_length=1, max_length=12),
    spread_bps: float = Query(8.0, ge=0, le=100),
    _=Depends(verify_api_key),
):
    sym = _validate_ticker(ticker)
    return sanitize_for_json(
        build_execution_algo_context(ticker=sym, spread_bps=spread_bps)
    )


@router.get("/ai-intelligence")
async def quant_ai_intelligence(
    tradeability: str = Query("WAIT", max_length=24),
    _=Depends(verify_api_key),
):
    return sanitize_for_json(
        build_ai_intelligence_for_today(
            market_regime={"tradeability": tradeability, "trend": "SIDEWAYS"},
            scanner_degraded=True,
            degraded=True,
        )
    )
