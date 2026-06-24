"""
IBKR Service — async wrapper around ibapi EClient/EWrapper
Supports: paper (port 7497) and live (port 7496) via IB Gateway / TWS
Thread model: ibapi runs its own reader thread; we bridge to asyncio via asyncio.Queue
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

ConnectSource = Literal[
    "ops_probe",
    "ibkr_page",
    "account_sync",
    "readiness_check",
    "dossier_worker",
    "manual_test",
    "reconnect_loop",
    "status_poll",
]

_RECONNECT_BACKOFF_S = (1.0, 2.0, 5.0, 10.0, 30.0)
_ACCOUNT_ACTIVITY_WINDOW_S = 120.0

logger = logging.getLogger(__name__)


def _running_in_docker() -> bool:
    return os.path.exists("/.dockerenv") or os.getenv(
        "RUNNING_IN_DOCKER", ""
    ).lower() in {
        "1",
        "true",
        "yes",
    }


def _env_int(*keys: str, default: int) -> int:
    for key in keys:
        value = os.getenv(key)
        if value:
            try:
                return int(value)
            except ValueError:
                logger.warning("[IBKR] Ignoring invalid integer env %s=%r", key, value)
    return default


def _default_host() -> str:
    configured = os.getenv("IBKR_HOST") or os.getenv("IB_HOST")
    if configured:
        return configured
    return "host.docker.internal" if _running_in_docker() else "127.0.0.1"


def _normalize_host(host: Optional[str]) -> str:
    value = (host or "").strip() or _default_host()
    if _running_in_docker() and value in {"127.0.0.1", "localhost", "::1"}:
        return _default_host()
    return value


def resolve_ibkr_host(host: Optional[str] = None) -> str:
    return _normalize_host(host)


def default_ibkr_port(mode: str) -> int:
    return IBKRService.PAPER_PORT if mode == "paper" else IBKRService.LIVE_PORT


# ── ibapi imports (installed via direct copy to site-packages) ──────────────
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.common import OrderId, TickAttrib, TickerId

    IBAPI_AVAILABLE = True
except ImportError:
    IBAPI_AVAILABLE = False
    logger.info("[IBKR] ibapi not available — service will return stub responses")

    class EWrapper:  # type: ignore[no-redef]
        pass

    class EClient:  # type: ignore[no-redef]
        def isConnected(self) -> bool:
            return False

    Contract = None  # type: ignore[assignment]
    Order = None  # type: ignore[assignment]
    OrderId = int  # type: ignore[assignment]
    TickAttrib = Any  # type: ignore[assignment]
    TickerId = int  # type: ignore[assignment]


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class AccountSummary:
    account: str = ""
    net_liquidation: float = 0.0
    cash_balance: float = 0.0
    buying_power: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    gross_position_value: float = 0.0
    init_margin_req: float = 0.0
    maint_margin_req: float = 0.0
    available_funds: float = 0.0
    currency: str = "USD"


@dataclass
class Position:
    account: str = ""
    symbol: str = ""
    sec_type: str = ""
    exchange: str = ""
    currency: str = ""
    position: float = 0.0
    avg_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class OrderResult:
    order_id: int = 0
    status: str = ""
    filled: float = 0.0
    remaining: float = 0.0
    avg_fill_price: float = 0.0
    error: Optional[str] = None


# IB informational codes — update health subsystems, not hard failures.
_IB_INFO_CODES = frozenset({1100, 1102, 2103, 2104, 2105, 2106, 2107, 2108, 2109, 2110, 2119, 2157, 2158})


@dataclass
class IBKRHealthState:
    """Institutional-grade broker health — partial degraded states, not binary."""

    session_status: str = "inactive"
    account_status: str = "unknown"
    market_data_status: str = "unknown"
    secdef_status: str = "unknown"
    hmds_status: str = "unknown"
    execution_status: str = "unavailable"
    handoff_status: str = "blocked"
    last_disconnect_at: Optional[str] = None
    last_restore_at: Optional[str] = None
    degraded_reasons: list[str] = field(default_factory=list)
    _recent_incidents: list[dict[str, Any]] = field(default_factory=list)

    def apply_ib_code(self, code: int, msg: str = "") -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        detail = (msg or "").strip()
        incident = {"code": code, "message": detail, "at": ts}
        if code == 1100:
            self.session_status = "lost"
            self.last_disconnect_at = ts
            self._push_incident("session_lost", incident)
            if detail and detail not in self.degraded_reasons:
                self.degraded_reasons.append(detail or "Connectivity lost (1100)")
        elif code == 1102:
            self.session_status = "restored_data_maintained"
            self.last_restore_at = ts
            self._push_incident("session_restored_data_maintained", incident)
        elif code == 2103:
            self.market_data_status = "degraded"
            self._push_incident("market_data_degraded", incident)
        elif code == 2104:
            self.market_data_status = "ok"
        elif code == 2157:
            self.secdef_status = "degraded"
            self._push_incident("secdef_degraded", incident)
        elif code == 2158:
            self.secdef_status = "ok"
        elif code == 2106:
            self.hmds_status = "ok"
        elif code == 2107:
            # Dormant HMDS is normal idle state — never treat as fatal.
            self.hmds_status = "dormant"
        elif code in {2105, 2108}:
            self.market_data_status = "degraded"
        elif code in {2109, 2110}:
            self.hmds_status = "degraded"

    def _push_incident(self, kind: str, incident: dict[str, Any]) -> None:
        row = {**incident, "kind": kind}
        self._recent_incidents.insert(0, row)
        self._recent_incidents = self._recent_incidents[:20]

    def note_account_ok(self) -> None:
        self.account_status = "ok"

    def note_account_stale(self) -> None:
        if self.account_status == "ok":
            self.account_status = "stale"

    def refresh_derived(
        self,
        *,
        socket_connected: bool,
        authenticated: bool,
        account_loaded: bool,
        bracket_ready: bool = False,
    ) -> None:
        if socket_connected and authenticated:
            if self.session_status in ("inactive", "lost"):
                self.session_status = "connected"
        elif not socket_connected:
            if self.session_status not in ("lost", "restored_data_maintained"):
                self.session_status = "inactive"

        if account_loaded:
            self.account_status = "ok"
        elif socket_connected and authenticated and self.account_status == "unknown":
            self.account_status = "stale"

        if authenticated and bool(socket_connected):
            self.execution_status = "ready"
        elif socket_connected:
            self.execution_status = "not_ready"
        else:
            self.execution_status = "unavailable"

        session_usable = self.session_status in (
            "connected",
            "restored_data_maintained",
        ) or self.account_status == "ok"
        farms_ok = (
            self.market_data_status != "degraded"
            and self.secdef_status != "degraded"
            and self.hmds_status not in ("degraded",)
        )

        if self.execution_status == "ready" and bracket_ready and farms_ok:
            self.handoff_status = "ready"
        elif session_usable and self.account_status == "ok":
            self.handoff_status = "monitoring_only"
        else:
            self.handoff_status = "blocked"

        self._rebuild_degraded_reasons()

    def _rebuild_degraded_reasons(self) -> None:
        reasons: list[str] = []
        if self.session_status == "lost":
            reasons.append("Session connectivity lost (1100)")
        if self.market_data_status == "degraded":
            reasons.append("Market data farm degraded (2103)")
        if self.secdef_status == "degraded":
            reasons.append("Sec-def data farm degraded (2157)")
        if self.hmds_status == "dormant":
            reasons.append("HMDS dormant — idle, not an error (2107)")
        elif self.hmds_status == "degraded":
            reasons.append("HMDS data farm degraded")
        if self.execution_status == "not_ready":
            reasons.append("Execution path not ready — waiting for order queue")
        if self.account_status == "stale":
            reasons.append("Account summary stale — refresh recommended")
        elif self.account_status == "unknown" and self.session_status != "inactive":
            reasons.append("Account API not verified this session")
        self.degraded_reasons = reasons

    def session_usable(self) -> bool:
        return self.session_status in (
            "connected",
            "restored_data_maintained",
        ) or self.account_status == "ok"

    def summary_label(self) -> str:
        if self.handoff_status == "ready":
            return "Execution ready — full handoff"
        if not self.session_usable():
            if self.session_status == "lost":
                return "Session lost — reconnect required"
            return "Broker offline — monitoring unavailable"
        parts: list[str] = []
        if self.session_status == "restored_data_maintained":
            parts.append("Session restored")
        elif self.session_status == "connected":
            parts.append("Session active")
        if self.account_status == "ok":
            parts.append("Account API OK")
        if self.market_data_status == "degraded":
            parts.append("Market data degraded")
        elif self.market_data_status == "ok":
            parts.append("Market data OK")
        if self.secdef_status == "degraded":
            parts.append("Sec-def degraded")
        elif self.secdef_status == "ok":
            parts.append("Sec-def OK")
        if self.hmds_status == "dormant":
            parts.append("HMDS dormant")
        elif self.hmds_status == "ok":
            parts.append("HMDS OK")
        elif self.hmds_status == "degraded":
            parts.append("HMDS degraded")
        if self.handoff_status == "monitoring_only":
            if self.execution_status == "ready":
                parts.append(
                    "Execution path available · monitor / manual mode"
                )
            else:
                parts.append("Technically connected, operationally partial")
        elif self.execution_status == "ready":
            parts.append("Order routing ready")
        elif self.execution_status == "not_ready":
            parts.append("Order routing pending")
        return ", ".join(parts) if parts else "Broker status unknown"

    def to_dict(self, *, transport: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = {
            "session_status": self.session_status,
            "account_status": self.account_status,
            "market_data_status": self.market_data_status,
            "secdef_status": self.secdef_status,
            "hmds_status": self.hmds_status,
            "execution_status": self.execution_status,
            "handoff_status": self.handoff_status,
            "last_disconnect_at": self.last_disconnect_at,
            "last_restore_at": self.last_restore_at,
            "degraded_reasons": list(self.degraded_reasons),
            "summary_label": self.summary_label(),
            "session_usable": self.session_usable(),
            "session_operational": self.session_usable(),
            "recent_incidents": self._recent_incidents[:8],
        }
        if transport:
            payload.update(transport)
        return payload


@dataclass
class IBKRSessionRuntime:
    """Single owner transport state — never inferred from raw TCP health probes."""

    socket_accepts_tcp: bool = False
    ib_handshake_started: bool = False
    ib_handshake_completed: bool = False
    ib_api_ready: bool = False
    connect_attempt_source: Optional[str] = None
    last_failed_handshake_at: Optional[float] = None
    _failed_handshake_times: list[float] = field(default_factory=list)

    def record_failed_handshake(self) -> None:
        now = time.time()
        self.last_failed_handshake_at = now
        self._failed_handshake_times.append(now)
        cutoff = now - 60.0
        self._failed_handshake_times = [
            ts for ts in self._failed_handshake_times if ts >= cutoff
        ]
        self.ib_handshake_started = False
        self.ib_handshake_completed = False
        self.ib_api_ready = False

    @property
    def failed_handshake_count_1m(self) -> int:
        cutoff = time.time() - 60.0
        return sum(1 for ts in self._failed_handshake_times if ts >= cutoff)

    def on_handshake_start(self, source: Optional[str]) -> None:
        self.connect_attempt_source = source
        self.ib_handshake_started = True
        self.ib_handshake_completed = False
        self.ib_api_ready = False

    def on_connect_ack(self) -> None:
        self.socket_accepts_tcp = True

    def on_next_valid_id(self) -> None:
        self.ib_handshake_completed = True
        self.ib_api_ready = True

    def on_session_closed(self) -> None:
        self.socket_accepts_tcp = False
        self.ib_handshake_started = False
        self.ib_handshake_completed = False
        self.ib_api_ready = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "socket_accepts_tcp": self.socket_accepts_tcp,
            "ib_handshake_started": self.ib_handshake_started,
            "ib_handshake_completed": self.ib_handshake_completed,
            "ib_api_ready": self.ib_api_ready,
            "connect_attempt_source": self.connect_attempt_source,
            "last_failed_handshake_at": (
                time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_failed_handshake_at)
                )
                if self.last_failed_handshake_at
                else None
            ),
            "failed_handshake_count_1m": self.failed_handshake_count_1m,
        }


def derive_gateway_reachable(
    *,
    ib_api_ready: bool,
    socket_connected: bool,
    session_usable: bool,
    account_loaded_at: Optional[float],
    api_port_open: bool = False,
) -> bool:
    """Gateway up if API session is active or the configured socket port accepts TCP."""
    if ib_api_ready or socket_connected or session_usable:
        return True
    if account_loaded_at is not None:
        if (time.time() - account_loaded_at) <= _ACCOUNT_ACTIVITY_WINDOW_S:
            return True
    if api_port_open:
        return True
    return False


# ── EWrapper + EClient combined class ────────────────────────────────────────


class _IBKRApp(EWrapper, EClient):  # type: ignore[misc]
    """
    Minimal EWrapper implementation — bridges ibapi callbacks → asyncio.Queue.
    Never call blocking methods from the main asyncio event loop.
    """

    def __init__(self):
        if not IBAPI_AVAILABLE:
            self._connected = False
            self._session_closed = False
            self._next_order_id = None
            self._account_q = asyncio.Queue()
            self._position_q = asyncio.Queue()
            self._order_status_q = asyncio.Queue()
            self._error_q = asyncio.Queue()
            self._open_orders_q = asyncio.Queue()
            self._open_orders: dict[int, dict] = {}
            self._account_data = {}
            self._positions = {}
            self._loop = None
            self._recent_fills: list[dict] = []
            return
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self._connected = False
        self._session_closed = False
        self._next_order_id: Optional[int] = None

        # Queues for async consumers
        self._account_q: asyncio.Queue = asyncio.Queue()
        self._position_q: asyncio.Queue = asyncio.Queue()
        self._order_status_q: asyncio.Queue = asyncio.Queue()
        self._error_q: asyncio.Queue = asyncio.Queue()
        self._open_orders_q: asyncio.Queue = asyncio.Queue()

        # Collected state
        self._account_data: dict[str, str] = {}
        self._positions: dict[str, Position] = {}
        # Open orders accumulated between openOrder callbacks and openOrderEnd
        self._open_orders: dict[int, dict] = {}

        # Event loop reference — set after connection
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._recent_fills: list[dict] = []
        self._on_ib_event: Optional[Callable[..., None]] = None

    def isConnected(self) -> bool:
        return bool(IBAPI_AVAILABLE and EClient.isConnected(self))

    # ── Connection callbacks ──────────────────────────────────────────────────

    def connectAck(self):
        self._connected = True
        self._session_closed = False
        logger.info("[IBKR] connectAck — connected to IB Gateway")
        if self._on_ib_event:
            self._on_ib_event(kind="connect_ack")

    def connectionClosed(self):
        self._connected = False
        self._session_closed = True
        logger.warning("[IBKR] connectionClosed")
        if self._on_ib_event:
            self._on_ib_event(kind="connection_closed")

    def nextValidId(self, orderId: int):
        self._next_order_id = orderId
        logger.info(f"[IBKR] nextValidId={orderId}")
        if self._on_ib_event:
            self._on_ib_event(kind="next_valid_id")

    # ── Account summary callbacks ─────────────────────────────────────────────

    def accountSummary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ):
        self._account_data[tag] = value
        if tag == "Currency":
            self._account_data["_currency"] = currency

    def accountSummaryEnd(self, reqId: int):
        summary = AccountSummary(
            account=self._account_data.get("AccountCode", ""),
            net_liquidation=float(self._account_data.get("NetLiquidation", 0) or 0),
            cash_balance=float(self._account_data.get("TotalCashValue", 0) or 0),
            buying_power=float(self._account_data.get("BuyingPower", 0) or 0),
            unrealized_pnl=float(self._account_data.get("UnrealizedPnL", 0) or 0),
            realized_pnl=float(self._account_data.get("RealizedPnL", 0) or 0),
            gross_position_value=float(
                self._account_data.get("GrossPositionValue", 0) or 0
            ),
            init_margin_req=float(self._account_data.get("InitMarginReq", 0) or 0),
            maint_margin_req=float(self._account_data.get("MaintMarginReq", 0) or 0),
            available_funds=float(self._account_data.get("AvailableFunds", 0) or 0),
            currency=self._account_data.get("_currency", "USD"),
        )
        if self._loop:
            self._loop.call_soon_threadsafe(self._account_q.put_nowait, summary)

    # ── Position callbacks ────────────────────────────────────────────────────

    def position(self, account: str, contract: Any, position: float, avgCost: float):
        key = f"{contract.symbol}_{contract.secType}"
        self._positions[key] = Position(
            account=account,
            symbol=contract.symbol,
            sec_type=contract.secType,
            exchange=contract.exchange,
            currency=contract.currency,
            position=position,
            avg_cost=avgCost,
        )

    def positionEnd(self):
        positions = list(self._positions.values())
        if self._loop:
            self._loop.call_soon_threadsafe(self._position_q.put_nowait, positions)

    # ── Order status callbacks ────────────────────────────────────────────────

    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ):
        result = OrderResult(
            order_id=orderId,
            status=status,
            filled=filled,
            remaining=remaining,
            avg_fill_price=avgFillPrice,
        )
        if self._loop:
            self._loop.call_soon_threadsafe(self._order_status_q.put_nowait, result)
        logger.info(
            f"[IBKR] orderStatus orderId={orderId} status={status} filled={filled}"
        )
        # Mirror status into open-orders cache so polling reflects live state
        existing = self._open_orders.get(orderId)
        if existing is not None:
            existing["status"] = status
            existing["filled"] = filled
            existing["remaining"] = remaining
            existing["avg_fill_price"] = avgFillPrice

    # ── Open-orders callbacks (for live bracket monitoring) ───────────────────

    def openOrder(self, orderId: int, contract: Any, order: Any, orderState: Any):
        try:
            self._open_orders[orderId] = {
                "order_id": orderId,
                "symbol": getattr(contract, "symbol", ""),
                "sec_type": getattr(contract, "secType", ""),
                "action": getattr(order, "action", ""),
                "order_type": getattr(order, "orderType", ""),
                "quantity": float(getattr(order, "totalQuantity", 0) or 0),
                "lmt_price": float(getattr(order, "lmtPrice", 0) or 0),
                "aux_price": float(getattr(order, "auxPrice", 0) or 0),
                "trail_stop_price": float(getattr(order, "trailStopPrice", 0) or 0),
                "trailing_percent": float(getattr(order, "trailingPercent", 0) or 0),
                "parent_id": int(getattr(order, "parentId", 0) or 0),
                "oca_group": getattr(order, "ocaGroup", "") or "",
                "status": getattr(orderState, "status", "") or "",
                # status fields filled in by orderStatus updates
                "filled": 0.0,
                "remaining": float(getattr(order, "totalQuantity", 0) or 0),
                "avg_fill_price": 0.0,
            }
        except Exception as e:  # pragma: no cover  — defensive
            logger.warning(f"[IBKR] openOrder parse error: {e}")

    def openOrderEnd(self):
        snapshot = list(self._open_orders.values())
        if self._loop:
            self._loop.call_soon_threadsafe(self._open_orders_q.put_nowait, snapshot)

    # ── Error callback ────────────────────────────────────────────────────────

    def execDetails(self, reqId: int, contract: Any, execution: Any):
        try:
            fill = {
                "exec_id": getattr(execution, "execId", "") or "",
                "order_id": int(getattr(execution, "orderId", 0) or 0),
                "symbol": getattr(contract, "symbol", "") or "",
                "sec_type": getattr(contract, "secType", "") or "",
                "side": getattr(execution, "side", "") or "",
                "quantity": float(getattr(execution, "shares", 0) or 0),
                "price": float(getattr(execution, "price", 0) or 0),
                "avg_price": float(getattr(execution, "avgPrice", 0) or 0),
                "timestamp": getattr(execution, "time", "") or "",
            }
            self._recent_fills.insert(0, fill)
            self._recent_fills = self._recent_fills[:30]
        except Exception as exc:  # pragma: no cover
            logger.warning("[IBKR] execDetails parse error: %s", exc)

    def error(
        self,
        reqId: TickerId,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        msg = f"reqId={reqId} code={errorCode} msg={errorString}"
        level = "info" if errorCode in _IB_INFO_CODES else "error"
        log_fn = logger.info if level == "info" else logger.error
        log_fn("[IBKR] %s %s", level, msg)
        if self._on_ib_event:
            self._on_ib_event(kind="ib_code", code=errorCode, msg=errorString)
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._error_q.put_nowait,
                {"reqId": reqId, "code": errorCode, "msg": errorString},
            )


# ── Service singleton ─────────────────────────────────────────────────────────


class IBKRService:
    """
    Singleton async service.  Manages one ibapi connection (reconnects on drop).
    Paper trading: port 7497  |  Live Gateway: port 4001
    """

    PAPER_PORT = _env_int("IBKR_PAPER_PORT", default=7497)
    LIVE_PORT = _env_int("IBKR_LIVE_PORT", default=4001)
    LIVE_TWS_PORT = _env_int("IBKR_LIVE_TWS_PORT", default=7496)
    HOST = _default_host()
    CLIENT_ID = _env_int("IBKR_CLIENT_ID", "IB_CLIENT_ID", default=1)
    CLIENT_ID_RETRY_COUNT = _env_int("IBKR_CLIENT_ID_RETRY_COUNT", default=10)
    TIMEOUT = 10  # seconds to wait for IB Gateway responses

    def _record_event(self, kind: str, detail: str, *, level: str = "info") -> None:
        ts = time.time()
        self._last_heartbeat_ts = ts
        event = {
            "kind": kind,
            "detail": detail,
            "level": level,
            "ts": ts,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        }
        self._recent_events.insert(0, event)
        self._recent_events = self._recent_events[:25]
        if kind == "error":
            self._last_error = {"detail": detail, "at": event["at"]}
        elif kind == "connectivity":
            if "lost" in detail.lower() or "1100" in detail:
                self._health.last_disconnect_at = event["at"]
            elif "restored" in detail.lower() or "1102" in detail:
                self._health.last_restore_at = event["at"]
        elif kind == "order_ack":
            self._last_order_ok = event["at"]
        elif kind == "order_reject":
            self._last_order_fail = event["at"]

    def _apply_ib_info_code(self, code: int, msg: str = "") -> None:
        if code not in _IB_INFO_CODES:
            return
        self._health.apply_ib_code(code, msg)
        level = "info" if code != 1100 else "warn"
        self._record_event("connectivity", f"{code}: {msg or 'IB info'}", level=level)

    def _bind_app_health(self, app: _IBKRApp) -> None:
        svc = self

        def _on_event(*, kind: str, code: Optional[int] = None, msg: str = "") -> None:
            if kind == "connect_ack":
                svc._session.on_connect_ack()
                svc._health.session_status = "connected"
                logger.info(
                    "[IBKR] handshake stage=connect_ack source=%s",
                    svc._session.connect_attempt_source,
                )
            elif kind == "connection_closed":
                svc._session.on_session_closed()
                svc._health.session_status = "lost"
                if not svc._health.last_disconnect_at:
                    svc._health.last_disconnect_at = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                    )
                svc._schedule_reconnect()
            elif kind == "next_valid_id":
                svc._session.on_next_valid_id()
                if svc._health.session_status in ("inactive", "lost"):
                    svc._health.session_status = "connected"
                logger.info(
                    "[IBKR] handshake stage=api_ready source=%s",
                    svc._session.connect_attempt_source,
                )
            elif kind == "ib_code" and code is not None:
                if code in _IB_INFO_CODES:
                    svc._apply_ib_info_code(code, msg)
                    if code == 1100:
                        svc._schedule_reconnect()
                else:
                    svc._record_event("error", f"{code}: {msg}", level="error")

        app._on_ib_event = _on_event

    def _sync_health_from_app(self) -> None:
        app = self._app
        if app is not None:
            while not app._error_q.empty():
                ib_error = app._error_q.get_nowait()
                code = int(ib_error.get("code") or 0)
                msg = str(ib_error.get("msg") or "")
                if code in _IB_INFO_CODES:
                    self._apply_ib_info_code(code, msg)
                else:
                    self._record_event("error", f"{code}: {msg}", level="error")
            if getattr(app, "_session_closed", False) and not app.isConnected():
                self._health.session_status = "lost"
                if not self._health.last_disconnect_at:
                    self._health.last_disconnect_at = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                    )

    def build_health_state(self, *, bracket_ready: bool = False) -> dict[str, Any]:
        self._sync_health_from_app()
        connected = self.is_connected
        authenticated = (
            connected and self._app is not None and self._app._next_order_id is not None
        )
        account_loaded = self._account_loaded_at is not None
        self._health.refresh_derived(
            socket_connected=connected,
            authenticated=authenticated,
            account_loaded=account_loaded,
            bracket_ready=bracket_ready,
        )
        return self._health.to_dict(transport=self._session.to_dict())

    def build_diagnosis(
        self,
        *,
        bracket_status: str = "unavailable",
        bracket_enabled: bool = False,
        trade_handoff_ready: bool = False,
    ) -> dict[str, Any]:
        from src.services.ibkr_diagnosis import build_ibkr_diagnosis

        health = self.build_health_state(bracket_ready=bracket_status == "ready")
        host = getattr(self, "_host", _normalize_host(None))
        port = int(
            getattr(
                self,
                "_port",
                self.PAPER_PORT if self._mode == "paper" else self.LIVE_PORT,
            )
        )
        last_err = self._last_error
        return build_ibkr_diagnosis(
            mode=self._mode,
            host=host,
            port=port,
            docker=_running_in_docker(),
            ibapi_available=IBAPI_AVAILABLE,
            socket_connected=self.is_connected,
            session_usable=bool(health.get("session_usable")),
            ib_api_ready=bool(self._session.ib_api_ready),
            account_loaded=self._account_loaded_at is not None,
            next_order_id=self._app._next_order_id if self._app else None,
            monitoring_only=health.get("handoff_status") == "monitoring_only",
            trade_handoff_ready=trade_handoff_ready,
            session_status=str(health.get("session_status") or "inactive"),
            bracket_status=bracket_status,
            bracket_enabled=bracket_enabled,
            ib_handshake_started=bool(self._session.ib_handshake_started),
            failed_handshake_count_1m=self._session.failed_handshake_count_1m,
            last_error=last_err,
            paper_port=self.PAPER_PORT,
            live_ports=[self.LIVE_PORT, self.LIVE_TWS_PORT],
        )

    def get_transport_snapshot(self) -> dict[str, Any]:
        """Shared broker transport view for routers/UI."""
        health = self.build_health_state()
        session_usable = bool(health.get("session_usable"))
        socket_connected = self.is_connected
        diagnosis = self.build_diagnosis()
        api_port_open = bool(diagnosis.get("api_port_open"))
        gateway_reachable = derive_gateway_reachable(
            ib_api_ready=bool(self._session.ib_api_ready),
            socket_connected=socket_connected,
            session_usable=session_usable,
            account_loaded_at=self._account_loaded_at,
            api_port_open=api_port_open,
        )
        return {
            **self._session.to_dict(),
            "gateway_reachable": gateway_reachable,
            "api_port_open": api_port_open,
            "diagnosis": diagnosis,
            "session_status": health.get("session_status"),
            "account_status": health.get("account_status"),
            "market_data_status": health.get("market_data_status"),
            "secdef_status": health.get("secdef_status"),
            "hmds_status": health.get("hmds_status"),
            "execution_status": health.get("execution_status"),
            "last_disconnect_at": health.get("last_disconnect_at"),
            "last_restore_at": health.get("last_restore_at"),
            "degraded_reasons": health.get("degraded_reasons") or [],
        }

    def _drain_app_errors(self, app: _IBKRApp) -> None:
        while not app._error_q.empty():
            ib_error = app._error_q.get_nowait()
            code = int(ib_error.get("code") or 0)
            msg = ib_error.get("msg") or ""
            if code in _IB_INFO_CODES:
                self._apply_ib_info_code(code, msg)
                continue
            self._record_event("error", f"{code}: {msg}", level="error")

    def __init__(self):
        self._app: Optional[_IBKRApp] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._mode: str = "paper"  # "paper" | "live"
        self._client_id: int = self.CLIENT_ID
        self._lock = asyncio.Lock()
        self._connect_inflight: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_enabled = True
        self._last_connect_ts: Optional[float] = None
        self._last_heartbeat_ts: Optional[float] = None
        self._last_order_ok: Optional[str] = None
        self._last_order_fail: Optional[str] = None
        self._last_error: Optional[dict] = None
        self._account_loaded_at: Optional[float] = None
        self._account_id: str = ""
        self._recent_events: list[dict] = []
        self._recent_fills: list[dict] = []
        self._health = IBKRHealthState()
        self._session = IBKRSessionRuntime()

    # ── Connection management ─────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._app is not None and self._app.isConnected()

    def _schedule_reconnect(self) -> None:
        if not self._reconnect_enabled or not IBAPI_AVAILABLE:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while self._reconnect_enabled and not self.is_connected:
            delay = _RECONNECT_BACKOFF_S[min(attempt, len(_RECONNECT_BACKOFF_S) - 1)]
            logger.info(
                "[IBKR] reconnect backoff %.0fs attempt=%s source=reconnect_loop",
                delay,
                attempt + 1,
            )
            await asyncio.sleep(delay)
            if self.is_connected:
                return
            result = await self.connect(
                mode=self._mode,
                host=getattr(self, "_host", None),
                port=getattr(self, "_port", None),
                client_id=self._client_id,
                source="reconnect_loop",
            )
            if result.get("ok"):
                logger.info("[IBKR] reconnect succeeded after %s attempts", attempt + 1)
                return
            attempt += 1

    async def connect(
        self,
        mode: str = "paper",
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
        source: ConnectSource = "manual_test",
    ) -> dict:
        if not IBAPI_AVAILABLE:
            return {"ok": False, "error": "ibapi not installed"}

        if self._connect_inflight is not None:
            return await asyncio.shield(self._connect_inflight)

        async def _run() -> dict:
            return await self._connect_impl(
                mode=mode,
                host=host,
                port=port,
                client_id=client_id,
                source=source,
            )

        self._connect_inflight = asyncio.create_task(_run())
        try:
            return await asyncio.shield(self._connect_inflight)
        finally:
            if self._connect_inflight and self._connect_inflight.done():
                self._connect_inflight = None

    async def _connect_impl(
        self,
        *,
        mode: str,
        host: Optional[str],
        port: Optional[int],
        client_id: Optional[int],
        source: ConnectSource,
    ) -> dict:
        async with self._lock:
            if self.is_connected:
                return {
                    "ok": True,
                    "mode": self._mode,
                    "client_id": self._client_id,
                    "already_connected": True,
                }

            self._mode = mode
            self._host = _normalize_host(host)
            self._session.on_handshake_start(source)
            logger.info(
                "[IBKR] connect start source=%s host=%s mode=%s",
                source,
                self._host,
                mode,
            )

            if port:
                candidate_ports = [port]
            elif getattr(self, "_port", None) and source == "reconnect_loop":
                candidate_ports = [self._port]
            elif mode == "live":
                candidate_ports = list(
                    dict.fromkeys([self.LIVE_PORT, self.LIVE_TWS_PORT])
                )
            else:
                candidate_ports = [self.PAPER_PORT]
            self._port = candidate_ports[0]

            port_errors: dict[int, str] = {}
            base_client_id = client_id or self.CLIENT_ID
            candidate_client_ids = [
                base_client_id + offset
                for offset in range(self.CLIENT_ID_RETRY_COUNT + 1)
                if base_client_id + offset > 0
            ]
            connected = False

            for candidate_port in candidate_ports:
                self._port = candidate_port
                handshake_errors: dict[int, list[str]] = {}
                socket_errors: dict[int, str] = {}

                for candidate_client_id in candidate_client_ids:
                    app = _IBKRApp()
                    app._loop = asyncio.get_event_loop()

                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                app.connect,
                                self._host,
                                candidate_port,
                                candidate_client_id,
                            ),
                            timeout=self.TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        try:
                            app.disconnect()
                        except Exception:
                            pass
                        socket_errors[candidate_client_id] = (
                            "Timeout connecting to IB Gateway"
                        )
                        continue
                    except Exception as e:
                        try:
                            app.disconnect()
                        except Exception:
                            pass
                        socket_errors[candidate_client_id] = (
                            str(e) or e.__class__.__name__
                        )
                        continue

                    t = threading.Thread(
                        target=app.run,
                        daemon=True,
                        name=f"ibkr-reader-{candidate_client_id}",
                    )
                    t.start()

                    deadline = time.time() + self.TIMEOUT
                    ib_errors: list[str] = []
                    while time.time() < deadline:
                        if app._next_order_id is not None:
                            break
                        while not app._error_q.empty():
                            ib_error = app._error_q.get_nowait()
                            ib_errors.append(
                                f"{ib_error.get('code')}: {ib_error.get('msg')}"
                            )
                        if any(error.startswith("326:") for error in ib_errors):
                            break
                        await asyncio.sleep(0.1)

                    if app._next_order_id is not None:
                        self._reader_thread = t
                        self._app = app
                        self._bind_app_health(app)
                        self._client_id = candidate_client_id
                        self._session.on_next_valid_id()
                        connected = True
                        break

                    while not app._error_q.empty():
                        ib_error = app._error_q.get_nowait()
                        ib_errors.append(
                            f"{ib_error.get('code')}: {ib_error.get('msg')}"
                        )
                    handshake_errors[candidate_client_id] = ib_errors
                    try:
                        app.disconnect()
                    except Exception:
                        pass

                if connected:
                    break

                error_parts = []
                for failed_client_id, failed_errors in handshake_errors.items():
                    detail = (
                        "; ".join(failed_errors)
                        if failed_errors
                        else "handshake timeout"
                    )
                    error_parts.append(f"clientId {failed_client_id}: {detail}")
                for failed_client_id, failed_error in socket_errors.items():
                    error_parts.append(f"clientId {failed_client_id}: {failed_error}")
                port_errors[candidate_port] = (
                    "; ".join(error_parts) or "no handshake response"
                )

            if not connected:
                self._session.record_failed_handshake()
                tried_ports = ", ".join(
                    f"{p} ({port_errors.get(p, 'failed')})" for p in candidate_ports
                )
                self._app = None
                return {
                    "ok": False,
                    "error": (
                        f"Cannot complete IB API handshake at {self._host}; tried {tried_ports}. "
                        "Start IB Gateway/TWS, enable API socket clients, and confirm the paper/live port. "
                        "Live Gateway defaults to 4001; Live TWS defaults to 7496; Paper TWS defaults to 7497."
                    ),
                    "host": self._host,
                    "port": self._port,
                    "tried_ports": candidate_ports,
                    "tried_client_ids": candidate_client_ids,
                    "connect_source": source,
                    "docker": _running_in_docker(),
                }

            logger.info(
                f"[IBKR] Connected — mode={mode} port={self._port} clientId={self._client_id} nextOrderId={self._app._next_order_id}"
            )
            self._last_connect_ts = time.time()
            self._health.session_status = "connected"
            self._record_event(
                "connect",
                f"Connected {mode} {self._host}:{self._port} clientId={self._client_id}",
            )
            return {
                "ok": True,
                "mode": mode,
                "host": self._host,
                "port": self._port,
                "client_id": self._client_id,
                "next_order_id": self._app._next_order_id,
            }

    async def disconnect(self):
        self._reconnect_enabled = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._app and self._app.isConnected():
            self._app.disconnect()
        self._session.on_session_closed()
        self._health.session_status = "inactive"
        self._record_event("disconnect", "Session disconnected")
        self._app = None
        self._account_loaded_at = None
        self._account_id = ""
        self._reconnect_enabled = True

    # ── Account summary ───────────────────────────────────────────────────────

    async def get_account_summary(self) -> Optional[AccountSummary]:
        if not self.is_connected:
            return None
        app = self._app
        app._account_data = {}
        # Clear queue
        while not app._account_q.empty():
            app._account_q.get_nowait()

        app.reqAccountSummary(
            reqId=9001,
            groupName="All",
            tags="NetLiquidation,TotalCashValue,BuyingPower,UnrealizedPnL,RealizedPnL,GrossPositionValue,InitMarginReq,MaintMarginReq,AvailableFunds,AccountCode",
        )
        try:
            summary = await asyncio.wait_for(app._account_q.get(), timeout=self.TIMEOUT)
            app.cancelAccountSummary(9001)
            self._account_loaded_at = time.time()
            self._account_id = summary.account or self._account_id
            self._health.note_account_ok()
            self._record_event("account", f"Account loaded {summary.account or '—'}")
            return summary
        except asyncio.TimeoutError:
            logger.error("[IBKR] get_account_summary timeout")
            return None

    # ── Positions ─────────────────────────────────────────────────────────────

    async def get_positions(self) -> list[Position]:
        if not self.is_connected:
            return []
        app = self._app
        app._positions = {}
        while not app._position_q.empty():
            app._position_q.get_nowait()

        app.reqPositions()
        try:
            positions = await asyncio.wait_for(
                app._position_q.get(), timeout=self.TIMEOUT
            )
            app.cancelPositions()
            return positions
        except asyncio.TimeoutError:
            logger.error("[IBKR] get_positions timeout")
            return []

    # ── Place order ───────────────────────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        sec_type: str,
        action: str,  # "BUY" | "SELL"
        quantity: float,
        order_type: str = "MKT",  # "MKT" | "LMT" | "STP"
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        tif: str = "DAY",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> OrderResult:
        if not self.is_connected:
            return OrderResult(error="Not connected to IB Gateway")
        if not IBAPI_AVAILABLE:
            return OrderResult(error="ibapi not available")

        app = self._app
        order_id = app._next_order_id
        app._next_order_id += 1

        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = sec_type.upper()
        contract.exchange = exchange
        contract.currency = currency

        order = Order()
        order.action = action.upper()
        order.orderType = order_type.upper()
        order.totalQuantity = quantity
        order.tif = (tif or "DAY").upper()
        if order_type.upper() == "LMT" and limit_price is not None:
            order.lmtPrice = limit_price
        elif order_type.upper() == "STP" and stop_price is not None:
            order.auxPrice = stop_price
        elif limit_price is not None:
            order.lmtPrice = limit_price

        # Clear order status queue
        while not app._order_status_q.empty():
            app._order_status_q.get_nowait()

        app.placeOrder(order_id, contract, order)
        logger.info(
            f"[IBKR] placeOrder id={order_id} {action} {quantity}x {symbol} {order_type}"
        )

        try:
            result = await asyncio.wait_for(
                app._order_status_q.get(), timeout=self.TIMEOUT
            )
            self._drain_app_errors(app)
            if result.error:
                self._record_event(
                    "order_reject",
                    f"#{result.order_id} {result.status}: {result.error}",
                    level="error",
                )
            else:
                self._record_event(
                    "order_ack",
                    f"#{result.order_id} {action} {quantity}x {symbol} {result.status}",
                )
            return result
        except asyncio.TimeoutError:
            self._drain_app_errors(app)
            self._record_event(
                "order_ack",
                f"#{order_id} {action} {quantity}x {symbol} Submitted (status timeout)",
            )
            return OrderResult(
                order_id=order_id,
                status="Submitted",
                error="Timeout waiting for status — order may still be active",
            )

    # ── Place bracket order (parent + stop + target, all OCA) ──────────────────
    async def place_bracket_order(
        self,
        symbol: str,
        sec_type: str,
        action: str,  # parent side: "BUY" | "SELL"
        quantity: float,
        entry_price: Optional[float],  # None → market entry
        stop_price: float,
        take_profit: float,
        exchange: str = "SMART",
        currency: str = "USD",
        trail: bool = False,
        trail_amount: Optional[float] = None,  # absolute $ trail
        trail_percent: Optional[float] = None,  # percent trail (e.g., 5.0 = 5%)
    ) -> dict:
        """
        Submits a 3-leg bracket: parent (entry) + child stop + child take-profit.
        Stop child is STP by default, or TRAIL when trail=True.
        Children are transmitted with parentId=parent.orderId and an OCA group so one cancels the other.

        Returns {parent_order_id, stop_order_id, target_order_id, oca_group, stop_kind, ...}.
        """
        if not self.is_connected:
            return {"error": "Not connected to IB Gateway"}
        if not IBAPI_AVAILABLE:
            return {"error": "ibapi not available"}
        # Validate geometry
        a = action.upper()
        if a == "BUY":
            if not (stop_price < (entry_price or take_profit) < take_profit):
                return {
                    "error": (
                        f"Invalid bracket geometry for BUY: need "
                        f"stop({stop_price}) < entry({entry_price}) < target({take_profit})"
                    )
                }
        else:  # SELL / short bracket
            if not (take_profit < (entry_price or stop_price) < stop_price):
                return {
                    "error": (
                        f"Invalid bracket geometry for SELL: need "
                        f"target({take_profit}) < entry({entry_price}) < stop({stop_price})"
                    )
                }

        app = self._app
        parent_id = app._next_order_id
        stop_id = parent_id + 1
        target_id = parent_id + 2
        app._next_order_id = target_id + 1

        oca_group = f"BRK_{symbol.upper()}_{parent_id}"
        child_action = "SELL" if a == "BUY" else "BUY"

        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = sec_type.upper()
        contract.exchange = exchange
        contract.currency = currency

        # Parent
        parent = Order()
        parent.orderId = parent_id
        parent.action = a
        parent.orderType = "LMT" if entry_price is not None else "MKT"
        parent.totalQuantity = quantity
        if entry_price is not None:
            parent.lmtPrice = entry_price
        parent.transmit = False  # hold transmission until children attached

        # Stop child
        stop_ord = Order()
        stop_ord.orderId = stop_id
        stop_ord.action = child_action
        stop_kind = "STP"
        if trail:
            stop_kind = "TRAIL"
            stop_ord.orderType = "TRAIL"
            # IB requires either trailingPercent OR auxPrice (trail amount)
            if trail_percent is not None and trail_percent > 0:
                stop_ord.trailingPercent = trail_percent
            elif trail_amount is not None and trail_amount > 0:
                stop_ord.auxPrice = trail_amount
            else:
                # Default to a $-amount trail equal to entry-stop distance
                ref = entry_price if entry_price is not None else stop_price
                stop_ord.auxPrice = abs(ref - stop_price)
            # trailStopPrice = initial worst-case stop (acts as floor/ceiling)
            stop_ord.trailStopPrice = stop_price
        else:
            stop_ord.orderType = "STP"
            stop_ord.auxPrice = stop_price
        stop_ord.totalQuantity = quantity
        stop_ord.parentId = parent_id
        stop_ord.ocaGroup = oca_group
        stop_ord.ocaType = 1  # cancel all remaining orders with block
        stop_ord.transmit = False

        # Target child (last leg transmits all)
        target_ord = Order()
        target_ord.orderId = target_id
        target_ord.action = child_action
        target_ord.orderType = "LMT"
        target_ord.totalQuantity = quantity
        target_ord.lmtPrice = take_profit
        target_ord.parentId = parent_id
        target_ord.ocaGroup = oca_group
        target_ord.ocaType = 1
        target_ord.transmit = True

        # Drain queue, send 3 legs
        while not app._order_status_q.empty():
            app._order_status_q.get_nowait()

        app.placeOrder(parent_id, contract, parent)
        app.placeOrder(stop_id, contract, stop_ord)
        app.placeOrder(target_id, contract, target_ord)
        logger.info(
            f"[IBKR] bracket id={parent_id} {a} {quantity}x {symbol} "
            f"entry={entry_price} stop={stop_price} target={take_profit} oca={oca_group}"
        )

        # Wait for parent ack; if timeout, still return ids (children may fill later)
        parent_status = None
        try:
            parent_status = await asyncio.wait_for(
                app._order_status_q.get(), timeout=self.TIMEOUT
            )
        except asyncio.TimeoutError:
            parent_status = None
        self._drain_app_errors(app)
        if parent_status and parent_status.error:
            self._record_event(
                "order_reject",
                f"Bracket #{parent_id} rejected: {parent_status.error}",
                level="error",
            )
        else:
            self._record_event(
                "order_ack",
                f"Bracket #{parent_id} {a} {quantity}x {symbol} OCA {oca_group}",
            )

        return {
            "parent_order_id": parent_id,
            "stop_order_id": stop_id,
            "target_order_id": target_id,
            "oca_group": oca_group,
            "stop_kind": stop_kind,
            "trail_amount": trail_amount,
            "trail_percent": trail_percent,
            "parent_status": parent_status.status if parent_status else "Submitted",
            "parent_filled": parent_status.filled if parent_status else 0,
            "parent_avg_fill": parent_status.avg_fill_price if parent_status else 0,
            "warning": (
                parent_status.error if (parent_status and parent_status.error) else None
            ),
        }

    # ── Cancel orders ─────────────────────────────────────────────────────────
    async def cancel_order(self, order_id: int) -> dict:
        """Cancel a single IB order by id. Idempotent — broker error if already done."""
        if not self.is_connected:
            return {"ok": False, "error": "Not connected"}
        if not IBAPI_AVAILABLE:
            return {"ok": False, "error": "ibapi not available"}
        try:
            # ibapi 10.x: cancelOrder(orderId, manualCancelOrderTime="")
            try:
                self._app.cancelOrder(order_id, "")
            except TypeError:
                # older signature
                self._app.cancelOrder(order_id)
            logger.info(f"[IBKR] cancelOrder id={order_id}")
            # Reflect locally so polling picks it up quickly
            existing = self._app._open_orders.get(order_id)
            if existing is not None:
                existing["status"] = "PendingCancel"
            return {"ok": True, "order_id": order_id, "status": "PendingCancel"}
        except Exception as e:
            return {"ok": False, "error": str(e), "order_id": order_id}

    async def cancel_bracket(
        self,
        parent_id: int,
        stop_id: Optional[int] = None,
        target_id: Optional[int] = None,
    ) -> dict:
        """
        Cancel all 3 legs of a bracket. Parent first (broker cancels children),
        then fall back to explicit child cancels in case OCA didn't propagate.
        """
        results = []
        for oid in [parent_id, stop_id, target_id]:
            if oid is None:
                continue
            r = await self.cancel_order(int(oid))
            results.append(r)
        ok = all(r.get("ok") for r in results)
        return {"ok": ok, "results": results}

    # ── Open orders snapshot ──────────────────────────────────────────────────
    async def get_open_orders(self) -> list[dict]:
        """
        Request and return current open orders. Drains queue, asks broker via
        reqAllOpenOrders, waits for openOrderEnd. Best-effort; returns last snapshot on timeout.
        """
        if not self.is_connected:
            return []
        if not IBAPI_AVAILABLE:
            return []
        app = self._app
        # Reset accumulator and queue so we get a clean snapshot
        app._open_orders = {}
        while not app._open_orders_q.empty():
            app._open_orders_q.get_nowait()
        try:
            app.reqAllOpenOrders()
            snapshot = await asyncio.wait_for(
                app._open_orders_q.get(), timeout=self.TIMEOUT
            )
            return snapshot
        except asyncio.TimeoutError:
            return list(app._open_orders.values())

    # ── Status ────────────────────────────────────────────────────────────────

    def get_recent_fills(self) -> list[dict]:
        if self._app is not None:
            return list(getattr(self._app, "_recent_fills", []) or [])
        return list(self._recent_fills)

    def build_readiness_matrix(
        self,
        *,
        gateway_reachable: bool = False,
        broker_position_count: int = 0,
        manual_position_count: int = 0,
        bracket_stop: Optional[float] = None,
        bracket_target: Optional[float] = None,
        bracket_enabled: bool = False,
    ) -> dict:
        connected = self.is_connected
        authenticated = connected and self._app is not None and self._app._next_order_id is not None
        account_loaded = self._account_loaded_at is not None
        order_routing_ready = authenticated and bool(self._app and self._app._next_order_id)
        ibapi_ok = IBAPI_AVAILABLE

        if not ibapi_ok:
            bracket_status = "unavailable"
            bracket_reason = "ibapi not installed"
        elif not connected:
            bracket_status = "unavailable"
            bracket_reason = "請先連線 IB Gateway · Connect IB Gateway session first"
        elif not order_routing_ready:
            bracket_status = "unavailable"
            bracket_reason = "等待 nextValidId／訂單佇列 · Waiting for nextValidId / order queue"
        elif bracket_enabled and (not bracket_stop or not bracket_target):
            bracket_status = "partial"
            bracket_reason = "Bracket 預覽待填止損＋目標 · Bracket preview pending stop + target fields"
        elif bracket_enabled:
            bracket_status = "ready"
            bracket_reason = "Bracket 已就緒 — 送出時 parent + OCA 子單 · Bracket builder ready on transmit"
        else:
            bracket_status = "partial"
            bracket_reason = (
                "Bracket 建構器可用但未完整設定；勿將「已連線」當作足夠保護，"
                "送出前請確認止損／目標邏輯。"
                " · Bracket builder available but not fully configured — "
                "confirm stop / target logic before transmit."
            )

        health = self.build_health_state(bracket_ready=bracket_status == "ready")
        session_usable = bool(health.get("session_usable"))

        md_ok = health.get("market_data_status") == "ok"
        md_partial = health.get("market_data_status") == "degraded" or (
            connected and health.get("market_data_status") == "unknown"
        )
        secdef_ok = health.get("secdef_status") == "ok"
        secdef_partial = health.get("secdef_status") == "degraded"
        hmds_status = health.get("hmds_status") or "unknown"
        hmds_ok = hmds_status == "ok"
        hmds_dormant = hmds_status == "dormant"

        if broker_position_count == 0 and manual_position_count > 0:
            portfolio_sync_status = "mismatch"
            portfolio_sync_reason = (
                f"Portfolio page has {manual_position_count} local positions; "
                f"IBKR shows 0 — local book is research/manual until broker sync"
            )
        elif broker_position_count > 0 and manual_position_count > broker_position_count:
            portfolio_sync_status = "partial"
            portfolio_sync_reason = (
                f"IBKR={broker_position_count} broker positions; "
                f"Portfolio={manual_position_count} local rows — reconcile stops/metadata"
            )
        elif connected and account_loaded:
            portfolio_sync_status = "ready"
            portfolio_sync_reason = "IBKR positions = broker truth when connected"
        elif connected:
            portfolio_sync_status = "partial"
            portfolio_sync_reason = "Connected — refresh account/positions to confirm sync"
        else:
            portfolio_sync_status = "unavailable"
            portfolio_sync_reason = "Portfolio page = research/manual book until IBKR connected"

        playbook_handoff_ready = connected and order_routing_ready and not (
            bracket_enabled and bracket_status != "ready"
        )

        def _row(
            key: str,
            label: str,
            ok: bool,
            *,
            category: str,
            partial: bool = False,
            reason: str = "",
        ) -> dict:
            if ok:
                state = "ready"
            elif partial:
                state = "partial"
            else:
                state = "unavailable"
            return {
                "key": key,
                "label": label,
                "category": category,
                "state": state,
                "ok": ok,
                "reason": reason,
            }

        rows = [
            _row(
                "gateway",
                "Gateway connected",
                gateway_reachable,
                category="critical",
                partial=gateway_reachable and not connected,
                reason=(
                    "IB API session active"
                    if gateway_reachable
                    else "No IB API session — use Connect (not TCP probe)"
                ),
            ),
            _row(
                "authenticated",
                "Authenticated",
                authenticated,
                category="critical",
                partial=connected and not authenticated,
                reason="API handshake complete" if authenticated else "Connect session to authenticate",
            ),
            _row(
                "account",
                "Account loaded",
                account_loaded or health.get("account_status") == "ok",
                category="critical",
                partial=session_usable and not account_loaded,
                reason=(
                    f"Account {self._account_id}"
                    if account_loaded or health.get("account_status") == "ok"
                    else "Refresh account summary"
                ),
            ),
            _row(
                "market_data",
                "Market data OK",
                md_ok,
                category="critical",
                partial=md_partial,
                reason=(
                    "Market data farm OK (2104)"
                    if md_ok
                    else (
                        "Market data farm degraded (2103) — quotes may be stale"
                        if health.get("market_data_status") == "degraded"
                        else "Farm status not reported this session"
                    )
                ),
            ),
            _row(
                "order_routing",
                "Order routing ready",
                order_routing_ready,
                category="critical",
                partial=connected and not order_routing_ready,
                reason=(
                    f"nextOrderId={self._app._next_order_id}"
                    if order_routing_ready and self._app
                    else "Waiting for order queue"
                ),
            ),
            {
                "key": "bracket",
                "label": "Bracket configured",
                "category": "workflow",
                "state": bracket_status,
                "ok": bracket_status == "ready",
                "reason": bracket_reason,
                "bracket_status": bracket_status,
            },
            {
                "key": "portfolio_sync",
                "label": "Portfolio synced",
                "category": "workflow",
                "state": portfolio_sync_status,
                "ok": portfolio_sync_status == "ready",
                "reason": portfolio_sync_reason,
                "sync_status": portfolio_sync_status,
            },
            _row(
                "playbook_handoff",
                "Playbook handoff ready",
                playbook_handoff_ready,
                category="workflow",
                partial=connected and not playbook_handoff_ready,
                reason=(
                    "Send-to-IBKR prefill available"
                    if playbook_handoff_ready
                    else "Connect + order routing + bracket required"
                ),
            ),
        ]

        farm_rows = [
            _row(
                "secdef",
                "Sec-def data farm",
                secdef_ok,
                category="farm",
                partial=secdef_partial,
                reason=(
                    "Sec-def farm OK (2158)"
                    if secdef_ok
                    else (
                        "Sec-def farm degraded (2157)"
                        if secdef_partial
                        else "Sec-def status not reported"
                    )
                ),
            ),
            {
                "key": "hmds",
                "label": "HMDS historical data",
                "category": "farm",
                "state": (
                    "ready"
                    if hmds_ok
                    else "partial"
                    if hmds_dormant
                    else "unavailable"
                    if hmds_status == "degraded"
                    else "partial"
                ),
                "ok": hmds_ok or hmds_dormant,
                "reason": (
                    "HMDS OK (2106)"
                    if hmds_ok
                    else (
                        "HMDS dormant — idle, not an error (2107)"
                        if hmds_dormant
                        else (
                            "HMDS degraded"
                            if hmds_status == "degraded"
                            else "HMDS status not reported"
                        )
                    )
                ),
            },
        ]

        critical_rows = [r for r in rows if r.get("category") == "critical"]
        workflow_rows = [r for r in rows if r.get("category") == "workflow"]
        ready_count = sum(1 for r in rows if r.get("state") == "ready")
        critical_ready = sum(1 for r in critical_rows if r.get("state") == "ready")
        workflow_ready = sum(1 for r in workflow_rows if r.get("state") == "ready")
        critical_ok = critical_ready == len(critical_rows)
        workflow_ok = workflow_ready == len(workflow_rows)
        full_handoff = critical_ok and workflow_ok and playbook_handoff_ready

        if full_handoff:
            op_badge = "HANDOFF READY"
            op_short = f"{self._mode.upper()} session ready for playbook handoff and manual transmit."
            op_full = (
                "All critical connectivity checks and workflow gates are satisfied. "
                "Broker truth, bracket configuration, and portfolio alignment are in place. "
                "Treat this page as fully synced execution control."
            )
            op_mode = "full execution control"
        elif connected and session_usable and critical_ok:
            op_badge = "MONITOR"
            gaps: list[str] = []
            if bracket_status != "ready":
                gaps.append("bracket configuration")
            if portfolio_sync_status == "mismatch":
                gaps.append("broker-vs-local portfolio alignment")
            elif portfolio_sync_status != "ready":
                gaps.append("portfolio sync confirmation")
            if not playbook_handoff_ready:
                gaps.append("playbook handoff readiness")
            gap_txt = " and ".join(gaps[:2]) if gaps else "workflow gates"
            op_short = (
                "Connected for monitoring and manual handoff, but not yet aligned "
                "for broker-truth portfolio control."
            )
            op_full = (
                "IBKR is connected, but only partially execution-ready. Market data, "
                "account, routing, and session health are available, but "
                f"{gap_txt} remain incomplete. Treat this page as monitor + manual "
                "handoff mode, not fully synced execution control."
            )
            op_mode = "monitor + manual handoff"
        elif connected or gateway_reachable:
            op_badge = "PARTIAL"
            op_short = (
                "Execution path available, but operating mode remains monitor / "
                "manual until critical connectivity and workflow gates are resolved."
            )
            op_full = (
                "IBKR session is partially active. Core connectivity may be incomplete "
                "or workflow-critical items (bracket, portfolio sync, handoff) are not "
                "yet satisfied. Do not treat a connected badge as deploy authority."
            )
            op_mode = "monitor + manual handoff"
        else:
            op_badge = "OFFLINE"
            op_short = "Broker offline — paper signals and local research book only."
            op_full = (
                "No usable IBKR session. Connect IB Gateway for broker truth, "
                "account data, and order routing."
            )
            op_mode = "offline"

        return {
            "rows": rows,
            "critical_rows": critical_rows,
            "workflow_rows": workflow_rows,
            "farm_rows": farm_rows,
            "ready_count": ready_count,
            "total": len(rows),
            "critical_ready_count": critical_ready,
            "critical_total": len(critical_rows),
            "workflow_ready_count": workflow_ready,
            "workflow_total": len(workflow_rows),
            "critical_ok": critical_ok,
            "workflow_ok": workflow_ok,
            "full_handoff_ready": full_handoff,
            "operating": {
                "badge": op_badge,
                "short_comment": op_short,
                "full_comment": op_full,
                "mode_label": op_mode,
            },
            "bracket_status": bracket_status,
            "bracket_reason": bracket_reason,
            "portfolio_sync_status": portfolio_sync_status,
            "portfolio_sync_reason": portfolio_sync_reason,
            "book_mismatch": portfolio_sync_status == "mismatch",
            "health": health,
            "health_label": health.get("summary_label"),
        }

    def diagnostics(self) -> dict:
        health = self.build_health_state()
        return {
            "host": getattr(self, "_host", _normalize_host(None)),
            "port": getattr(
                self,
                "_port",
                self.PAPER_PORT if self._mode == "paper" else self.LIVE_PORT,
            ),
            "mode": self._mode,
            "client_id": self._client_id,
            "account_id": self._account_id or None,
            "last_connect": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._last_connect_ts))
                if self._last_connect_ts
                else None
            ),
            "last_heartbeat": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._last_heartbeat_ts))
                if self._last_heartbeat_ts
                else None
            ),
            "last_disconnect_at": health.get("last_disconnect_at"),
            "last_restore_at": health.get("last_restore_at"),
            "last_order_ok": self._last_order_ok,
            "last_order_fail": self._last_order_fail,
            "last_error": self._last_error,
            "health": health,
            "recent_events": self._recent_events[:12],
            "recent_incidents": health.get("recent_incidents") or [],
        }

    def status(self) -> dict:
        health = self.build_health_state()
        transport = self.get_transport_snapshot()
        diagnosis = transport.get("diagnosis") or self.build_diagnosis()
        session_usable = bool(health.get("session_usable"))
        socket_connected = self.is_connected
        # Account API success implies session is usable even when farms are degraded.
        effective_connected = socket_connected or (
            health.get("account_status") == "ok" and session_usable
        )
        display_label = diagnosis.get("label") or health.get("summary_label")
        return {
            "connected": effective_connected,
            "socket_connected": socket_connected,
            "session_usable": session_usable,
            "gateway_reachable": transport.get("gateway_reachable", False),
            "api_port_open": transport.get("api_port_open", False),
            "mode": self._mode,
            "ibapi_available": IBAPI_AVAILABLE,
            "host": getattr(self, "_host", _normalize_host(None)),
            "port": getattr(
                self,
                "_port",
                self.PAPER_PORT if self._mode == "paper" else self.LIVE_PORT,
            ),
            "docker": _running_in_docker(),
            "client_id": self._client_id,
            "next_order_id": self._app._next_order_id if self._app else None,
            "account_loaded": self._account_loaded_at is not None,
            "account_id": self._account_id or None,
            "health": health,
            "health_label": display_label,
            "health_label_short": diagnosis.get("short"),
            "diagnosis": diagnosis,
            "monitoring_only": health.get("handoff_status") == "monitoring_only",
            "transport": transport,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_ibkr_service: Optional[IBKRService] = None


def ibkr_authority_gate_snapshot() -> dict[str, Any]:
    """In-process broker gates for decision authority — no TCP port probes.

    ``status()`` and ``build_diagnosis()`` probe gateway ports (multi-second).
    Ranked payload finalization must stay fast under pytest/CI.
    """
    try:
        svc = get_ibkr_service()
        svc._sync_health_from_app()
        health = svc.build_health_state()
        socket_connected = svc.is_connected
        session_usable = bool(health.get("session_usable"))
        effective_connected = socket_connected or (
            health.get("account_status") == "ok" and session_usable
        )
        return {
            "connected": effective_connected,
            "circuit_breaker": False,
        }
    except Exception:
        return {"connected": False, "circuit_breaker": False}


def get_ibkr_service() -> IBKRService:
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService()
    return _ibkr_service
