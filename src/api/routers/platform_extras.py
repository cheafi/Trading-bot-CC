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


@router.get("/stock-universe")
async def stock_universe():
    """Core US equity universe used by brief, RS, watchlist, and demo portfolio."""
    from src.core.stock_universe import (
        CORE_WATCHLIST,
        POPULAR_TICKERS,
        RS_UNIVERSE,
        universe_summary,
    )

    return sanitize_for_json(
        {
            **universe_summary(),
            "core_watchlist": CORE_WATCHLIST,
            "rs_universe": RS_UNIVERSE,
            "popular": POPULAR_TICKERS,
        }
    )


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


@router.get("/rs-decision")
async def rs_decision(
    request: Request,
    limit: int = Query(30, ge=5, le=60),
    sector: Optional[str] = Query(None),
):
    """Institutional RS decision surface — live leaders, buyability, freshness."""
    from src.services.rs_decision_surface import build_rs_decision_surface

    return sanitize_for_json(
        await build_rs_decision_surface(request, limit=limit, sector=sector)
    )


@router.get("/flow-decision")
async def flow_decision(request: Request, limit: int = Query(20, ge=1, le=40)):
    """Institutional options flow console — evidence ladder + PM actions."""
    from src.services.flow_decision_surface import build_flow_decision_surface

    return sanitize_for_json(await build_flow_decision_surface(request, limit=limit))


@router.get("/flow-decision/{ticker}")
async def flow_decision_ticker(
    request: Request, ticker: str, limit: int = Query(8, ge=1, le=20)
):
    """Single-ticker flow slice for Dossier 360 fusion."""
    from src.api.deps import validate_ticker
    from src.services.flow_decision_surface import build_ticker_flow_intel

    ticker = validate_ticker(ticker)
    return sanitize_for_json(
        await build_ticker_flow_intel(request, ticker, limit=limit)
    )


async def _cc_header_for_ops(request: Request) -> dict:
    """Cached / bounded cc-header — avoids ops-console hanging on freshness."""
    import asyncio
    import time as _time

    from src.api.routers.cc_header import cc_header

    now = _time.monotonic()
    cache = getattr(request.app.state, "cc_header_cache", None) or {}
    if cache.get("payload") and (now - float(cache.get("ts") or 0)) < 45:
        return cache["payload"]

    try:
        cc = await asyncio.wait_for(cc_header(request), timeout=8.0)
        if isinstance(cc, dict):
            request.app.state.cc_header_cache = {"payload": cc, "ts": now}
            return cc
    except asyncio.TimeoutError:
        logger.warning("ops-console: cc_header timed out; using cache or minimal snapshot")
    except Exception as exc:
        logger.warning("ops-console: cc_header failed: %s", exc)

    if cache.get("payload"):
        stale = dict(cache["payload"])
        stale["stale_header"] = True
        return stale
    return {}


@router.get("/ops-console")
async def ops_console(request: Request):
    """Operator verdict — runnable state, blockers, next actions."""
    import time as _time
    from datetime import datetime, timezone

    from src.api.app_state import get_engine
    from src.services.ops_operator_console import build_ops_operator_console

    engine = get_engine(request.app)
    st = getattr(request.app.state, "startup_time", None)
    if st is not None:
        uptime_s = (datetime.now(timezone.utc) - st).total_seconds()
    else:
        uptime_s = 0.0
    hours = int((uptime_s % 86400) // 3600)
    minutes = int((uptime_s % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m"

    eng_snap: dict = {
        "running": bool(getattr(engine, "_running", False)) if engine else False,
        "dry_run": bool(getattr(engine, "dry_run", True)) if engine else True,
        "cycle_count": int(getattr(engine, "cycle_count", 0)) if engine else 0,
        "signals_today": int(getattr(engine, "signals_today", 0)) if engine else 0,
        "trades_today": int(getattr(engine, "trades_today", 0)) if engine else 0,
        "cached_recommendations": (
            len(getattr(engine, "_cached_recommendations", [])) if engine else 0
        ),
        "circuit_breaker": bool(
            getattr(engine, "circuit_breaker_triggered", False)
        )
        if engine
        else False,
        "circuit_breaker_reason": str(
            getattr(engine, "circuit_breaker_reason", "") or ""
        ),
        "last_cycle": str(getattr(engine, "last_cycle_time", "") or "") or None,
    }

    t0 = _time.monotonic()
    regime_ms = -1
    try:
        rr = getattr(request.app.state, "regime_router", None)
        if rr:
            await request.app.state.market_data.get_market_state()
            regime_ms = round((_time.monotonic() - t0) * 1000, 1)
    except Exception:
        pass

    cc = await _cc_header_for_ops(request)
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    ops_status = {
        "uptime": uptime_str,
        "engine": eng_snap,
        "latency": {"regime_ms": regime_ms},
    }

    return sanitize_for_json(
        build_ops_operator_console(
            ops_status=ops_status,
            cc_header=cc if isinstance(cc, dict) else {},
            today=today,
        )
    )
