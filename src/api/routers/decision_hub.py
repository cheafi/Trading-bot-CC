"""GET /api/v7/decision-hub — platform-wide decision system."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.api.deps import sanitize_for_json
from src.services.decision_hub import build_decision_hub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE: Dict[str, Any] = {}
_CACHE_TS = 0.0
_TTL = 120
_STALE_MAX = 600


@router.get("/decision-hub")
async def decision_hub(request: Request):
    """Cross-tab decision strip + monitoring + allocator snapshot."""
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE and now - _CACHE_TS < _TTL:
        return _CACHE
    payload = await build_decision_hub(request)
    out = sanitize_for_json(payload)
    today_cache = getattr(request.app.state, "today_v7_cache", None) or {}
    if not today_cache and not (out.get("top_5") or out.get("decision_strip", {}).get("best_idea_now")):
        if _CACHE and now - _CACHE_TS < _STALE_MAX:
            stale = dict(_CACHE)
            stale["warming"] = True
            stale["stale"] = True
            return stale
        out["warming"] = True
    _CACHE = out
    _CACHE_TS = now
    return out
