"""Lowest-order execution boundary — dry_run default, live gate, simulation ledger."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.live_trading_gate import authorize_live_order
from src.core.state_paths import atomic_write_jsonl_append, simulation_ledger_path

logger = logging.getLogger(__name__)


class LiveTradingRequiredError(RuntimeError):
    """Raised when dry_run=False without full live authorisation."""


def assert_live_order_permitted(*, dry_run: bool, account: str = "") -> None:
    """Raise if caller requests live execution without authorisation."""
    if dry_run:
        return
    auth = authorize_live_order(account)
    if not auth.live_allowed:
        missing = ", ".join(auth.missing) or "unknown"
        raise LiveTradingRequiredError(
            f"Live order blocked — missing gate requirements: {missing}"
        )


def append_simulation_ledger(entry: Dict[str, Any]) -> str:
    """Append-only simulation ledger for dry-run orders."""
    path = simulation_ledger_path()
    row = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **entry,
    }
    atomic_write_jsonl_append(path, row)
    return str(path)


def record_dry_run_order(
    *,
    source: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "MKT",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a dry-run order without touching the live broker."""
    payload: Dict[str, Any] = {
        "mode": "dry_run",
        "source": source,
        "symbol": str(symbol or "").upper(),
        "side": str(side or "").upper(),
        "quantity": quantity,
        "order_type": order_type,
    }
    if extra:
        payload.update(extra)
    append_simulation_ledger(payload)
    logger.info(
        "[DRY RUN] recorded %s %s x%s (%s) via %s",
        payload["side"],
        payload["symbol"],
        payload["quantity"],
        payload["order_type"],
        source,
    )
