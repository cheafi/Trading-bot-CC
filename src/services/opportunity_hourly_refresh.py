"""Hourly opportunity refresh — cached ranked board + delta alerts (non-blocking)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 50
_REFRESH_LOCK = asyncio.Lock()
_LAST_RUN_TS = 0.0
_LAST_RESULT: Dict[str, Any] = {}


async def run_opportunity_refresh(
    *,
    limit: int = _DEFAULT_LIMIT,
    scan_fn: Any = None,
    notify: bool = True,
    source: str = "hourly_refresh",
) -> Dict[str, Any]:
    """
    Refresh Playbook ranked cache and optionally fire Telegram delta alerts.

    Safe to call from scheduler or API background loop — uses module lock.
    """
    global _LAST_RUN_TS, _LAST_RESULT
    from src.api.routers.playbook import (
        _compute_ranked_live,
        _finalize_ranked_response,
        _ranked_cache_key,
        _set_ranked_cached,
    )
    from src.services.playbook_board_fallback import save_playbook_snapshot

    async with _REFRESH_LOCK:
        t0 = time.time()
        meta: Dict[str, Any] = {
            "ok": False,
            "source": source,
            "limit": limit,
            "elapsed_ms": 0,
        }
        try:
            cache_key = _ranked_cache_key(limit, None, None)
            response = await _compute_ranked_live(limit, None, None, scan_fn=scan_fn)
            response = _finalize_ranked_response(
                response, from_live=True, limit=limit, action=None, sector=None
            )
            _set_ranked_cached(cache_key, response)
            save_playbook_snapshot(response, cache_key)
            if notify:
                try:
                    from src.services.opportunity_telegram_alerts import (
                        notify_live_playbook_scan,
                    )

                    alert_meta = notify_live_playbook_scan(response, source=source)
                    meta["alerts"] = alert_meta
                except Exception as exc:
                    logger.debug("hourly refresh telegram notify skipped: %s", exc)
            meta.update(
                {
                    "ok": True,
                    "opportunities": len(response.get("opportunities") or []),
                    "near_miss": len(response.get("near_miss") or []),
                    "watch_qualified": int(
                        (response.get("filter_funnel") or {}).get("watch_qualified_setups")
                        or 0
                    ),
                    "deploy_qualified": int(
                        (response.get("filter_funnel") or {}).get("deploy_qualified_setups")
                        or 0
                    ),
                    "board_mode": response.get("board_mode"),
                }
            )
            _LAST_RUN_TS = time.time()
            _LAST_RESULT = meta
            logger.info(
                "[OpportunityRefresh] %s — %d opps, %d near-miss, %d watch-qualified",
                source,
                meta["opportunities"],
                meta["near_miss"],
                meta["watch_qualified"],
            )
        except Exception as exc:
            meta["error"] = str(exc)[:200]
            logger.warning("[OpportunityRefresh] failed (%s): %s", source, exc)
        meta["elapsed_ms"] = int((time.time() - t0) * 1000)
        return meta


def last_refresh_meta() -> Dict[str, Any]:
    return {
        "last_run_ts": _LAST_RUN_TS,
        "last_result": dict(_LAST_RESULT),
    }


async def opportunity_hourly_loop(
    app: Any,
    *,
    interval_seconds: int = 3600,
    limit: int = _DEFAULT_LIMIT,
) -> None:
    """Background loop for API-only deployments — hourly refresh during market hours."""
    await asyncio.sleep(120)
    while True:
        try:
            from src.api.main import _is_market_open

            if _is_market_open():
                scan_fn = getattr(getattr(app, "state", None), "scan_signals", None)
                await run_opportunity_refresh(
                    limit=limit,
                    scan_fn=scan_fn,
                    notify=True,
                    source="api_hourly_loop",
                )
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[OpportunityRefresh] loop error: %s", exc)
            await asyncio.sleep(300)
