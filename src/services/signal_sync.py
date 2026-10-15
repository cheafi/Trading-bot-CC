"""
Cross-platform signal sync (AI-Trader / Lean-inspired envelope).

Research and paper only — no broker credentials in payloads.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
SYNC_DIR = _REPO / "data" / "signal_sync"
SCHEMA_VERSION = "cc.signal.v1"

_MARKETS = ("equity", "crypto", "forex", "option", "future")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_from_signal_board(item: dict[str, Any], regime: dict[str, Any]) -> dict[str, Any]:
    side = str(item.get("side") or "BUY").upper()
    return {
        "symbol": item.get("ticker"),
        "asset_class": "crypto" if str(item.get("ticker", "")).endswith("-USD") else "equity",
        "direction": "LONG" if side == "BUY" else "SHORT",
        "entry": item.get("entry"),
        "stop": item.get("stop"),
        "target": item.get("target1"),
        "score": item.get("score"),
        "setup": item.get("setup"),
        "authority": item.get("authority") or "Paper signal",
        "regime": regime.get("label"),
    }


def build_sync_export(
    *,
    source: str = "signal_board",
    board: dict[str, Any] | None = None,
    engine_recs: list[dict[str, Any]] | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    from src.services.signal_board import get_latest

    board = board if board is not None else get_latest() or {}
    regime = board.get("regime") or {}
    signals: list[dict[str, Any]] = []
    buckets = board.get("buckets") or {}
    for bucket in ("strong_buy", "buy", "sell", "strong_sell"):
        for row in buckets.get(bucket) or []:
            if isinstance(row, dict):
                signals.append({**_row_from_signal_board(row, regime), "bucket": bucket})

    for rec in engine_recs or []:
        if not isinstance(rec, dict):
            continue
        ticker = rec.get("ticker") or rec.get("symbol")
        if not ticker:
            continue
        signals.append(
            {
                "symbol": ticker,
                "asset_class": "equity",
                "direction": str(rec.get("action") or "WATCH").upper(),
                "entry": rec.get("entry_price"),
                "stop": rec.get("stop_price"),
                "target": rec.get("target_price"),
                "score": rec.get("score"),
                "setup": rec.get("setup"),
                "authority": "engine_cache",
                "source": "engine",
            }
        )

    return {
        "schema": SCHEMA_VERSION,
        "sync_id": str(uuid.uuid4()),
        "generated_at": _now(),
        "source": source,
        "agent_id": agent_id,
        "markets_supported": list(_MARKETS),
        "execution_permission": False,
        "signals": signals[:200],
        "meta": {
            "board_as_of": board.get("generated_at"),
            "regime": regime.get("label"),
            "count": len(signals),
        },
    }


def import_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema: {payload.get('schema')}")
    if payload.get("execution_permission"):
        raise ValueError("import rejects execution_permission=true payloads")
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    sync_id = str(payload.get("sync_id") or uuid.uuid4())
    path = SYNC_DIR / f"inbox_{sync_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, "sync_id": sync_id, "path": str(path.relative_to(_REPO))}
