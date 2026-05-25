"""Clarity Console header — single poll for top-bar status pills."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.api.app_state import get_engine
from src.api.deps import optional_api_key, sanitize_for_json
from src.api.routers.brief_regenerate import _latest_brief
from src.api.routers.ibkr import _gateway_port_open
from src.core.config import get_settings
from src.services.ibkr_service import default_ibkr_port, get_ibkr_service, resolve_ibkr_host

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ops"])


async def _provider_components(
    request: Request, engine, freshness: Dict[str, Any] | None
) -> Dict[str, bool]:
    """Health flags for Ops → Data Providers (independent of engine.running)."""
    components: Dict[str, bool] = {}

    md_ok = False
    if freshness:
        streams = freshness.get("streams") or []
        md_ok = freshness.get("worst_tier") == "FRESH" or any(
            s.get("ok") for s in streams
        )
    if not md_ok:
        try:
            q = await request.app.state.market_data.get_quote("SPY")
            md_ok = bool(q and q.get("price"))
        except Exception as exc:
            logger.debug("cc-header market_data probe failed: %s", exc)
    components["market_data"] = md_ok

    regime_ok = False
    try:
        rr = getattr(request.app.state, "regime_router", None)
        if rr is not None:
            cache = getattr(request.app.state, "regime_cache", None)
            if cache is not None:
                regime_ok = True
            else:
                mkt = await request.app.state.market_data.get_market_state()
                st = rr.classify(mkt)
                regime_ok = st is not None
                if regime_ok:
                    import time as _time

                    request.app.state.regime_cache = st
                    request.app.state.regime_cache_ts = _time.monotonic()
    except Exception as exc:
        logger.debug("cc-header regime probe failed: %s", exc)
        regime_ok = getattr(request.app.state, "regime_router", None) is not None
    components["regime_router"] = regime_ok

    settings = get_settings()
    broker_ok = bool(settings.alpaca_api_key and settings.alpaca_secret_key)
    if engine:
        try:
            hc = await engine.health_check()
            broker_ok = broker_ok or bool((hc.get("components") or {}).get("broker"))
        except Exception as exc:
            logger.debug("cc-header broker probe failed: %s", exc)
    components["broker"] = broker_ok

    if engine:
        try:
            hc = await engine.health_check()
            for name, ok in (hc.get("components") or {}).items():
                if name not in components:
                    components[name] = bool(ok)
        except Exception:
            pass

    return components


def _engine_snapshot(engine) -> Dict[str, Any]:
    if not engine:
        return {
            "running": False,
            "dry_run": True,
            "circuit_breaker": False,
            "circuit_breaker_reason": "",
        }
    return {
        "running": bool(getattr(engine, "_running", False)),
        "dry_run": bool(getattr(engine, "dry_run", True)),
        "circuit_breaker": bool(getattr(engine, "circuit_breaker_triggered", False)),
        "circuit_breaker_reason": str(
            getattr(engine, "circuit_breaker_reason", "") or ""
        ),
    }


@router.get("/api/ops/cc-header")
async def cc_header(request: Request, _=optional_api_key):
    """Aggregate status for CC top bar (mode, data, brief, alerts, IBKR)."""
    from src.services.data_freshness_service import freshness_report

    now = datetime.now(timezone.utc)
    settings = get_settings()
    engine = get_engine(request.app)
    eng = _engine_snapshot(engine)

    trust_mode = "PAPER" if eng["dry_run"] else "LIVE"
    display_mode = (
        "LIVE"
        if not eng["dry_run"]
        else ("PAPER" if eng["running"] else trust_mode)
    )

    freshness = None
    try:
        mds = request.app.state.market_data
        freshness = await freshness_report(mds)
    except Exception as exc:
        logger.debug("cc-header freshness failed: %s", exc)

    brief = {"ok": True, "latest": _latest_brief()}
    alerts: Dict[str, Any] = {"count": 0, "by_severity": {}}
    try:
        from src.api.routers.position_alerts import portfolio_risk_alerts

        alerts = await portfolio_risk_alerts(request, _=None)
    except Exception as exc:
        logger.debug("cc-header alerts failed: %s", exc)

    ibkr_st = get_ibkr_service().status()
    host = ibkr_st.get("host") or resolve_ibkr_host(None)
    port = int(ibkr_st.get("port") or default_ibkr_port(ibkr_st.get("mode") or "paper"))
    ibkr_st["gateway_reachable"] = _gateway_port_open(host, port)

    components = await _provider_components(request, engine, freshness)
    alpaca_configured = bool(settings.alpaca_api_key and settings.alpaca_secret_key)

    pills = {
        "data": (freshness or {}).get("worst_tier", "FRESH"),
        "brief": (brief.get("latest") or {}).get("tier", "FRESH"),
        "alerts": int(alerts.get("count") or 0),
    }
    healthy = (
        display_mode in ("PAPER", "LIVE")
        and pills["data"] == "FRESH"
        and pills["brief"] == "FRESH"
        and pills["alerts"] == 0
        and not eng["circuit_breaker"]
    )

    return sanitize_for_json(
        {
            "as_of": now.isoformat() + "Z",
            "healthy": healthy,
            "display_mode": display_mode,
            "trust_mode": trust_mode,
            "engine": eng,
            "freshness": freshness,
            "brief_status": brief,
            "risk_alerts": alerts,
            "ibkr": ibkr_st,
            "pills": pills,
            "components": components,
            "providers": {
                "yfinance": components.get("market_data", False),
                "regime_router": components.get("regime_router", False),
                "alpaca": {
                    "configured": alpaca_configured,
                    "connected": components.get("broker", False),
                    "paper": bool(settings.alpaca_paper),
                },
            },
        }
    )
