"""IBKR connectivity diagnosis — distinguish UI login vs API session vs port/host/mode."""

from __future__ import annotations

import socket
import time
from typing import Any, Dict, List, Optional

# User-facing diagnosis codes (stable API for UI)
DIAG_HANDOFF_READY = "connected_handoff_ready"
DIAG_MONITORING = "connected_monitoring"
DIAG_CONNECTED_PARTIAL = "connected_partial"
DIAG_BRACKET_MISALIGNED = "bracket_not_aligned"
DIAG_HANDSHAKE_INCOMPLETE = "handshake_incomplete"
DIAG_SESSION_LOST = "session_lost"
DIAG_GATEWAY_UP_CONNECT = "gateway_port_open_need_connect"
DIAG_GATEWAY_UP_API_OFF = "gateway_port_open_api_disabled"
DIAG_API_PORT_UNREACHABLE = "api_port_unreachable"
DIAG_WRONG_HOST_DOCKER = "wrong_host_docker"
DIAG_MODE_PORT_MISMATCH = "mode_port_mismatch"
DIAG_CLIENT_ID_IN_USE = "client_id_in_use"
DIAG_TRUSTED_IP = "trusted_ip_blocked"
DIAG_IBAPI_MISSING = "ibapi_missing"

_PROBE_CACHE: Dict[tuple[str, int], tuple[float, bool]] = {}
_PROBE_TTL_S = 12.0

_MESSAGES: Dict[str, Dict[str, str]] = {
    DIAG_HANDOFF_READY: {
        "short": "READY",
        "label": "IBKR handoff ready — orders and bracket path verified",
        "hint": "Session is execution-ready for playbook handoff.",
    },
    DIAG_MONITORING: {
        "short": "MONITOR",
        "label": "IBKR connected — monitor / manual mode (not full handoff)",
        "hint": "Account API is up; confirm bracket and portfolio sync before live transmit.",
    },
    DIAG_CONNECTED_PARTIAL: {
        "short": "PARTIAL",
        "label": "IBKR session partial — connectivity or account still settling",
        "hint": "Wait for nextValidId and account summary, or refresh on the IBKR tab.",
    },
    DIAG_BRACKET_MISALIGNED: {
        "short": "PARTIAL",
        "label": "IBKR connected — bracket or portfolio gates not aligned",
        "hint": "Set stop/target on the bracket builder or reconcile broker vs local positions.",
    },
    DIAG_HANDSHAKE_INCOMPLETE: {
        "short": "HANDSHAKE",
        "label": "API socket reachable — IB handshake did not finish",
        "hint": "Click Connect on the IBKR tab; check API client ID and Trusted IPs in TWS/Gateway.",
    },
    DIAG_SESSION_LOST: {
        "short": "LOST",
        "label": "IBKR session lost — reconnect required",
        "hint": "TWS/Gateway may still be open; use Connect to restore the API session.",
    },
    DIAG_GATEWAY_UP_CONNECT: {
        "short": "LOGIN",
        "label": "Gateway port open — API session not started from this app",
        "hint": (
            "TWS/Gateway may show you as logged in, but this runtime has no API client. "
            "Open IBKR tab → Connect (enable Socket clients in TWS settings)."
        ),
    },
    DIAG_GATEWAY_UP_API_OFF: {
        "short": "API OFF",
        "label": "Gateway port closed or API socket disabled in TWS/Gateway",
        "hint": (
            "Enable Settings → API → Enable ActiveX and Socket Clients; set the correct "
            "paper (7497) or live (4001 Gateway / 7496 TWS) port."
        ),
    },
    DIAG_API_PORT_UNREACHABLE: {
        "short": "OFFLINE",
        "label": "Cannot reach IB API port — Gateway/TWS not listening",
        "hint": (
            "Start IB Gateway or TWS, confirm host and port, and allow localhost "
            "(or host.docker.internal from Docker)."
        ),
    },
    DIAG_WRONG_HOST_DOCKER: {
        "short": "HOST",
        "label": "Wrong host from Docker — use host.docker.internal not 127.0.0.1",
        "hint": (
            "The API port responds on host.docker.internal but not 127.0.0.1 inside "
            "the container. Set IBKR_HOST=host.docker.internal or connect using that host."
        ),
    },
    DIAG_MODE_PORT_MISMATCH: {
        "short": "PORT",
        "label": "Paper/live port mismatch — wrong socket for selected mode",
        "hint": (
            "Paper TWS defaults to 7497; live Gateway 4001; live TWS 7496. "
            "Match the mode toggle to the port configured in TWS/Gateway."
        ),
    },
    DIAG_CLIENT_ID_IN_USE: {
        "short": "CLIENT ID",
        "label": "IB API client ID already in use",
        "hint": "Close other API clients or change IBKR_CLIENT_ID to a free value (1–32).",
    },
    DIAG_TRUSTED_IP: {
        "short": "TRUST IP",
        "label": "Connection blocked — trusted IP / localhost permission",
        "hint": "In TWS/Gateway API settings, allow 127.0.0.1 and your Docker host IP.",
    },
    DIAG_IBAPI_MISSING: {
        "short": "NO IBAPI",
        "label": "ibapi package not installed in this runtime",
        "hint": "Install Interactive Brokers Python API (ibapi) in the server environment.",
    },
}


def probe_tcp_port(host: str, port: int, *, timeout: float = 2.0) -> bool:
    """Lightweight TCP reachability (cached). Does not complete an IB API handshake."""
    if not host or port <= 0:
        return False
    key = (host, port)
    now = time.time()
    cached = _PROBE_CACHE.get(key)
    if cached and (now - cached[0]) < _PROBE_TTL_S:
        return cached[1]
    ok = False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError:
        ok = False
    _PROBE_CACHE[key] = (now, ok)
    return ok


