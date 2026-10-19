"""Durable idempotency store for ExecutionGateway.submit()."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.state_paths import atomic_write_text, execution_idempotency_path

_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def validate_idempotency_key(key: str) -> str:
    cleaned = str(key or "").strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(cleaned):
        raise ValueError(
            "idempotency_key must be 8–128 chars (letters, digits, _ or -)"
        )
    return cleaned


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdempotencyStore:
    """File-backed idempotency records (fail-closed on corrupt load)."""

    def __init__(self, *, path: Optional[Path] = None) -> None:
        self._path = path or execution_idempotency_path()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._persist_ok = True
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

    def _save(self) -> None:
        try:
            payload = {"records": self._records, "updated_at": _utcnow()}
            atomic_write_text(self._path, json.dumps(payload, indent=2))
            self._persist_ok = True
        except Exception:
            self._persist_ok = False

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._records.get(key)

    def begin(self, key: str, *, local_order_id: str) -> str:
        """Reserve key. Returns 'new', 'replay', or 'in_flight'."""
        existing = self._records.get(key)
        if existing:
            status = str(existing.get("status") or "")
            if status == "completed":
                return "replay"
            if status == "in_flight":
                return "in_flight"
        self._records[key] = {
            "status": "in_flight",
            "local_order_id": local_order_id,
            "response": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        self._save()
        return "new"

    def complete(self, key: str, response: Dict[str, Any]) -> None:
        row = self._records.get(key)
        if not row:
            return
        row["status"] = "completed"
        row["response"] = response
        row["updated_at"] = _utcnow()
        self._save()

    def abort(self, key: str) -> None:
        """Release in-flight reservation when no broker submit occurred."""
        row = self._records.get(key)
        if not row or row.get("status") != "in_flight":
            return
        del self._records[key]
        self._save()


idempotency_store = IdempotencyStore()
