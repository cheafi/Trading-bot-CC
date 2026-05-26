"""Alpha Operating System endpoints — Sprint 3/4."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json
from src.services.leaders_tracker import build_leaders_snapshot
from src.services.pm_memory import append_note, get_memory
from src.services.rebalance_sim import simulate_rebalance
from src.services.thesis_drift import build_thesis_drift

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-aos"])


@router.post("/rebalance-sim")
async def rebalance_sim(request: Request, policy: str = Query("equal_weight")):
    positions = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        positions = _user_portfolio.get("holdings") or []
    except Exception:
        logger.debug("rebalance-sim holdings failed", exc_info=True)
    return sanitize_for_json(simulate_rebalance(positions, policy=policy))


@router.get("/compare")
async def compare_tickers(
    request: Request,
    a: str = Query(..., min_length=1, max_length=10),
    b: str = Query(..., min_length=1, max_length=10),
):
    """Why this not that — side-by-side stub with live quotes when available."""
    from src.services.stock_intel import build_stock_intel

    sym_a = a.strip().upper()
    sym_b = b.strip().upper()
    if sym_a == sym_b:
        raise HTTPException(status_code=400, detail="Tickers must differ")
    intel_a = intel_b = None
    err_a = err_b = None
    try:
        intel_a = await build_stock_intel(request, sym_a)
    except Exception as exc:
        err_a = str(exc)
    try:
        intel_b = await build_stock_intel(request, sym_b)
    except Exception as exc:
        err_b = str(exc)
    return sanitize_for_json(
        {
            "a": sym_a,
            "b": sym_b,
            "intel_a": intel_a,
            "intel_b": intel_b,
            "errors": {"a": err_a, "b": err_b},
            "verdict_hint": _compare_verdict(intel_a, intel_b),
        }
    )


def _compare_verdict(
    ia: Optional[Dict[str, Any]],
    ib: Optional[Dict[str, Any]],
) -> str:
    if not ia or not ib:
        return "Insufficient data for compare"
    ca = (ia.get("confluence") or {}).get("score") or 0
    cb = (ib.get("confluence") or {}).get("score") or 0
    if ca > cb + 10:
        return f"Higher confluence: {ia.get('ticker')}"
    if cb > ca + 10:
        return f"Higher confluence: {ib.get('ticker')}"
    return "Similar confluence — decide by portfolio fit and regime"


@router.get("/leaders-tracker")
async def leaders_tracker(limit: int = Query(15, ge=1, le=40)):
    return sanitize_for_json(build_leaders_snapshot(limit=limit))


@router.get("/pm-memory/{ticker}")
async def pm_memory_get(ticker: str):
    return sanitize_for_json(get_memory(ticker))


@router.post("/pm-memory/{ticker}")
async def pm_memory_post(ticker: str, body: Dict[str, Any]):
    try:
        return sanitize_for_json(append_note(ticker, body or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/thesis-drift/{ticker}")
async def thesis_drift(ticker: str, request: Request):
    from src.services.stock_intel import build_stock_intel
    from src.services.pm_memory import get_memory

    try:
        intel = await build_stock_intel(request, ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mem = get_memory(ticker)
    return sanitize_for_json(
        build_thesis_drift(ticker, stock_intel=intel, pm_memory=mem.get("summary"))
    )
