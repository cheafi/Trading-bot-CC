"""
IBKR Service — async wrapper around ibapi EClient/EWrapper
Supports: paper (port 7497) and live (port 7496) via IB Gateway / TWS
Thread model: ibapi runs its own reader thread; we bridge to asyncio via asyncio.Queue
"""

import asyncio
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

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


def _socket_probe(
    host: str, port: int, timeout: float = 2.5
) -> tuple[bool, Optional[str]]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except OSError as exc:
        return False, str(exc) or exc.__class__.__name__


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


# ── EWrapper + EClient combined class ────────────────────────────────────────


class _IBKRApp(EWrapper, EClient):  # type: ignore[misc]
    """
    Minimal EWrapper implementation — bridges ibapi callbacks → asyncio.Queue.
    Never call blocking methods from the main asyncio event loop.
    """

    def __init__(self):
        if not IBAPI_AVAILABLE:
            self._connected = False
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
            return
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self._connected = False
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

    def isConnected(self) -> bool:
        return bool(IBAPI_AVAILABLE and EClient.isConnected(self))

    # ── Connection callbacks ──────────────────────────────────────────────────

    def connectAck(self):
        self._connected = True
        logger.info("[IBKR] connectAck — connected to IB Gateway")

    def connectionClosed(self):
        self._connected = False
        logger.warning("[IBKR] connectionClosed")

    def nextValidId(self, orderId: int):
        self._next_order_id = orderId
        logger.info(f"[IBKR] nextValidId={orderId}")

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

    def error(
        self,
        reqId: TickerId,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        msg = f"reqId={reqId} code={errorCode} msg={errorString}"
        logger.error(f"[IBKR] error {msg}")
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

    def __init__(self):
        self._app: Optional[_IBKRApp] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._mode: str = "paper"  # "paper" | "live"
        self._client_id: int = self.CLIENT_ID
        self._lock = asyncio.Lock()

    # ── Connection management ─────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._app is not None and self._app.isConnected()

    async def connect(
        self,
        mode: str = "paper",
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
    ) -> dict:
        if not IBAPI_AVAILABLE:
            return {"ok": False, "error": "ibapi not installed"}

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
            if mode == "live":
                candidate_ports = [port] if port else []
                candidate_ports.extend([self.LIVE_PORT, self.LIVE_TWS_PORT])
            else:
                candidate_ports = [port or self.PAPER_PORT]
            candidate_ports = list(dict.fromkeys(p for p in candidate_ports if p))

            probe_errors: dict[int, str] = {}
            self._port = candidate_ports[0]
            for candidate_port in candidate_ports:
                reachable, probe_error = await asyncio.to_thread(
                    _socket_probe, self._host, candidate_port
                )
                if reachable:
                    self._port = candidate_port
                    break
                probe_errors[candidate_port] = probe_error or "unreachable"
            else:
                tried = ", ".join(
                    f"{probe_port} ({probe_error})"
                    for probe_port, probe_error in probe_errors.items()
                )
                return {
                    "ok": False,
                    "error": (
                        f"Cannot reach IB Gateway/TWS at {self._host}; tried {tried}. "
                        "Start IB Gateway/TWS, enable API socket clients, and confirm the paper/live port. "
                        "Live Gateway defaults to 4001; Live TWS defaults to 7496; Paper TWS defaults to 7497. "
                        "When the API runs in Docker on macOS, use host.docker.internal instead of 127.0.0.1."
                    ),
                    "host": self._host,
                    "port": self._port,
                    "tried_ports": list(probe_errors),
                    "docker": _running_in_docker(),
                }

            base_client_id = client_id or self.CLIENT_ID
            candidate_client_ids = [
                base_client_id + offset
                for offset in range(self.CLIENT_ID_RETRY_COUNT + 1)
                if base_client_id + offset > 0
            ]
            handshake_errors: dict[int, list[str]] = {}
            socket_errors: dict[int, str] = {}

            for candidate_client_id in candidate_client_ids:
                app = _IBKRApp()
                app._loop = asyncio.get_event_loop()

                try:
                    # connect() is blocking — run in thread
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            app.connect, self._host, self._port, candidate_client_id
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
                    socket_errors[candidate_client_id] = str(e) or e.__class__.__name__
                    continue

                # Start ibapi reader thread
                t = threading.Thread(
                    target=app.run,
                    daemon=True,
                    name=f"ibkr-reader-{candidate_client_id}",
                )
                t.start()

                # Wait for nextValidId (confirms handshake complete)
                deadline = time.time() + self.TIMEOUT
                ib_errors = []
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
                    self._client_id = candidate_client_id
                    break

                while not app._error_q.empty():
                    ib_error = app._error_q.get_nowait()
                    ib_errors.append(f"{ib_error.get('code')}: {ib_error.get('msg')}")
                handshake_errors[candidate_client_id] = ib_errors
                try:
                    app.disconnect()
                except Exception:
                    pass
            else:
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
                error_detail = "; ".join(error_parts) or "no handshake response"
                self._app = None
                return {
                    "ok": False,
                    "error": (
                        "Timeout waiting for IB Gateway/TWS API handshake after trying unique client IDs "
                        f"{candidate_client_ids}. Details: {error_detail}. "
                        "Confirm API connections are enabled and trusted IPs allow this client."
                    ),
                    "host": self._host,
                    "port": self._port,
                    "tried_client_ids": candidate_client_ids,
                }

            logger.info(
                f"[IBKR] Connected — mode={mode} port={self._port} clientId={self._client_id} nextOrderId={self._app._next_order_id}"
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
        if self._app and self._app.isConnected():
            self._app.disconnect()
        self._app = None

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
        if limit_price is not None:
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
            return result
        except asyncio.TimeoutError:
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
            pass

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

    def status(self) -> dict:
        return {
            "connected": self.is_connected,
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
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_ibkr_service: Optional[IBKRService] = None


def get_ibkr_service() -> IBKRService:
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService()
    return _ibkr_service
