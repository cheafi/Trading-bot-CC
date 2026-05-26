"""Short TTL caches for P2 surfaces (reduce repeat latency)."""

from __future__ import annotations

import time
from typing import Any, Optional


def get_cached(state: Any, key: str) -> Optional[Any]:
    entry = getattr(state, key, None)
    if isinstance(entry, dict) and entry.get("exp", 0) > time.time():
        return entry.get("data")
    return None


def set_cached(state: Any, key: str, data: Any, ttl_sec: int = 120) -> None:
    setattr(state, key, {"exp": time.time() + ttl_sec, "data": data})
