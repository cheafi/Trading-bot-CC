"""Clarity Console header — single poll for top-bar status pills."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from src.api.app_state import get_engine
from src.api.deps import optional_api_key, sanitize_for_json
from src.api.routers.brief_regenerate import _latest_brief
from src.core.config import get_settings
from src.services.ibkr_service import get_ibkr_service
from src.services.surface_authority import header_summary_for_tab, resolve_surface_mode

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
            import asyncio

            hc = await asyncio.wait_for(engine.health_check(), timeout=5.0)
            broker_ok = broker_ok or bool((hc.get("components") or {}).get("broker"))
        except asyncio.TimeoutError:
            logger.debug("cc-header broker probe timed out")
        except Exception as exc:
            logger.debug("cc-header broker probe failed: %s", exc)
    try:
        ibkr_probe = get_ibkr_service().status()
        if ibkr_probe.get("gateway_reachable") or ibkr_probe.get("session_usable") or ibkr_probe.get("connected"):
            broker_ok = True
    except Exception as exc:
        logger.debug("cc-header ibkr broker probe failed: %s", exc)
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


def _cached_today_payload() -> Dict[str, Any] | None:
    try:
        from src.api.routers.decision import _today_cache

        if _today_cache and isinstance(_today_cache, dict):
            return _today_cache
    except Exception as exc:
        logger.debug("cc-header today cache unavailable: %s", exc)
    return None


def _page_authority_mode(
    *,
    decision_authority: Dict[str, Any] | None,
    engine_running: bool,
    circuit_breaker: bool,
) -> str:
    if circuit_breaker or not engine_running:
        return "diagnostic"
    da = decision_authority or {}
    if da.get("source") == "fallback_brief" or (da.get("gates") or {}).get(
        "fallback_brief"
    ):
        return "fallback_board"
    if da.get("degraded") or da.get("gates_active"):
        return "degraded_board"
    return "active"


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
async def cc_header(
    request: Request,
    tab: Optional[str] = Query(None, description="Active UI tab for surface-aware header"),
    _=optional_api_key,
):
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
    ibkr_st["health_label"] = (
        (ibkr_st.get("diagnosis") or {}).get("label")
        or ibkr_st.get("health_label")
        or (ibkr_st.get("health") or {}).get("summary_label")
    )
    ibkr_st["health_label_short"] = (ibkr_st.get("diagnosis") or {}).get("short")

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

    today = _cached_today_payload()
    decision_authority = (today or {}).get("decision_authority")
    tradeability = "WAIT"
    should_trade = True
    if today:
        regime = today.get("market_regime") or {}
        tradeability = str(
            regime.get("tradeability")
            or (today.get("decision_model") or {}).get("honest_tradeability")
            or "WAIT"
        )
        should_trade = bool(regime.get("should_trade", True))

    if not decision_authority:
        from src.services.decision_truth_model import build_decision_authority

        data_stale = pills["data"] in ("STALE", "CRITICAL")
        brief_stale = pills["brief"] in ("STALE", "CRITICAL")
        ibkr_connected = bool(
            ibkr_st.get("session_usable") or ibkr_st.get("connected")
        )
        decision_authority = build_decision_authority(
            tradeability=tradeability,
            should_trade=should_trade,
            data_stale=data_stale,
            fallback_brief=brief_stale,
            broker_offline=not ibkr_connected,
            engine_off=not eng["running"],
            exec_blocked=bool(eng.get("circuit_breaker")),
            trust_source="cc-header",
        )

    page_authority_mode = _page_authority_mode(
        decision_authority=decision_authority,
        engine_running=bool(eng["running"]),
        circuit_breaker=bool(eng["circuit_breaker"]),
    )

    ibkr_connected = bool(ibkr_st.get("session_usable") or ibkr_st.get("connected"))
    portfolio_context: Dict[str, Any]
    try:
        from src.api.routers.portfolio import portfolio_header_snapshot_for_cc

        portfolio_context = portfolio_header_snapshot_for_cc(ibkr_connected=ibkr_connected)
    except Exception as exc:
        logger.debug("cc-header portfolio snapshot failed: %s", exc)
        portfolio_context = {
            "mode": "portfolio",
            "book_label": "Manual book",
            "position_count": 0,
            "positions_label": "No positions",
            "broker_sync": "unavailable" if not ibkr_connected else "ok",
            "broker_sync_label": (
                "Broker sync unavailable"
                if not ibkr_connected
                else "Broker linked"
            ),
            "rebalance_only": True,
            "rebalance_label": "Rebalance support only",
            "source": "manual",
        }

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
            "decision_authority": decision_authority,
            "page_authority_mode": page_authority_mode,
            "portfolio_context": portfolio_context,
            "surface_mode": resolve_surface_mode(tab) if tab else None,
            "header_summary": header_summary_for_tab(
                tab,
                {
                    "tradeability": tradeability,
                    "regime_trend": (today or {}).get("market_regime", {}).get("trend"),
                    "execution_blocked": bool(eng["circuit_breaker"])
                    or not ibkr_connected,
                    "stale": pills["data"] in ("STALE", "CRITICAL"),
                    "fallback": page_authority_mode == "fallback_board",
                    "position_count": portfolio_context.get("position_count"),
                    "ibkr_label": ibkr_st.get("health_label") or "IBKR",
                },
            )
            if tab
            else None,
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
