"""Execution / IBKR readiness — deployability layer for PM dashboard."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


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
    try:
        from src.services.ibkr_service import (
            default_ibkr_port,
            get_ibkr_service,
            resolve_ibkr_host,
        )
        from src.services.ibkr_service import _socket_probe

        svc = get_ibkr_service()
        st = svc.status()
        ibkr_connected = bool(st.get("connected"))
        ibkr_mode = (st.get("mode") or ibkr_mode or "paper").lower()
        host = st.get("host") or resolve_ibkr_host(None)
        port = int(st.get("port") or default_ibkr_port(ibkr_mode))
        if gateway_reachable is None:
            gw_ok, _ = _socket_probe(host, port)
            gateway_reachable = gw_ok
        last_heartbeat = getattr(svc, "_last_heartbeat_ts", None)
        last_order_ok = getattr(svc, "_last_order_ok", None)
        last_order_fail = getattr(svc, "_last_order_fail", None)
        next_order_id = st.get("next_order_id")
    except Exception:
        host = ""
        port = 0
        gateway_reachable = bool(gateway_reachable)
        last_heartbeat = None
        last_order_ok = None
        last_order_fail = None
        next_order_id = None

    portfolio_synced = (portfolio_source or "").lower() == "ibkr" and ibkr_connected
    queue_healthy = ibkr_connected and not circuit_breaker and bool(next_order_id)
    trade_handoff_ready = ibkr_connected and bracket_ready and queue_healthy

    if circuit_breaker:
        readiness_label = "BLOCKED — circuit breaker"
        level = "blocked"
    elif trade_handoff_ready:
        readiness_label = f"Ready — {ibkr_mode.upper()} handoff"
        level = "ready"
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

    return {
        "broker_connected": ibkr_connected,
        "gateway_reachable": bool(gateway_reachable),
        "mode": ibkr_mode,
        "paper_or_live": "live" if ibkr_mode == "live" else "paper",
        "bracket_order_ready": bracket_ready,
        "trade_handoff_ready": trade_handoff_ready,
        "portfolio_synced": portfolio_synced,
        "portfolio_source": portfolio_source or "manual",
        "order_queue_healthy": queue_healthy,
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
        "evidence_badge": "live_broker" if ibkr_connected else "gateway_only" if gateway_reachable else "disconnected",
    }
