"""Durable idempotency store for ExecutionGateway.submit()."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.state_paths import atomic_write_text, execution_idempotency_path

_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

STATUS_IN_FLIGHT = "in_flight"
STATUS_COMPLETED = "completed"
STATUS_UNKNOWN_SUBMITTED = "unknown_submitted"


def validate_idempotency_key(key: str) -> str:
    cleaned = str(key or "").strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(cleaned):
        raise ValueError(
            "idempotency_key must be 8–128 chars (letters, digits, _ or -)"
        )
    return cleaned


def fingerprint_order_payload(
    *,
    ticker: str,
    side: str,
    quantity: int,
    order_type: str,
    limit_price: Optional[float],
    stop_price: Optional[float],
    broker_scope: str,
    account_scope: str = "",
) -> str:
    """Stable hash for idempotency key binding."""
    canonical = {
        "ticker": str(ticker or "").upper(),
        "side": str(side or "").lower(),
        "quantity": int(quantity),
        "order_type": str(order_type or "").lower(),
        "limit_price": limit_price,
        "stop_price": stop_price,
        "broker_scope": str(broker_scope or ""),
        "account_scope": str(account_scope or "").upper(),
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdempotencyStore:
    """File-backed idempotency records (fail-closed on corrupt load)."""

    def __init__(self, *, path: Optional[Path] = None) -> None:
        self._path = path or execution_idempotency_path()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._persist_ok = True
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("records") if isinstance(raw, dict) else {}
            if isinstance(rows, dict):
                self._records = {str(k): v for k, v in rows.items() if isinstance(v, dict)}
        except Exception:
            self._persist_ok = False

    def _save(self) -> bool:
        try:
            payload = {"records": self._records, "updated_at": _utcnow()}
            atomic_write_text(self._path, json.dumps(payload, indent=2))
            self._persist_ok = True
            return True
        except Exception:
            self._persist_ok = False
            return False

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._records.get(key)

    def begin(
        self,
        key: str,
        *,
        local_order_id: str,
        payload_hash: str,
    ) -> str:
        """
        Reserve key atomically.

        Returns: new | replay | in_flight | conflict | unknown_blocked | persist_failed
        """
        with self._lock:
            existing = self._records.get(key)
            if existing:
                status = str(existing.get("status") or "")
                stored_hash = str(existing.get("payload_hash") or "")
                if stored_hash and payload_hash and stored_hash != payload_hash:
                    return "conflict"
                if status == STATUS_COMPLETED:
                    return "replay"
                if status == STATUS_UNKNOWN_SUBMITTED:
                    return "unknown_blocked"
                if status == STATUS_IN_FLIGHT:
                    return "in_flight"

            self._records[key] = {
                "status": STATUS_IN_FLIGHT,
                "local_order_id": local_order_id,
                "payload_hash": payload_hash,
                "response": None,
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
            }
            if not self._save():
                self._records.pop(key, None)
                return "persist_failed"
            return "new"

    def complete(self, key: str, response: Dict[str, Any]) -> bool:
        with self._lock:
            row = self._records.get(key)
            if not row:
                return False
            row["status"] = STATUS_COMPLETED
            row["response"] = response
            row["updated_at"] = _utcnow()
            if self._save():
                return True
            row["status"] = STATUS_UNKNOWN_SUBMITTED
            row["unknown_reason"] = "result_persist_failed"
            row["response"] = response
            row["updated_at"] = _utcnow()
            self._save()
            return False

    def mark_unknown_submitted(
        self, key: str, *, reason: str, partial_response: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Broker outcome uncertain — never delete the reservation."""
        with self._lock:
            row = self._records.get(key)
            if not row:
                return False
            row["status"] = STATUS_UNKNOWN_SUBMITTED
            row["unknown_reason"] = reason
            if partial_response is not None:
                row["response"] = partial_response
            row["updated_at"] = _utcnow()
            if self._save():
                return True
            # Memory retains UNKNOWN — same process must block retry even if disk stale.
            return False

    def abort(self, key: str) -> bool:
        """Release in-flight reservation only before broker submit."""
        with self._lock:
            row = self._records.get(key)
            if not row or row.get("status") != STATUS_IN_FLIGHT:
                return True
            snapshot = dict(row)
            del self._records[key]
            if self._save():
                return True
            self._records[key] = snapshot
            return False


idempotency_store = IdempotencyStore()
