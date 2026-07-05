"""
Execution Router — Sprint 99
==============================
Exposes execution cost, fill quality tracking, Kelly sizing, and
multi-timeframe confluence gate over REST.

Routes:
  GET  /api/v7/execution/metrics          — fill quality stats (last 30d)
  POST /api/v7/execution/estimate         — pre-trade cost estimate (TWAP/VWAP)
  POST /api/v7/execution/record-fill      — record an actual fill
  GET  /api/v7/execution/fills            — list recent fills
  GET  /api/v7/execution/size-kelly       — dynamic Kelly position size
  POST /api/v7/execution/mtf-confluence   — multi-timeframe alignment gate
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.engines.execution_cost import get_execution_engine
from src.engines.mtf_confluence import CONFLUENCE_THRESHOLD, get_mtf_gate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/execution", tags=["execution"])


# ── Fill quality metrics ──────────────────────────────────────────────────────


@router.get("/metrics")
async def execution_metrics(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    lookback_days: int = Query(30, ge=1, le=365),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Best-ex summary: avg/median/p95 slippage, % favourable fills, total commission."""
    stats = get_execution_engine().quality_stats(
        ticker=ticker, lookback_days=lookback_days
    )
    return sanitize_for_json(stats)


# ── Pre-trade estimate ────────────────────────────────────────────────────────


@router.post("/estimate")
async def estimate_cost(
    ticker: str,
    side: str,
    shares: int,
    price: float,
    atr: float,
    adv: float = 10_000_000.0,
    twap_minutes: int = 30,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Pre-trade TWAP/VWAP execution cost estimate.

    Returns cost breakdown in USD and basis points.
    """
    est = get_execution_engine().estimate(
        ticker=ticker,
        side=side,
        shares=shares,
        price=price,
        atr=atr,
        adv=adv,
        twap_minutes=twap_minutes,
    )
    return sanitize_for_json(est.to_dict())


# ── Record fill ───────────────────────────────────────────────────────────────


@router.post("/record-fill")
async def record_fill(
    ticker: str,
    side: str,
    shares: int,
    expected_price: float,
    fill_price: float,
    commission: float = 0.0,
    strategy: str = "MARKET",
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Record an actual execution fill for post-trade slippage analysis."""
    rec = get_execution_engine().record_fill(
        ticker=ticker,
        side=side,
        shares=shares,
        expected_price=expected_price,
        fill_price=fill_price,
        commission=commission,
        strategy=strategy,
    )
    return sanitize_for_json(rec.to_dict())


# ── List fills ────────────────────────────────────────────────────────────────


@router.get("/fills")
async def list_fills(
    ticker: Optional[str] = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
    strategy: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """List recent execution fills."""
    fills = get_execution_engine().get_fills(
        ticker=ticker,
        lookback_days=lookback_days,
        strategy=strategy,
        limit=limit,
    )
    return sanitize_for_json(
        {"fills": [f.to_dict() for f in fills], "count": len(fills)}
    )


# ── Kelly position sizing ─────────────────────────────────────────────────────


@router.get("/size-kelly")
async def size_kelly(
    ticker: str,
    request: Request,
    win_rate: float = Query(0.55, ge=0.1, le=0.99),
    avg_win_pct: float = Query(0.06, ge=0.001),
    avg_loss_pct: float = Query(0.03, ge=0.001),
    account_equity: float = Query(100_000.0, ge=1000.0),
    kelly_fraction: float = Query(
        0.25, ge=0.05, le=1.0, description="Fractional Kelly (0.25 = quarter-Kelly)"
    ),
    max_position_pct: float = Query(0.05, ge=0.001, le=0.20),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Dynamic Kelly position size.

    Returns:
      - kelly_pct: raw Kelly fraction of equity
      - fractional_kelly_pct: kelly_pct × kelly_fraction (recommended)
      - position_usd: capped by max_position_pct
      - R:R: reward-to-risk ratio
    """
    rr = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 2.0
    # Kelly formula: f* = (p * b - q) / b where b = W/L ratio
    b = rr
    q = 1.0 - win_rate
    kelly_pct = max(0.0, (win_rate * b - q) / b)

    frac_kelly = min(kelly_pct * kelly_fraction, max_position_pct)
    position_usd = frac_kelly * account_equity

    return {
        "ticker": ticker,
        "win_rate": win_rate,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "rr_ratio": round(rr, 2),
        "kelly_pct": round(kelly_pct, 4),
        "fractional_kelly_pct": round(frac_kelly, 4),
        "kelly_fraction_used": kelly_fraction,
        "position_usd": round(position_usd, 2),
        "position_pct_of_equity": round(frac_kelly * 100, 2),
        "capped_at_max": frac_kelly >= max_position_pct,
    }


# ── MTF confluence gate ───────────────────────────────────────────────────────


@router.post("/mtf-confluence")
async def mtf_confluence(
    ticker: str,
    request: Request,
    direction: str = "LONG",
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Multi-timeframe alignment gate.

    Checks daily + weekly trend, momentum (RSI), MACD, and regime alignment.
    Returns a confluence_score [0–1] and approved flag (≥ 0.60 passes).
    """
    mds = getattr(
        getattr(request, "app", None) and request.app.state, "market_data", None
    )
    result = await get_mtf_gate().check(
        ticker=ticker.upper(),
        market_data_service=mds,
        direction=direction,
    )
    return sanitize_for_json(
        {
            **result.to_dict(),
            "threshold": CONFLUENCE_THRESHOLD,
        }
    )
