"""Cache 13F holdings QoQ — reduce SEC EDGAR load."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_STORE = Path("data") / "research" / "13f_holdings_cache.json"
_TTL = 7 * 86400  # 7d — 13F is quarterly


def _load_store() -> Dict[str, Any]:
    if not _STORE.exists():
        return {"entries": {}}
    try:
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data
    except Exception:
        pass
    return {"entries": {}}


def _save_store(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _key(cik: str, ticker: str) -> str:
    return f"{str(cik).strip()}:{ticker.upper().strip()}"


def get_cached_holdings(cik: str, ticker: str) -> Optional[Dict[str, Any]]:
    store = _load_store()
    entry = store.get("entries", {}).get(_key(cik, ticker))
    if not isinstance(entry, dict):
        return None
    try:
        ts = float(entry.get("ts") or 0)
        if time.time() - ts > _TTL:
            return None
    except (TypeError, ValueError):
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


def put_cached_holdings(cik: str, ticker: str, payload: Dict[str, Any]) -> None:
    store = _load_store()
    store.setdefault("entries", {})[_key(cik, ticker)] = {
        "ts": time.time(),
        "cached_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
    _save_store(store)


async def fetch_holdings_qoq_cached(cik: str, ticker: str) -> Dict[str, Any]:
    hit = get_cached_holdings(cik, ticker)
    if hit:
        out = dict(hit)
        out["from_cache"] = True
        return out
    from src.services.filing_13f_holdings import fetch_13f_holdings_qoq

    fresh = await fetch_13f_holdings_qoq(cik=cik, ticker=ticker)
    if fresh.get("ok"):
        put_cached_holdings(cik, ticker, fresh)
    fresh["from_cache"] = False
    return fresh
