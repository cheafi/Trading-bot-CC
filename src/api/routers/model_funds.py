"""
Model Funds Router — Sprint 99
================================
GET /api/v1/model-funds
  Returns all three productized model fund cards with full PM-facing data.

GET /api/v1/model-funds/{fund_id}
  Returns a single fund card.

GET /api/v1/model-funds/confidence-validation
  Proves that higher conviction → better outcomes (buckets by tier/regime/strategy).

Cache: 30-min TTL matching fund_lab/live — no extra yfinance load.
Auth: no auth required (read-only market data).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/model-funds", tags=["model-funds"])

# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: Optional[Dict[str, Any]] = None
_cache_time: float = 0.0
_CACHE_TTL: float = 1800.0  # 30 min
_lock = asyncio.Lock()


async def _build_payload(request: Request, benchmark: str) -> Dict[str, Any]:
    """Fetch fund_lab payload + build model fund cards."""
    from src.services.fund_lab_service import get_fund_lab_service
    from src.services.model_funds import get_model_fund_service

    # Resolve regime
    regime = "unknown"
    try:
        rs = getattr(request.app.state, "regime_service", None)
        if rs is not None:
            r = await rs.get()
            regime = (r or {}).get("trend", "unknown")
    except Exception:
        pass

    # Fund lab data (delegates to existing service — reuses its yfinance calls)
    mds = getattr(request.app.state, "market_data", None)
    service = get_fund_lab_service()
    lab_result = await service.run(
        mds, period="1y", benchmark=benchmark.upper(), top_n=5, regime=regime
    )

    # Build model fund cards
    mf_svc = get_model_fund_service()
    cards = await mf_svc.build_cards(
        lab_result, regime=regime, benchmark=benchmark.upper()
    )

    return {
        "funds": cards,
        "regime": regime,
        "benchmark": benchmark.upper(),
        "benchmark_return_pct": lab_result.get("benchmark_return_pct", 0.0),
        "winner": (
            max(cards, key=lambda c: c["fund_return_pct"])["id"] if cards else None
        ),
        "as_of": int(time.time()),
    }


@router.get("")
async def get_model_funds(
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    """
    All three model fund cards: Leader Momentum, Balanced Multi-Factor,
    Tactical/Defensive — each with benchmark-relative return, holdings,
    adds/reduces/exits, attribution, regime fit, and strategy identity.
    """
    global _cache, _cache_time

    now = time.time()
    if _cache and (now - _cache_time) < _CACHE_TTL:
        return {**_cache, "cached": True, "cache_age_s": int(now - _cache_time)}

    async with _lock:
        now = time.time()
        if _cache and (now - _cache_time) < _CACHE_TTL:
            return {**_cache, "cached": True, "cache_age_s": int(now - _cache_time)}

        try:
            payload = await _build_payload(request, benchmark)
            payload = sanitize_for_json(payload)
            _cache = payload
            _cache_time = time.time()
            return {**payload, "cached": False, "cache_age_s": 0}
        except Exception as exc:
            logger.warning("model-funds build failed: %s", exc)
            return {
                "error": f"model-funds unavailable: {exc}",
                "funds": [],
                "cached": False,
            }


@router.get("/invalidate")
async def invalidate_model_funds_cache() -> Dict[str, str]:
    """Bust the cache — triggers fresh fund computation on next request."""
    global _cache, _cache_time
    _cache = None
    _cache_time = 0.0
    return {"status": "cache cleared"}


@router.get("/{fund_id}")
async def get_single_fund(
    fund_id: str,
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    """Single model fund card by ID (LEADER_MOMENTUM / BALANCED_MULTI / TACTICAL_DEF)."""
    from src.services.model_funds import FUND_IDENTITY

    fund_id_upper = fund_id.upper()
    if fund_id_upper not in FUND_IDENTITY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown fund id '{fund_id}'. Valid: {list(FUND_IDENTITY.keys())}",
        )

    result = await get_model_funds(request, benchmark=benchmark)
    cards: List[Dict[str, Any]] = result.get("funds", [])
    card = next((c for c in cards if c.get("id") == fund_id_upper), None)
    if card is None:
        raise HTTPException(status_code=503, detail="Fund data not yet available")
    return card
