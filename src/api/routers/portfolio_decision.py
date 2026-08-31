"""GET /api/v7/portfolio-decision — allocator decision console for portfolio tab."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.api.deps import sanitize_for_json
from src.services.portfolio_decision_console import build_portfolio_decision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE: Dict[str, Any] = {}
_CACHE_TS = 0.0
_TTL = 60


@router.get("/portfolio")
async def portfolio_ssot(request: Request):
    """Server-side portfolio SSOT — holdings from persisted store, not browser localStorage."""
    from src.api.routers import portfolio as portfolio_router

    book = portfolio_router._user_portfolio
    if not isinstance(book, dict) or book.get("holdings") is None:
        book = portfolio_router._load_portfolio_from_disk()
    holdings = book.get("holdings") or []
    ibkr_status = getattr(request.app.state, "ibkr_status", None) or {}
    ibkr_connected = bool(ibkr_status.get("connected"))
    return sanitize_for_json(
        {
            "holdings": holdings,
            "source": book.get("source") or "server",
            "updated_at": book.get("updated_at") or "",
            "position_count": len(holdings),
            "ssot": "server",
            "authority": "monitor_only",
            "broker_sync": "ok" if ibkr_connected else "unavailable",
            "local_storage_is_fallback_only": True,
        }
    )


@router.get("/portfolio-decision")
async def portfolio_decision(request: Request):
    """Portfolio decision summary + attribution + monitor + sleeves."""
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE and now - _CACHE_TS < _TTL:
        return _CACHE
    payload = await build_portfolio_decision(request)
    try:
        from src.services.cc_state import build_cc_state

        today = getattr(request.app.state, "today_v7_cache", None) or {}
        decision_authority = today.get("decision_authority") or {}
        regime = today.get("market_regime") or {}
        tradeability = str(regime.get("tradeability") or "WAIT")
        should_trade = bool(regime.get("should_trade", True))
        trust = today.get("trust") if isinstance(today.get("trust"), dict) else None
        payload["cc_state"] = build_cc_state(
            tradeability=tradeability,
            should_trade=should_trade,
            decision_authority=decision_authority
            if isinstance(decision_authority, dict)
            else {},
            execution_readiness=payload.get("execution") or {},
            surface_authority=None,
            trust=trust,
        )
    except Exception:
        pass
    out = sanitize_for_json(payload)
    _CACHE = out
    _CACHE_TS = now
    return out
