"""Execution / IBKR readiness — deployability layer for PM dashboard."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from src.services.ibkr_health import build_unified_labels


def build_execution_readiness(
    *,
    ibkr_connected: bool = False,
    ibkr_mode: str = "paper",
    bracket_ready: bool = False,
    portfolio_source: str = "manual",
    engine_running: bool = False,
    circuit_breaker: bool = False,
    gateway_reachable: Optional[bool] = None,
) -> Dict[str, Any]:
    """Full execution readiness object for Today / Playbook / cc-header."""
    health: Dict[str, Any] = {}
    diagnosis: Dict[str, Any] = {}
    socket_connected = False
    try:
        from src.services.ibkr_service import get_ibkr_service

        svc = get_ibkr_service()
        health = svc.build_health_state(bracket_ready=bracket_ready)
        st = svc.status()
        transport = svc.get_transport_snapshot()
        socket_connected = bool(st.get("socket_connected", st.get("connected")))
        session_usable = bool(st.get("session_usable") or health.get("session_usable"))
        ibkr_connected = session_usable or bool(st.get("connected"))
        ibkr_mode = (st.get("mode") or ibkr_mode or "paper").lower()
        host = st.get("host") or ""
        port = int(st.get("port") or 0)
        diagnosis = st.get("diagnosis") or transport.get("diagnosis") or {}
        if gateway_reachable is None:
            gateway_reachable = bool(
                diagnosis.get("gateway_reachable")
                or transport.get("gateway_reachable")
                or st.get("gateway_reachable")
            )
        last_heartbeat = getattr(svc, "_last_heartbeat_ts", None)
        last_order_ok = getattr(svc, "_last_order_ok", None)
        last_order_fail = getattr(svc, "_last_order_fail", None)
        next_order_id = st.get("next_order_id")
        if not isinstance(last_heartbeat, (int, float)):
            last_heartbeat = None
    except Exception:
        diagnosis = {}
        host = ""
        port = 0
        session_usable = bool(ibkr_connected)
        socket_connected = bool(ibkr_connected)
        gateway_reachable = bool(gateway_reachable)
        last_heartbeat = None
        last_order_ok = None
        last_order_fail = None
        next_order_id = None

    account_ok = health.get("account_status") == "ok"
    monitoring_only = health.get("handoff_status") == "monitoring_only"
    portfolio_synced = (portfolio_source or "").lower() == "ibkr" and ibkr_connected
    queue_healthy = ibkr_connected and not circuit_breaker and bool(next_order_id)
    trade_handoff_ready = (
        ibkr_connected
        and bracket_ready
        and queue_healthy
        and health.get("handoff_status") == "ready"
    )

    labels = build_unified_labels(
        health,
        ibkr_mode=ibkr_mode,
        circuit_breaker=circuit_breaker,
        trade_handoff_ready=trade_handoff_ready,
        gateway_reachable=bool(gateway_reachable),
        diagnosis=diagnosis if isinstance(diagnosis, dict) else None,
    )
    level = labels["level"]
    unified_label = labels["unified_label"]
    unified_short = labels["unified_short"]
    evidence_badge = labels["evidence_badge"]

    if circuit_breaker:
        readiness_label = "BLOCKED — circuit breaker"
    elif trade_handoff_ready:
        readiness_label = f"Ready — {ibkr_mode.upper()} handoff"
    elif monitoring_only or (ibkr_connected and account_ok):
        readiness_label = health.get("summary_label") or f"{ibkr_mode.upper()} · monitor / manual"
        level = "partial"
    elif ibkr_connected and bracket_ready:
        readiness_label = f"Connected — confirm {ibkr_mode.upper()} order"
        level = "partial"
    elif gateway_reachable and not ibkr_connected:
        readiness_label = "Gateway up — connect session"
        level = "partial"
    elif gateway_reachable:
        readiness_label = "Gateway reachable — not logged in"
        level = "partial"
    else:
        readiness_label = "Broker offline — paper signals only"
        level = "offline"

    sub_status = {
        "broker_transport": "up" if gateway_reachable else "down",
        "session_auth": "active" if ibkr_connected else "inactive",
        "engine": "on" if engine_running and not circuit_breaker else "off",
        "handoff_readiness": (
            "ready"
            if trade_handoff_ready
            else "monitoring" if monitoring_only else "blocked"
        ),
        "bracket_readiness": "ready" if bracket_ready else "draft",
        "market_data_farm": health.get("market_data_status") or "unknown",
        "secdef_farm": health.get("secdef_status") or "unknown",
        "hmds": health.get("hmds_status") or "unknown",
        "account_api": health.get("account_status") or "unknown",
    }

    return {
        "broker_connected": ibkr_connected,
        "ibkr_connected": ibkr_connected,
        "socket_connected": socket_connected,
        "session_usable": bool(health.get("session_usable") or ibkr_connected),
        "gateway_reachable": bool(gateway_reachable),
        "mode": ibkr_mode,
        "paper_or_live": "live" if ibkr_mode == "live" else "paper",
        "bracket_order_ready": bracket_ready,
        "bracket_ready": bracket_ready,
        "trade_handoff_ready": trade_handoff_ready,
        "monitoring_only": monitoring_only,
        "portfolio_synced": portfolio_synced,
        "portfolio_source": portfolio_source or "manual",
        "order_queue_healthy": queue_healthy,
        "can_send_order": trade_handoff_ready,
        "engine_running": engine_running,
        "circuit_breaker": circuit_breaker,
        "last_heartbeat": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_heartbeat))
            if last_heartbeat
            else None
        ),
        "last_order_ok": last_order_ok,
        "last_order_fail": last_order_fail,
        "next_order_id": next_order_id,
        "host": host,
        "port": port,
        "readiness_label": readiness_label,
        "level": level,
        "sub_status": sub_status,
        "unified_label": unified_label,
        "unified_short": unified_short,
        "evidence_badge": evidence_badge,
        "health": health,
        "health_label": health.get("summary_label"),
        "degraded_reasons": health.get("degraded_reasons") or [],
        "last_disconnect_at": health.get("last_disconnect_at"),
        "last_restore_at": health.get("last_restore_at"),
        "diagnosis": diagnosis if isinstance(diagnosis, dict) else {},
        "api_port_open": bool(
            (diagnosis or {}).get("api_port_open") if isinstance(diagnosis, dict) else False
        ),
    }
