"""
Opportunity Scanner REST router — Sprint 114.

Endpoints:
  GET  /api/v7/opportunity-scanner        — full ranked scan (cached 4h)
  GET  /api/v7/opportunity-scanner/status — last run metadata
  POST /api/v7/opportunity-scanner/invalidate — force refresh
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import optional_api_key, sanitize_for_json, verify_api_key
from src.engines.opportunity_scanner import run_opportunity_scanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/opportunity-scanner", tags=["opportunity-scanner"])

# ── 4-hour result cache ───────────────────────────────────────────────────────
_CACHE_TTL = 4 * 3600
_cache: Dict[str, Any] = {}  # key = regime/top_n/min filters
_CACHE_FILE = Path("models") / "opportunity_scanner_cache.json"


def _cache_key(regime: str, top_n: int, min_price: float, min_vol: int) -> str:
    return f"{regime.upper()}_{top_n}_{min_price:.2f}_{int(min_vol)}"


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    # Try disk cache
    try:
        if _CACHE_FILE.exists():
            d = json.loads(_CACHE_FILE.read_text())
            if d.get("key") == key and time.time() - d.get("ts", 0) < _CACHE_TTL:
                _cache[key] = {"data": d["data"], "ts": d["ts"]}
                return d["data"]
    except Exception:
        pass
    return None


def _set_cached(key: str, data: Dict[str, Any]) -> None:
    ts = time.time()
    _cache[key] = {"data": data, "ts": ts}
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({"key": key, "data": data, "ts": ts}))
    except Exception:
        pass


@router.get("")
async def opportunity_scanner(
    regime: str = Query("BULL", description="BULL / BEAR / SIDEWAYS / CHOPPY"),
    top_n: int = Query(
        50, ge=10, le=200, description="Number of ranked candidates to return"
    ),
    min_price: float = Query(5.0, ge=0.5, description="Minimum close price filter"),
    min_vol: int = Query(200_000, ge=10_000, description="Minimum avg daily volume"),
    force_refresh: bool = Query(False, description="Bypass cache and re-scan"),
    _: bool = Depends(optional_api_key),
) -> Dict[str, Any]:
    """Neal-style dual-engine opportunity scanner.

    Returns the full ranked candidate list with:
    - Regime-adaptive engine (Bull / Weak)
    - Filter funnel stats (universe → candidates)
    - Score, leadership, actionability, tags per ticker
    - Close, Stop Loss (−2×ATR), Activation (TP1, +2×ATR)

    Results are cached for 4 hours. Use force_refresh=true to re-scan.
    Sprint 114.
    """
    key = _cache_key(regime, top_n, min_price, min_vol)
    if not force_refresh:
        cached = _get_cached(key)
        if cached:
            return sanitize_for_json({**cached, "cached": True})

    result = await run_opportunity_scanner(
        regime=regime,
        top_n=top_n,
        min_price=min_price,
        min_vol=min_vol,
    )
    data = result.to_dict()
    _set_cached(key, data)
    return sanitize_for_json({**data, "cached": False})


@router.get("/status")
async def scanner_status(
    _: bool = Depends(optional_api_key),
) -> Dict[str, Any]:
    """Return metadata about the last scan run (Sprint 114)."""
    entries = []
    for key, entry in _cache.items():
        entries.append(
            {
                "key": key,
                "age_seconds": int(time.time() - entry["ts"]),
                "candidates_ranked": entry["data"].get("candidates_ranked", 0),
                "regime": entry["data"].get("regime"),
                "engine": entry["data"].get("engine"),
                "generated_at": entry["data"].get("generated_at"),
            }
        )
    return sanitize_for_json(
        {
            "cached_runs": entries,
            "cache_ttl_seconds": _CACHE_TTL,
        }
    )


@router.post("/invalidate")
async def invalidate_cache(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Force-clear the scanner cache (Sprint 114)."""
    n = len(_cache)
    _cache.clear()
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except Exception:
        pass
    return {"cleared": n, "status": "cache invalidated"}
