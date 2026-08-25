"""Institutional IBKR health state — partial degraded states, not binary connected."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# IB info/error codes → semantic events (from TWS/Gateway message stream)
IB_SESSION_LOST = 1100
IB_SESSION_RESTORED = 1102
IB_MARKET_DATA_BROKEN = 2103
IB_MARKET_DATA_OK = 2104
IB_HMDS_OK = 2106
IB_HMDS_DORMANT = 2107
IB_SECDEF_BROKEN = 2157
IB_SECDEF_OK = 2158

# Informational farm codes — never treat as hard failures
INFO_CODES = frozenset(
    {
        IB_MARKET_DATA_OK,
        IB_MARKET_DATA_BROKEN,
        IB_HMDS_OK,
        IB_HMDS_DORMANT,
        IB_SECDEF_OK,
        IB_SECDEF_BROKEN,
        IB_SESSION_LOST,
        IB_SESSION_RESTORED,
        2119,
        2105,
        2108,
        2109,
        2110,
    }
)


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


@dataclass
class IBKRHealthTracker:
    """Tracks IB gateway message codes into structured sub-states."""

    session_status: str = "disconnected"
    account_status: str = "unavailable"
    market_data_status: str = "unknown"
    secdef_status: str = "unknown"
    hmds_status: str = "unknown"
    execution_status: str = "unavailable"
    handoff_status: str = "unavailable"
    last_disconnect_at: Optional[float] = None
    last_restore_at: Optional[float] = None
    degraded_reasons: List[str] = field(default_factory=list)
    _recent_incidents: List[Dict[str, Any]] = field(default_factory=list)

    def ingest_code(self, code: int, msg: str = "") -> None:
        """Apply one IB error/info code to tracker state."""
        detail = (msg or "").strip()
        now = time.time()
        incident = {
            "code": code,
            "message": detail,
            "at": _iso(now),
            "ts": now,
        }

        if code == IB_SESSION_LOST:
            self.session_status = "lost"
            self.last_disconnect_at = now
            self._push_incident("session_lost", incident)
            self._rebuild_degraded()
            return

        if code == IB_SESSION_RESTORED:
            self.session_status = "restored_data_maintained"
            self.last_restore_at = now
            self._push_incident("session_restored_data_maintained", incident)
            self._rebuild_degraded()
            return

        if code == IB_MARKET_DATA_BROKEN:
            self.market_data_status = "degraded"
            self._push_incident("market_data_degraded", incident)
            self._rebuild_degraded()
            return

        if code == IB_MARKET_DATA_OK:
            self.market_data_status = "ok"
            self._rebuild_degraded()
            return

        if code == IB_SECDEF_BROKEN:
            self.secdef_status = "degraded"
            self._push_incident("secdef_degraded", incident)
            self._rebuild_degraded()
            return

        if code == IB_SECDEF_OK:
            self.secdef_status = "ok"
            self._rebuild_degraded()
            return

        if code == IB_HMDS_OK:
            self.hmds_status = "ok"
            self._rebuild_degraded()
            return

        if code == IB_HMDS_DORMANT:
            # Dormant HMDS is normal outside market hours — not a failure
            self.hmds_status = "dormant"
            self._rebuild_degraded()
            return

    def on_connect(self) -> None:
        self.session_status = "connected"
        self.execution_status = "not_ready"
        self._rebuild_degraded()

    def on_disconnect(self) -> None:
        self.session_status = "disconnected"
        self.account_status = "unavailable"
        self.execution_status = "unavailable"
        self.handoff_status = "unavailable"
        now = time.time()
        self.last_disconnect_at = now
        self._push_incident(
            "session_disconnected",
            {"code": 0, "message": "connectionClosed", "at": _iso(now), "ts": now},
        )
        self._rebuild_degraded()

    def on_account_loaded(self) -> None:
        if self.session_status in ("disconnected", "lost"):
            # Account summary succeeded despite socket flag — session is operational
            if self.last_restore_at:
                self.session_status = "restored_data_maintained"
            else:
                self.session_status = "connected"
        self.account_status = "ok"
        self._rebuild_degraded()

    def on_next_valid_id(self) -> None:
        if self.session_status == "disconnected":
            self.session_status = "connected"
        self.execution_status = "ready"
        self._rebuild_degraded()

    def finalize(
        self,
        *,
        socket_connected: bool,
        account_loaded: bool,
        next_order_id: Optional[int],
        trade_handoff_ready: bool = False,
        circuit_breaker: bool = False,
    ) -> None:
        """Reconcile tracker with live service probes (status poll / account fetch)."""
        if not socket_connected and not account_loaded:
            if self.session_status not in ("lost", "restored_data_maintained"):
                self.session_status = "disconnected"
            self.account_status = "unavailable"
            self.execution_status = "unavailable"
            self.handoff_status = "unavailable"
        elif account_loaded:
            self.on_account_loaded()
        elif socket_connected:
            if self.session_status == "disconnected":
                self.session_status = "connected"
            self.account_status = "degraded"

        if next_order_id and socket_connected:
            self.execution_status = "ready"
        elif socket_connected or account_loaded:
            self.execution_status = "not_ready"
        else:
            self.execution_status = "unavailable"

        if circuit_breaker:
            self.handoff_status = "blocked"
        elif trade_handoff_ready:
            self.handoff_status = "ready"
        elif account_loaded or socket_connected:
            self.handoff_status = "monitoring_only"
        else:
            self.handoff_status = "unavailable"

        self._rebuild_degraded()

    def _push_incident(self, kind: str, incident: Dict[str, Any]) -> None:
        row = {**incident, "kind": kind}
        self._recent_incidents.insert(0, row)
        self._recent_incidents = self._recent_incidents[:20]

    def _rebuild_degraded(self) -> None:
        reasons: List[str] = []
        if self.session_status == "lost":
            reasons.append("Session connectivity lost (1100)")
        elif self.session_status == "restored_data_maintained":
            reasons.append("Session restored — data maintained (1102)")
        if self.account_status == "degraded":
            reasons.append("Account API not yet loaded")
        if self.market_data_status == "degraded":
            reasons.append("Market data farm degraded (2103)")
        if self.secdef_status == "degraded":
            reasons.append("Sec-def data farm degraded (2157)")
        if self.hmds_status == "dormant":
            reasons.append("HMDS dormant — normal outside active hours (2107)")
        if self.execution_status == "not_ready":
            reasons.append("Execution path not ready — order queue pending")
        self.degraded_reasons = reasons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_status": self.session_status,
            "account_status": self.account_status,
            "market_data_status": self.market_data_status,
            "secdef_status": self.secdef_status,
            "hmds_status": self.hmds_status,
            "execution_status": self.execution_status,
            "handoff_status": self.handoff_status,
            "last_disconnect_at": _iso(self.last_disconnect_at),
            "last_restore_at": _iso(self.last_restore_at),
            "degraded_reasons": list(self.degraded_reasons),
            "recent_incidents": self._recent_incidents[:8],
            "session_operational": self.session_operational,
            "summary_label": self.summary_label,
            "monitoring_only": self.handoff_status == "monitoring_only",
        }

    @property
    def session_operational(self) -> bool:
        """True when account API or restored session is usable — not just socket flag."""
        return self.account_status == "ok" or self.session_status in (
            "connected",
            "restored_data_maintained",
        )

    @property
    def summary_label(self) -> str:
        parts: List[str] = []
        if self.session_status == "restored_data_maintained":
            parts.append("Session restored")
        elif self.session_status == "connected":
            parts.append("Session connected")
        elif self.session_status == "lost":
            parts.append("Session lost")
        else:
            parts.append("Session disconnected")

        if self.account_status == "ok":
            parts.append("Account API OK")
        elif self.account_status == "degraded":
            parts.append("Account pending")

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

        if self.execution_status == "ready":
            parts.append("Order routing ready")
        elif self.execution_status == "not_ready":
            parts.append("Order routing pending")

        if self.handoff_status == "monitoring_only":
            if self.execution_status == "ready":
                parts.append("Execution path available · monitor / manual mode")
            else:
                parts.append("Technically connected, operationally partial")
        elif self.handoff_status == "ready":
            parts.append("Handoff ready")
        elif self.handoff_status == "blocked":
            parts.append("Handoff blocked")

        return " · ".join(parts)


def build_unified_labels(
    health: Dict[str, Any],
    *,
    ibkr_mode: str = "paper",
    circuit_breaker: bool = False,
    trade_handoff_ready: bool = False,
    gateway_reachable: bool = False,
    diagnosis: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Derive unified header labels from structured health — avoid false DISCONNECTED."""
    if diagnosis and diagnosis.get("short") and diagnosis.get("label"):
        level = "offline"
        short = str(diagnosis.get("short") or "OFFLINE")
        if trade_handoff_ready or diagnosis.get("code") == "connected_handoff_ready":
            level = "ready"
        elif circuit_breaker:
            level = "blocked"
            return {
                "unified_label": "BLOCKED — circuit breaker",
                "unified_short": "BLOCKED",
                "level": level,
                "evidence_badge": "blocked",
            }
        elif short in ("READY",):
            level = "ready"
        elif short in ("OFFLINE", "NO IBAPI"):
            level = "offline"
        else:
            level = "partial"
        badge = "disconnected"
        if level == "ready":
            badge = "live_broker"
        elif level == "partial" and short == "LOGIN":
            badge = "gateway_only"
        elif level == "partial":
            badge = "session_partial"
        return {
            "unified_label": str(diagnosis.get("label")),
            "unified_short": short,
            "level": level,
            "evidence_badge": badge,
        }

    mode = (ibkr_mode or "paper").upper()
    session_op = bool(health.get("session_operational") or health.get("session_usable"))
    account_ok = health.get("account_status") == "ok"
    degraded = health.get("degraded_reasons") or []
    has_degraded = any(
        "degraded" in r.lower() or "lost" in r.lower() or "not ready" in r.lower()
        for r in degraded
    )

    if circuit_breaker:
        return {
            "unified_label": "BLOCKED — circuit breaker",
            "unified_short": "BLOCKED",
            "level": "blocked",
            "evidence_badge": "blocked",
        }

    if trade_handoff_ready:
        return {
            "unified_label": f"{mode} · HANDOFF READY",
            "unified_short": mode,
            "level": "ready",
            "evidence_badge": "live_broker",
        }

    if session_op or account_ok:
        short = "PARTIAL" if has_degraded else mode
        label = health.get("summary_label") or f"{mode} · CONNECTED"
        if has_degraded and not health.get("summary_label"):
            label = f"{mode} · PARTIAL — " + "; ".join(degraded[:3])
        return {
            "unified_label": label,
            "unified_short": short,
            "level": "partial",
            "evidence_badge": "live_broker" if account_ok else "session_partial",
        }

    if gateway_reachable:
        return {
            "unified_label": "GATEWAY UP · LOGIN REQUIRED",
            "unified_short": "LOGIN",
            "level": "partial",
            "evidence_badge": "gateway_only",
        }

    return {
        "unified_label": "BROKER OFFLINE",
        "unified_short": "OFFLINE",
        "level": "offline",
        "evidence_badge": "disconnected",
    }
