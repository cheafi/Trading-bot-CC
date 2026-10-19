"""GET /api/v7/portfolio-decision — allocator decision console for portfolio tab."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Request

from src.api.deps import sanitize_for_json
from src.services.portfolio_decision_console import build_portfolio_decision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE_BY_SCOPE: Dict[str, Dict[str, Any]] = {}
_CACHE_TS_BY_SCOPE: Dict[str, float] = {}
_TTL = 60


def portfolio_decision_cache_scope(request: Request) -> str:
    """
    Isolate cached portfolio-decision payloads per operator context.

    Uses API key (when present), client identity, and current manual portfolio
    fingerprint so one request cannot receive another scope's cached book.
    """
    auth = (
        request.headers.get("X-API-Key")
        or request.headers.get("Authorization")
        or ""
    ).strip()
    client_host = ""
    if request.client and request.client.host:
        client_host = request.client.host
    operator = auth or f"anon:{client_host or 'unknown'}"

    holdings_fp = "0:"
    try:
        from src.api.routers import portfolio as _pf

        book = _pf._user_portfolio or {}
        holdings = book.get("holdings") or []
        updated = str(book.get("updated_at") or "")
        source = str(book.get("source") or "")
        holdings_fp = f"{source}:{len(holdings)}:{updated}"
    except Exception:
        holdings_fp = "unavailable"

    raw = f"{operator}|{holdings_fp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fail_closed_should_trade(regime: Dict[str, Any]) -> bool:
    """Missing regime permission defaults to no new trading (fail-closed)."""
    if not regime:
        return False
    if "should_trade" not in regime:
        return False
    return bool(regime.get("should_trade"))


def _cache_get(scope: str, now: float) -> Tuple[bool, Dict[str, Any] | None]:
    ts = _CACHE_TS_BY_SCOPE.get(scope, 0.0)
    payload = _CACHE_BY_SCOPE.get(scope)
    if payload and now - ts < _TTL:
        return True, payload
    return False, None


def _cache_put(scope: str, payload: Dict[str, Any], now: float) -> None:
    _CACHE_BY_SCOPE[scope] = payload
    _CACHE_TS_BY_SCOPE[scope] = now


@router.get("/portfolio-decision")
async def portfolio_decision(request: Request):
    """Portfolio decision summary + attribution + monitor + sleeves."""
    now = time.time()
    scope = portfolio_decision_cache_scope(request)
    hit, cached = _cache_get(scope, now)
    if hit and cached is not None:
        return cached

    payload = await build_portfolio_decision(request)
    try:
        from src.services.cc_state import build_cc_state

        today = getattr(request.app.state, "today_v7_cache", None) or {}
        decision_authority = today.get("decision_authority") or {}
        regime = today.get("market_regime") or {}
        tradeability = str(regime.get("tradeability") or "WAIT")
        should_trade = fail_closed_should_trade(
            regime if isinstance(regime, dict) else {}
        )
        trust = today.get("trust") if isinstance(today.get("trust"), dict) else None
        payload["cc_state"] = build_cc_state(
            tradeability=tradeability,
            should_trade=should_trade,
            decision_authority=decision_authority if isinstance(decision_authority, dict) else {},
            execution_readiness=payload.get("execution") or {},
            surface_authority=None,
            trust=trust,
        )
    except Exception:
        pass
    out = sanitize_for_json(payload)
    _cache_put(scope, out, now)
    return out
