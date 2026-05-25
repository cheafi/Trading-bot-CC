"""
Opportunity Scanner REST router — Sprint 114.

Endpoints:
  GET  /api/v7/opportunity-scanner        — full ranked scan (cached 4h)
  GET  /api/v7/opportunity-scanner/status — last run metadata
  POST /api/v7/opportunity-scanner/invalidate — force refresh
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import optional_api_key, sanitize_for_json, verify_api_key
from src.engines.opportunity_scanner import run_opportunity_scanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/opportunity-scanner", tags=["opportunity-scanner"])

# ── 4-hour result cache ───────────────────────────────────────────────────────
_CACHE_TTL = 4 * 3600
_cache: Dict[str, Any] = {}  # key = regime/top_n/min filters
_CACHE_FILE = Path("models") / "opportunity_scanner_cache.json"
_DISK_CACHE_DISABLED = os.getenv("OPPORTUNITY_SCANNER_DISABLE_DISK_CACHE", "0") == "1"
_PILOT_SCORE_THRESH = 50.0
_SCAN_TIMEOUT_SECONDS = float(os.getenv("OPPORTUNITY_SCANNER_TIMEOUT_SECONDS", "8"))
_FORCE_SCAN_TIMEOUT_SECONDS = float(
    os.getenv("OPPORTUNITY_SCANNER_FORCE_TIMEOUT_SECONDS", "30")
)


def _cache_key(regime: str, top_n: int, min_price: float, min_vol: int) -> str:
    return f"{regime.upper()}_{top_n}_{min_price:.2f}_{int(min_vol)}"


def _with_candidate_tiers(data: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill action metadata for older cache files."""
    for candidate in data.get("candidates", []) or []:
        if candidate.get("action_tier"):
            continue
        if candidate.get("is_actionable"):
            action_tier = "TRADE"
        elif (
            candidate.get("is_watch")
            or float(candidate.get("score") or 0) >= _PILOT_SCORE_THRESH
        ):
            action_tier = "PILOT"
        else:
            action_tier = "WATCH"
        candidate["action_tier"] = action_tier
        candidate["position_hint"] = {
            "TRADE": "1.0R max if portfolio gates pass",
            "PILOT": "0.25R pilot / buy-small only",
            "WATCH": "Watchlist only",
        }[action_tier]
    return data


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    if _DISK_CACHE_DISABLED:
        return None
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


def _get_stale_cached(key: str) -> Optional[Dict[str, Any]]:
    """Return cache even if stale; used as timeout fallback."""
    entry = _cache.get(key)
    if entry:
        return entry["data"]
    if _DISK_CACHE_DISABLED:
        return None
    try:
        if _CACHE_FILE.exists():
            d = json.loads(_CACHE_FILE.read_text())
            if d.get("key") == key:
                _cache[key] = {"data": d.get("data", {}), "ts": d.get("ts", 0)}
                return d.get("data", {})
    except Exception:
        pass
    return None


def _get_regime_stale_cached(regime: str) -> Optional[Dict[str, Any]]:
    """Return latest cached result for regime, ignoring top_n/min filters."""
    regime_upper = regime.upper()
    # In-memory first
    best_ts = -1.0
    best_data: Optional[Dict[str, Any]] = None
    for k, entry in _cache.items():
        if k.startswith(f"{regime_upper}_") and entry.get("ts", 0) > best_ts:
            best_ts = entry.get("ts", 0)
            best_data = entry.get("data")
    if best_data:
        return best_data

    if _DISK_CACHE_DISABLED:
        return None
    try:
        if _CACHE_FILE.exists():
            d = json.loads(_CACHE_FILE.read_text())
            key = str(d.get("key", ""))
            if key.startswith(f"{regime_upper}_"):
                data = d.get("data", {})
                _cache[key] = {"data": data, "ts": d.get("ts", 0)}
                return data
    except Exception:
        pass
    return None


def _set_cached(key: str, data: Dict[str, Any]) -> None:
    ts = time.time()
    _cache[key] = {"data": data, "ts": ts}
    if _DISK_CACHE_DISABLED:
        return
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({"key": key, "data": data, "ts": ts}))
    except Exception:
        pass