def clear_probe_cache() -> None:
    _PROBE_CACHE.clear()


def _mode_mismatch_detail(
    mode: str,
    expected_port: int,
    paper_port: int,
    live_ports: List[int],
    host: str,
) -> Optional[str]:
    expected_open = probe_tcp_port(host, expected_port)
    if expected_open:
        return None
    if mode == "paper":
        for lp in live_ports:
            if lp != expected_port and probe_tcp_port(host, lp):
                return f"live port {lp} is open but paper expects {expected_port}"
    else:
        if paper_port != expected_port and probe_tcp_port(host, paper_port):
            return f"paper port {paper_port} is open but live expects {expected_port}"
    return None


def _last_error_hints(last_error: Optional[dict]) -> tuple[Optional[str], str]:
    if not last_error:
        return None, ""
    detail = str(last_error.get("detail") or last_error.get("message") or "")
    code = last_error.get("code")
    text = detail
    if code is not None:
        text = f"{code}: {detail}"
    if "326" in text or "client id" in text.lower():
        return DIAG_CLIENT_ID_IN_USE, text
    if "162" in text or "trusted" in text.lower() or "127.0.0.1" in text.lower():
        return DIAG_TRUSTED_IP, text
    if "502" in text or "504" in text:
        return DIAG_GATEWAY_UP_API_OFF, text
    return None, text


def build_ibkr_diagnosis(
    *,
    mode: str = "paper",
    host: str = "127.0.0.1",
    port: int = 7497,
    docker: bool = False,
    ibapi_available: bool = True,
    socket_connected: bool = False,
    session_usable: bool = False,
    ib_api_ready: bool = False,
    account_loaded: bool = False,
    next_order_id: Optional[int] = None,
    monitoring_only: bool = False,
    trade_handoff_ready: bool = False,
    session_status: str = "inactive",
    bracket_status: str = "unavailable",
    bracket_enabled: bool = False,
    ib_handshake_started: bool = False,
    failed_handshake_count_1m: int = 0,
    last_error: Optional[dict] = None,
    paper_port: int = 7497,
    live_ports: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Classify broker state for CC header and IBKR tab."""
    live_ports = live_ports or [4001, 7496]
    mode = (mode or "paper").lower()
    host = (host or "127.0.0.1").strip()

    err_code, err_detail = _last_error_hints(last_error)

    api_port_open = probe_tcp_port(host, port)
    docker_alt_reachable = False
    if docker and host in {"127.0.0.1", "localhost", "::1"}:
        docker_alt_reachable = probe_tcp_port("host.docker.internal", port)

    mode_mismatch = _mode_mismatch_detail(mode, port, paper_port, live_ports, host)

    gateway_reachable = bool(
        api_port_open
        or docker_alt_reachable
        or socket_connected
        or session_usable
        or ib_api_ready
    )

    code = DIAG_API_PORT_UNREACHABLE
    if not ibapi_available:
        code = DIAG_IBAPI_MISSING
    elif trade_handoff_ready:
        code = DIAG_HANDOFF_READY
    elif session_status == "lost":
        code = DIAG_SESSION_LOST
    elif session_usable and monitoring_only:
        code = DIAG_MONITORING
    elif session_usable or (socket_connected and account_loaded):
        if bracket_enabled and bracket_status not in ("ready",):
            code = DIAG_BRACKET_MISALIGNED
        elif trade_handoff_ready:
            code = DIAG_HANDOFF_READY
        else:
            code = DIAG_MONITORING if monitoring_only else DIAG_CONNECTED_PARTIAL
    elif socket_connected or ib_api_ready:
        if next_order_id is None:
            code = DIAG_HANDSHAKE_INCOMPLETE
        else:
            code = DIAG_CONNECTED_PARTIAL
    elif err_code:
        code = err_code
    elif ib_handshake_started or failed_handshake_count_1m > 0:
        code = DIAG_HANDSHAKE_INCOMPLETE
    elif docker_alt_reachable and not api_port_open:
        code = DIAG_WRONG_HOST_DOCKER
    elif mode_mismatch:
        code = DIAG_MODE_PORT_MISMATCH
    elif api_port_open:
        code = DIAG_GATEWAY_UP_CONNECT
    elif failed_handshake_count_1m > 0 and not api_port_open:
        code = DIAG_GATEWAY_UP_API_OFF
    else:
        code = DIAG_API_PORT_UNREACHABLE

    meta = dict(_MESSAGES.get(code, _MESSAGES[DIAG_API_PORT_UNREACHABLE]))
    if mode_mismatch and code == DIAG_MODE_PORT_MISMATCH:
        meta["label"] = f"Port mismatch — {mode_mismatch}"
        meta["hint"] = (
            f"{meta['hint']} Detected: {mode_mismatch} on {host}."
        )
    if err_detail and code in (
        DIAG_HANDSHAKE_INCOMPLETE,
        DIAG_CLIENT_ID_IN_USE,
        DIAG_TRUSTED_IP,
        DIAG_GATEWAY_UP_API_OFF,
    ):
        meta["detail"] = err_detail

    return {
        "code": code,
        "short": meta["short"],
        "label": meta["label"],
        "hint": meta["hint"],
        "detail": meta.get("detail") or err_detail or None,
        "api_port_open": api_port_open,
        "gateway_reachable": gateway_reachable,
        "docker_alt_reachable": docker_alt_reachable,
        "mode_mismatch": mode_mismatch,
        "expected_host": host,
        "expected_port": port,
        "mode": mode,
    }
