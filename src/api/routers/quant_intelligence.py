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
from src.services.ai_intelligence import build_ai_intelligence_for_today
from src.services.capacity_intelligence import (
    build_capacity_context,
    build_sleeve_capacity,
)
from src.services.cost_adjusted_ranker import build_cost_rank_context
from src.services.drawdown_sizer import build_drawdown_sizer_context
from src.services.execution_algo_selector import build_execution_algo_context
from src.services.execution_analytics import build_execution_analytics
from src.services.execution_tca import build_execution_tca_context
from src.services.factor_exposure import build_factor_exposure
from src.services.index_regime import build_index_regime_summary
from src.services.strategy_allocator import build_allocator_context
from src.services.strategy_curve_analytics import build_strategy_curve_analytics
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
        build_strategy_curve_context(
            sym, strategy_id=strategy_id or "momentum_breakout_v2"
        )
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
        build_execution_analytics(
            ibkr_connected=ibkr_connected, degraded=not ibkr_connected
        )
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


@router.get("/capacity")
async def quant_capacity(
    ticker: str = Query("AAPL", min_length=1, max_length=12),
    size_shares: float = Query(1000, ge=0, le=1e9),
    adv: Optional[float] = Query(None, ge=0),
    price: Optional[float] = Query(None, ge=0),
    raw_score: float = Query(7.0, ge=0, le=10),
    spread_bps: Optional[float] = Query(None, ge=0, le=1000),
    _=Depends(verify_api_key),
):
    """Per-ticker capacity assessment (research-only, downgrade-only).

    Returns 'can it scale?' classification + %ADV / impact / net-of-scale edge.
    Degraded (adv omitted) -> classification 'unknown', never a guess.
    """
    sym = _validate_ticker(ticker)
    return sanitize_for_json(
        build_capacity_context(
            ticker=sym,
            size_shares=size_shares,
            adv=adv,
            price=price,
            raw_score=raw_score,
            spread_bps=spread_bps,
            degraded=adv is None,
        )
    )


@router.get("/strategy-curve-analytics")
async def quant_strategy_curve_analytics(
    strategy_id: str = Query("momentum_breakout_v2", max_length=64),
    days_since_calibration: int = Query(45, ge=0, le=3650),
    execution_drag_bps: Optional[float] = Query(None, ge=0, le=500),
    _=Depends(verify_api_key),
):
    """Time-series curve analytics (research-only). Synthetic series — degraded-labeled.

    Rolling Sharpe, drawdown duration/acceleration, expectancy & hit-rate trend,
    live-vs-backtest divergence, decay score. Never authorizes deploy.
    """
    # Deterministic synthetic equity curve + trade series (clearly research/mock).
    equity = [100.0]
    for i in range(1, 60):
        equity.append(round(equity[-1] * (1.004 if i % 3 else 0.992), 4))
    r_multiples = [0.8, -1.0, 1.5, 0.3, -0.5, 2.0, -1.0, 0.6] * 5
    win_flags = [r > 0 for r in r_multiples]
    return sanitize_for_json(
        build_strategy_curve_analytics(
            strategy_id=strategy_id,
            equity_curve=equity,
            r_multiples=r_multiples,
            win_flags=win_flags,
            live_expectancy_r=0.22,
            backtest_expectancy_r=0.35,
            days_since_calibration=days_since_calibration,
            execution_drag_bps=execution_drag_bps,
        )
    )


@router.get("/execution-tca")
async def quant_execution_tca(
    ibkr_connected: bool = Query(False),
    report_dimension: str = Query("algo", max_length=24),
    _=Depends(verify_api_key),
):
    """Per-order TCA report (research-only / ops_probe when live fills present).

    Uses an illustrative stub fill set when no live fills are wired — honestly
    labeled degraded/research_only. Never authorizes execution.
    """
    # Illustrative stub orders (epoch-ms timestamps, deterministic). Clearly
    # surfaced as degraded unless ibkr_connected is asserted by the caller.
    stub_orders = [
        {
            "ticker": "AAPL",
            "side": "BUY",
            "algo": "vwap",
            "venue": "IBKR",
            "order_type": "LMT",
            "session_minute": 15,
            "order_qty": 1000,
            "filled_qty": 1000,
            "arrival_price": 190.0,
            "avg_fill_price": 190.12,
            "interval_vwap": 190.05,
            "midpoint_price": 190.0,
            "ref_end_price": 190.5,
            "ts_signal": 0,
            "ts_send": 120,
            "ts_first_fill": 380,
            "ts_final_fill": 900,
            "handoff_ok": True,
        },
        {
            "ticker": "NVDA",
            "side": "BUY",
            "algo": "twap",
            "venue": "IBKR",
            "order_type": "MKT",
            "session_minute": 200,
            "order_qty": 500,
            "filled_qty": 450,
            "arrival_price": 120.0,
            "avg_fill_price": 120.35,
            "interval_vwap": 120.1,
            "midpoint_price": 120.0,
            "ref_end_price": 119.6,
            "ts_signal": 0,
            "ts_send": 90,
            "ts_first_fill": 250,
            "ts_final_fill": 1500,
            "cancel_replace_count": 1,
            "handoff_ok": True,
        },
        {
            "ticker": "MSFT",
            "side": "SELL",
            "algo": "vwap",
            "venue": "IBKR",
            "order_type": "LMT",
            "session_minute": 380,
            "order_qty": 800,
            "filled_qty": 0,
            "arrival_price": 410.0,
            "avg_fill_price": None,
            "handoff_ok": False,
        },
    ]
    return sanitize_for_json(
        build_execution_tca_context(
            stub_orders,
            ibkr_connected=ibkr_connected,
            report_dimension=report_dimension,
        )
    )


@router.get("/capacity/sleeves")
async def quant_capacity_sleeves(_=Depends(verify_api_key)):
    """Sleeve-level capacity headroom summary (Funds / Portfolio research)."""
    # Default illustrative sleeves when no live book is wired; degraded-labeled.
    sleeves = [
        {"name": "breakout", "size_shares": 5000, "adv": 2_000_000, "raw_score": 7.4},
        {"name": "pullback", "size_shares": 8000, "adv": 400_000, "raw_score": 6.8},
        {"name": "event_driven", "size_shares": 3000, "adv": 120_000, "raw_score": 7.1},
        {"name": "defensive", "size_shares": 2000, "adv": 5_000_000, "raw_score": 6.2},
    ]
    return sanitize_for_json(build_sleeve_capacity(sleeves))


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
