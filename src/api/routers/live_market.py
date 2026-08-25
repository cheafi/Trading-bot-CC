"""Live market overview — indices, macro, sectors, Asia, regime."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.deps import sanitize_for_json
from src.api.live_state import (
    LIVE_ASIA,
    LIVE_INDICES,
    LIVE_MACRO,
    LIVE_SECTORS,
    OVERVIEW_CACHE_TTL,
    fetch_regime_state,
    get_overview_cache,
    is_prewarm_done,
    mds_quote,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/market")
async def live_market(request: Request):
    """Live market overview — indices, macro, sectors, Asia, regime."""
    return await _build_live_market(request)


async def warm_market_overview(app) -> dict:
    """Startup prewarm helper — builds overview cache without HTTP request."""
    from starlette.requests import Request as StarletteRequest

    scope = {"type": "http", "app": app}
    request = StarletteRequest(scope)
    return await _build_live_market(request)


async def _build_live_market(request: Request):
    overview_cache = get_overview_cache()
    now = time.time()
    if overview_cache["data"] and (now - overview_cache["ts"]) < OVERVIEW_CACHE_TTL:
        return overview_cache["data"]

    if not is_prewarm_done() and not overview_cache["data"]:
        return JSONResponse(
            status_code=503,
            content={
                "error": "API warming up — first load takes ~5s",
                "mode": "loading",
            },
        )

    try:
        all_symbols = (
            [(s, n, "index") for s, n in LIVE_INDICES]
            + [(s, n, "macro") for s, n in LIVE_MACRO]
            + [(s, n, "sector") for s, n in LIVE_SECTORS]
            + [(s, n, "asia") for s, n in LIVE_ASIA]
        )

        async def _fetch_one(sym, name, group):
            try:
                q = await mds_quote(request, sym)
                q["name"] = name
                q["group"] = group
                return sym, q
            except Exception:
                return sym, {
                    "symbol": sym,
                    "name": name,
                    "group": group,
                    "price": 0,
                    "change_pct": 0,
                }

        fetched = await asyncio.gather(
            *[_fetch_one(s, n, g) for s, n, g in all_symbols]
        )
        results = dict(fetched)

        regime_state = await fetch_regime_state(request)

        vol_map = {
            "low_vol": "LOW",
            "normal_vol": "NORMAL",
            "elevated_vol": "HIGH",
            "high_vol": "HIGH",
            "crisis_vol": "CRISIS",
        }
        vol_label = vol_map.get(regime_state.volatility_regime, "NORMAL")
        trend_map = {
            "uptrend": "UPTREND",
            "downtrend": "DOWNTREND",
            "sideways": "SIDEWAYS",
        }
        trend_label = trend_map.get(regime_state.trend_regime, "SIDEWAYS")

        router_engine = request.app.state.regime_router
        mults = router_engine.get_strategy_multipliers(regime_state)
        strategies = [
            k.replace("_", "-").title()
            for k, v in sorted(mults.items(), key=lambda x: -x[1])
            if v >= 0.5
        ][:4]

        conf = regime_state.confidence
        risk_score = (
            max(0, min(100, int(conf * 100)))
            if isinstance(conf, (int, float)) and not math.isnan(conf)
            else 50
        )

        indices = [results[s] for s, _ in LIVE_INDICES if s in results]
        macro = [results[s] for s, _ in LIVE_MACRO if s in results]
        sectors = sorted(
            [results[s] for s, _ in LIVE_SECTORS if s in results],
            key=lambda x: x.get("change_pct", 0),
            reverse=True,
        )
        asia = [results[s] for s, _ in LIVE_ASIA if s in results]

        mode = (
            "PAPER"
            if getattr(request.app.state, "engine", None)
            and getattr(request.app.state.engine, "dry_run", True)
            else "LIVE"
        )

        result = sanitize_for_json(
            {
                "regime": {
                    "label": regime_state.regime,
                    "trend": trend_label,
                    "vol": vol_label,
                    "score": risk_score,
                    "strategies": strategies,
                    "should_trade": regime_state.should_trade,
                    "entropy": regime_state.entropy,
                    "size_scalar": regime_state.size_scalar,
                    "no_trade_reason": regime_state.no_trade_reason,
                },
                "indices": indices,
                "macro": macro,
                "sectors": sectors,
                "asia": asia,
                "trust": {
                    "mode": mode,
                    "source": "market_data_service",
                    "as_of": datetime.now(timezone.utc).isoformat() + "Z",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        overview_cache["data"] = result
        overview_cache["ts"] = time.time()
        return result
    except Exception as exc:
        logger.error("live_market error: %s", exc)
        return {
            "regime": {
                "label": "unknown",
                "trend": "SIDEWAYS",
                "vol": "NORMAL",
                "score": 50,
                "strategies": [],
                "should_trade": False,
                "entropy": None,
                "size_scalar": 1.0,
                "no_trade_reason": f"data unavailable: {exc}",
            },
            "indices": [],
            "macro": [],
            "sectors": [],
            "asia": [],
            "trust": {
                "mode": "PAPER",
                "source": "fallback",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
