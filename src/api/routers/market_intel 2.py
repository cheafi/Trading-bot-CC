"""
Market Intel Router — Sprint 81
================================
Extracted from main.py (was 5 inline @app.get routes, lines 11727-11877).

Endpoints:
    GET /api/market-intel/regime
    GET /api/market-intel/vix
    GET /api/market-intel/breadth
    GET /api/market-intel/spy-return
    GET /api/market-intel/rates
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

from src.services.regime_service import get_regime

# NOTE: market-intel routes are intentionally unauthenticated.
# All data is read-only reference data (regime label, VIX, SPY breadth) derived
# from public market prices — no portfolio state or user data is exposed.
# If the deployment requires auth on all endpoints, add:
#   dependencies=[Depends(verify_api_key)]
# to the APIRouter constructor below.
router = APIRouter(prefix="/api/market-intel", tags=["market-intel"])


@router.get("/regime")
async def market_intel_regime(request: Request):
    """
    Market regime classification — risk, trend, volatility labels.

    Returns the current regime from the singleton RegimeRouter,
    refreshed every 60 s.  Read-only, no side effects.
    """
    regime = await get_regime(request)
    if not regime:
        return {
            "regime": "UNKNOWN",
            "detail": "Regime router unavailable",
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        }
    return {
        "regime_label": regime.get(
            "regime_label",
            regime.get("risk", "NEUTRAL"),
        ),
        "risk": regime.get("risk", "NEUTRAL"),
        "trend": regime.get("trend", "NEUTRAL"),
        "volatility": regime.get("volatility", "NORMAL"),
        "strategy_playbook": regime.get("playbook", {}),
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/vix")
async def market_intel_vix(request: Request):
    """Current VIX level with classification."""
    mds = request.app.state.market_data
    try:
        vix = await mds.get_vix()
    except Exception:
        vix = None

    if vix is None:
        return {
            "vix": None,
            "label": "UNAVAILABLE",
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        }

    label = (
        "LOW"
        if vix < 15
        else (
            "NORMAL"
            if vix < 20
            else "ELEVATED" if vix < 30 else "HIGH" if vix < 40 else "EXTREME"
        )
    )
    return {
        "vix": round(vix, 2),
        "label": label,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/breadth")
async def market_intel_breadth(request: Request):
    """Market breadth — advance/decline ratio, new highs/lows."""
    mds = request.app.state.market_data
    try:
        breadth = await mds.get_market_breadth()
    except Exception:
        breadth = {}

    return {
        "breadth": breadth or {},
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/spy-return")
async def market_intel_spy_return(request: Request):
    """SPY return over various periods (1d, 5d, 1mo, 3mo, ytd)."""
    mds = request.app.state.market_data
    periods: Dict[str, Any] = {}

    async def _ret(period: str, label: str):
        try:
            r = await mds.get_spy_return(period=period)
            periods[label] = round(r * 100, 2) if r else None
        except Exception:
            periods[label] = None

    await asyncio.gather(
        _ret("5d", "1w_pct"),
        _ret("1mo", "1m_pct"),
        _ret("3mo", "3m_pct"),
        _ret("ytd", "ytd_pct"),
    )

    return {
        "spy_returns": periods,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/rates")
async def market_intel_rates(request: Request):
    """US Treasury yield curve snapshot (3M, 5Y, 10Y, 30Y)."""
    mds = request.app.state.market_data
    rate_tickers = [
        ("^IRX", "3M"),
        ("^FVX", "5Y"),
        ("^TNX", "10Y"),
        ("^TYX", "30Y"),
    ]

    async def _rate(sym: str) -> Optional[float]:
        try:
            q = await mds.get_quote(sym)
            return q["price"] if q else None
        except Exception:
            return None

    results = await asyncio.gather(
        *[_rate(sym) for sym, _ in rate_tickers],
    )

    yields_out: Dict[str, Any] = {}
    for (_, tenor), val in zip(rate_tickers, results):
        yields_out[tenor] = round(val, 3) if val else None

    y10 = yields_out.get("10Y")
    y3m = yields_out.get("3M")
    spread = round(y10 - y3m, 3) if y10 and y3m else None
    curve_status = (
        "INVERTED"
        if spread and spread < 0
        else (
            "FLAT"
            if spread is not None and spread < 0.5
            else "NORMAL" if spread else "UNKNOWN"
        )
    )

    return {
        "yields": yields_out,
        "spread_10y_3m": spread,
        "curve_status": curve_status,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }
