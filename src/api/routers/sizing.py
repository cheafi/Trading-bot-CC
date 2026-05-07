"""
Sizing Advisor REST Router — Sprint 109
========================================
Exposes the SizingAdvisor as REST endpoints.

Endpoints
---------
GET  /api/v7/size/advise            — single-ticker sizing recommendation
POST /api/v7/size/advise/batch      — batch sizing for up to 20 signals
GET  /api/v7/size/params            — current advisor parameters (equity, heat, limits)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from src.api.deps import optional_api_key, sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/size", tags=["v7-sizing"])


# ── Pydantic request models ─────────────────────────────────────────────────


class BatchSignal(BaseModel):
    ticker: str
    entry_price: float
    stop_price: float
    signal_score: float = 70.0
    signal_grade: str = "B"
    age_hours: float = 0.0
    strategy: str = "UNKNOWN"
    regime: str = "UNKNOWN"
    win_rate: Optional[float] = None
    avg_win_loss_ratio: Optional[float] = None


class BatchRequest(BaseModel):
    equity: float = 100_000.0
    current_heat_pct: float = 0.0
    signals: List[BatchSignal]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_advisor(equity: float, current_heat_pct: float):
    from src.engines.sizing_advisor import SizingAdvisor

    return SizingAdvisor(equity=equity, current_heat_pct=current_heat_pct)


def _get_equity(request: Request) -> float:
    """Pull equity from engine state; fall back to 100k."""
    try:
        engine = request.app.state.engine
        if engine and hasattr(engine, "portfolio_equity"):
            return float(engine.portfolio_equity)
    except Exception:  # noqa: BLE001
        pass
    return 100_000.0


def _get_heat(request: Request) -> float:
    """Pull current portfolio heat from engine state; fall back to 0."""
    try:
        engine = request.app.state.engine
        if engine and hasattr(engine, "current_heat_pct"):
            return float(engine.current_heat_pct)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/advise", summary="Single-ticker sizing recommendation")
async def advise_single(
    request: Request,
    ticker: str = Query(..., description="Ticker symbol"),
    entry_price: float = Query(..., gt=0, description="Entry price in USD"),
    stop_price: float = Query(..., gt=0, description="Stop-loss price in USD"),
    signal_score: float = Query(70.0, ge=0, le=100, description="Signal score 0–100"),
    signal_grade: str = Query("B", description="Setup grade (A+, A, B+, B, C+, C, D)"),
    age_hours: float = Query(0.0, ge=0, description="Signal age in hours"),
    strategy: str = Query("UNKNOWN", description="Strategy type for Thompson arm"),
    regime: str = Query("UNKNOWN", description="Current regime for Thompson arm"),
    equity: Optional[float] = Query(
        None, gt=0, description="Account equity; defaults to engine state"
    ),
    current_heat_pct: Optional[float] = Query(
        None, ge=0, le=1, description="Portfolio heat 0–1"
    ),
    _auth=optional_api_key,
):
    """
    Compute a full position sizing recommendation combining:
    - Fixed-risk / Half-Kelly base size
    - Thompson RL multiplier (strategy × regime arm)
    - Staleness decay adjustment
    - Portfolio heat throttle
    """
    try:
        eq = equity if equity is not None else _get_equity(request)
        heat = current_heat_pct if current_heat_pct is not None else _get_heat(request)
        advisor = _make_advisor(eq, heat)
        result = advisor.advise(
            ticker=ticker,
            entry_price=entry_price,
            stop_price=stop_price,
            signal_score=signal_score,
            signal_grade=signal_grade,
            age_hours=age_hours,
            strategy=strategy,
            regime=regime,
        )
        return sanitize_for_json(result.to_dict())
    except Exception as exc:
        logger.exception("[sizing] advise_single failed: %s", exc)
        return {"error": str(exc), "ticker": ticker}


@router.post("/advise/batch", summary="Batch sizing recommendations (max 20)")
async def advise_batch(
    request: Request,
    body: BatchRequest,
    _auth=optional_api_key,
):
    """
    Compute sizing recommendations for up to 20 signals in one call.
    Shared equity + heat values apply to all signals.
    """
    signals = body.signals[:20]  # hard cap
    eq = body.equity if body.equity > 0 else _get_equity(request)
    heat = body.current_heat_pct
    advisor = _make_advisor(eq, heat)

    results: List[Dict[str, Any]] = []
    for sig in signals:
        try:
            r = advisor.advise(
                ticker=sig.ticker,
                entry_price=sig.entry_price,
                stop_price=sig.stop_price,
                signal_score=sig.signal_score,
                signal_grade=sig.signal_grade,
                age_hours=sig.age_hours,
                strategy=sig.strategy,
                regime=sig.regime,
                win_rate=sig.win_rate,
                avg_win_loss_ratio=sig.avg_win_loss_ratio,
            )
            results.append(sanitize_for_json(r.to_dict()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[sizing] batch item %s failed: %s", sig.ticker, exc)
            results.append({"ticker": sig.ticker, "error": str(exc), "size_ok": False})

    ok_count = sum(1 for r in results if r.get("size_ok"))
    return {
        "equity": eq,
        "current_heat_pct": heat,
        "total": len(results),
        "sized_ok": ok_count,
        "results": results,
    }


@router.get("/params", summary="Current SizingAdvisor parameters")
async def sizing_params(
    request: Request,
    _auth=optional_api_key,
):
    """Return current effective sizing parameters (equity, heat, limits)."""
    from src.core.risk_limits import RISK

    eq = _get_equity(request)
    heat = _get_heat(request)
    return sanitize_for_json(
        {
            "equity": eq,
            "current_heat_pct": round(heat, 4),
            "max_risk_pct": 0.01,
            "max_position_pct": 0.10,
            "max_portfolio_heat": getattr(RISK, "max_portfolio_heat", 0.06),
            "decay_schedule": {
                "A+": 48,
                "A": 36,
                "B+": 24,
                "B": 18,
                "C+": 12,
                "C": 8,
                "D": 4,
            },
            "decay_size_adj_range": "×0.5 – ×1.0",
            "thompson_mult_range": "×0.25 – ×2.0",
        }
    )
