"""Platform extras — catalyst calendar, risk cockpit, PM memo."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request

from src.api.deps import sanitize_for_json
from src.services.catalyst_calendar import build_catalyst_calendar
from src.services.pm_memo import generate_pm_memo
from src.services.portfolio_decision_console import build_portfolio_decision
from src.services.portfolio_risk_cockpit import build_portfolio_risk_cockpit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])


@router.get("/catalyst-calendar")
async def catalyst_calendar(
    request: Request,
    tickers: Optional[str] = Query(None, description="Comma-separated tickers"),
):
    syms = [t.strip() for t in tickers.split(",")] if tickers else None
    return sanitize_for_json(await build_catalyst_calendar(request, syms))


@router.get("/portfolio-risk-cockpit")
async def portfolio_risk_cockpit(request: Request):
    positions = []
    try:
        from src.api.routers.portfolio import portfolio_monitor

        mon = await portfolio_monitor(request)
        positions = mon.get("positions") or []
    except Exception:
        logger.debug("risk cockpit monitor failed", exc_info=True)
    return sanitize_for_json(build_portfolio_risk_cockpit(positions))


@router.get("/pm-memo")
async def pm_memo(
    request: Request,
    scope: str = Query("portfolio", description="portfolio | ticker | today"),
    ticker: Optional[str] = None,
):
    scope_l = scope.lower()
    portfolio_decision = None
    today = None
    stock_intel = None

    if scope_l in ("portfolio", "ticker"):
        portfolio_decision = await build_portfolio_decision(request)
    if scope_l == "today":
        today = getattr(request.app.state, "today_v7_cache", None) or {}
    if scope_l == "ticker" and ticker:
        try:
            from src.services.stock_intel import build_stock_intel

            stock_intel = await build_stock_intel(request, ticker.strip().upper())
        except Exception:
            logger.debug("pm_memo stock_intel failed", exc_info=True)

    out = generate_pm_memo(
        scope=scope_l,
        ticker=ticker,
        portfolio_decision=portfolio_decision,
        today=today,
        stock_intel=stock_intel,
    )
    return sanitize_for_json(out)
