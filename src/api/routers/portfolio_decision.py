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


@router.get("/portfolio-decision")
async def portfolio_decision(request: Request):
    """Portfolio decision summary + attribution + monitor + sleeves."""
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE and now - _CACHE_TS < _TTL:
        return _CACHE
    payload = await build_portfolio_decision(request)
    out = sanitize_for_json(payload)
    _CACHE = out
    _CACHE_TS = now
    return out
