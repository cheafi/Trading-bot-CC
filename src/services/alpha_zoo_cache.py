"""Cached alpha zoo bench — overnight / on-demand refresh."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.services.alpha_zoo_bench import bench_alphas_zoo
from src.services.research_safety import sanitize_research_payload

logger = logging.getLogger(__name__)

_CACHE = Path("data") / "research" / "alpha_zoo_latest.json"
_DEFAULT_TICKER = "SPY"
_DEFAULT_COMPUTE = 478


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_cached_zoo() -> Optional[Dict[str, Any]]:
    if not _CACHE.exists():
        return None
    try:
        with open(_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.debug("alpha zoo cache read failed: %s", exc)
        return None


def save_cached_zoo(payload: Dict[str, Any]) -> Dict[str, Any]:
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    row = {**payload, "cached_at": _now(), "cache_path": str(_CACHE)}
    with open(_CACHE, "w", encoding="utf-8") as f:
        json.dump(row, f, indent=2)
    return row


async def refresh_alpha_zoo_cache(
    mds,
    *,
    ticker: str = _DEFAULT_TICKER,
    period: str = "2y",
    compute_limit: int = _DEFAULT_COMPUTE,
) -> Dict[str, Any]:
    started = time.time()
    result = await bench_alphas_zoo(
        mds, ticker, period=period, compute_limit=compute_limit
    )
    result["refresh_duration_sec"] = round(time.time() - started, 2)
    if result.get("ok"):
        save_cached_zoo(result)
    return sanitize_research_payload(result)


def cached_zoo_fresh(*, max_age_sec: int = 86400) -> bool:
    row = load_cached_zoo()
    if not row or not row.get("cached_at"):
        return False
    try:
        raw = str(row["cached_at"]).strip()
        if raw.endswith("+00:00Z"):
            raw = raw[:-1]
        elif raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        ts = datetime.fromisoformat(raw)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age <= max_age_sec
    except Exception:
        return False