def _diagnose_funnel(funnel: Dict[str, Any]) -> Dict[str, Any]:
    """Stage-by-stage drop diagnostic for zero-candidate cases.

    Returns where the funnel collapsed and a human-readable hint.
    """
    if not funnel:
        return {
            "verdict": "NO_FUNNEL_DATA",
            "hint": "Scanner has not run yet — click Refresh.",
            "stages": [],
        }
    initial = int(funnel.get("initial_universe", 0) or 0)
    pi = int(funnel.get("passed_initial_filters", 0) or 0)
    prs = int(funnel.get("passed_rs_filter", 0) or 0)
    pp = int(funnel.get("passed_pattern_filter", 0) or 0)
    final = int(funnel.get("final_candidates", 0) or 0)
    stages = [
        {"stage": "initial_universe", "count": initial, "kept_pct": 100.0},
        {
            "stage": "passed_initial_filters",
            "count": pi,
            "kept_pct": round((pi / initial * 100) if initial else 0, 1),
            "dropped": initial - pi,
            "reason": "price/volume/sector filters",
        },
        {
            "stage": "passed_rs_filter",
            "count": prs,
            "kept_pct": round((prs / max(pi, 1) * 100), 1),
            "dropped": pi - prs,
            "reason": "relative strength vs SPY (63d)",
        },
        {
            "stage": "passed_pattern_filter",
            "count": pp,
            "kept_pct": round((pp / max(prs, 1) * 100), 1),
            "dropped": prs - pp,
            "reason": "setup pattern detection",
        },
        {
            "stage": "final_candidates",
            "count": final,
            "kept_pct": round((final / max(pp, 1) * 100), 1),
            "dropped": pp - final,
            "reason": "ranking score threshold",
        },
    ]
    if initial == 0:
        verdict, hint = "EMPTY_UNIVERSE", "Universe is empty — check market_data cache."
    elif pi == 0:
        verdict, hint = (
            "ALL_DROPPED_INITIAL",
            "Every ticker failed price/volume gate. Lower min_price or min_vol.",
        )
    elif prs == 0:
        verdict, hint = (
            "ALL_DROPPED_RS",
            "No ticker is outperforming SPY. Likely BEAR/CHOPPY regime — switch engine.",
        )
    elif pp == 0:
        verdict, hint = (
            "ALL_DROPPED_PATTERN",
            "No setup patterns matched. Market may be range-bound — wait for cleaner setups.",
        )
    elif final == 0:
        verdict, hint = (
            "ALL_DROPPED_RANKING",
            "Setups detected but none cleared score threshold. Re-run with force_refresh.",
        )
    else:
        verdict, hint = "OK", "Funnel produced candidates."
    return {"verdict": verdict, "hint": hint, "stages": stages}


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
            payload = {**_with_candidate_tiers(cached), "cached": True}
            if int(payload.get("candidates_ranked", 0) or 0) == 0:
                payload["diagnosis"] = _diagnose_funnel(
                    payload.get("filter_funnel", {})
                )
            return sanitize_for_json(payload)
        stale = _get_stale_cached(key) or _get_regime_stale_cached(regime)
        if stale:
            payload = {
                **_with_candidate_tiers(stale),
                "cached": True,
                "stale": True,
                "warning": "serving stale scanner cache — use force_refresh=true for live rescan",
            }
            if int(payload.get("candidates_ranked", 0) or 0) == 0:
                payload["diagnosis"] = _diagnose_funnel(
                    payload.get("filter_funnel", {})
                )
            return sanitize_for_json(payload)
        return sanitize_for_json(
            {
                "engine": "idle",
                "regime": regime.upper(),
                "universe_size": 0,
                "filter_funnel": {},
                "candidates_raw": 0,
                "candidates_ranked": 0,
                "top_n": top_n,
                "generated_at": None,
                "candidates": [],
                "cached": False,
                "stale": True,
                "warming": False,
                "warning": "no scanner cache available — click Refresh for a live scan",
                "diagnosis": {
                    "verdict": "COLD_START",
                    "hint": "No scan has run yet. Use force_refresh=true to run one.",
                    "stages": [],
                },
            }
        )

    try:
        result = await asyncio.wait_for(
            run_opportunity_scanner(
                regime=regime,
                top_n=top_n,
                min_price=min_price,
                min_vol=min_vol,
            ),
            timeout=_FORCE_SCAN_TIMEOUT_SECONDS,
        )
        data = result.to_dict()
        _set_cached(key, data)
        if (
            str(data.get("engine", "")).lower() == "unknown"
            or data.get("candidates_ranked", 0) == 0
        ):
            logger.warning(
                "Scanner returned unknown engine or 0 candidates, refusing to serve stale fallback."
            )
            raise HTTPException(
                status_code=503,
                detail="Scanner failed or matched 0 opportunities. No stale fallbacks permitted.",
            )

        return sanitize_for_json({**data, "cached": False, "stale": False})
    except asyncio.TimeoutError:
        logger.warning("Opportunity scanner timeout, refusing to serve stale fallback.")
        raise HTTPException(
            status_code=504,
            detail="Scanner timed out reading market data. Please retry.",
        )


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
