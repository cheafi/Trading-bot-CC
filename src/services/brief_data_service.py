"""
BriefDataService — Sprint 73 (debt reduction)
===============================================
Single source of truth for loading and caching brief JSON files.
Replaces 5 duplicate _load_brief() functions across routers.
"""

from __future__ import annotations

import glob
import errno
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BRIEF_CACHE: Optional[Dict] = None
_BRIEF_CACHE_TS: float = 0
_BRIEF_CACHE_TTL = 120  # 2 min — brief files change at most daily
_BRIEF_FAILURE_CACHE_TTL = 60  # short — iCloud/Docker mounts recover quickly
_BRIEF_CACHE_FAILED = False
_BRIEF_LAST_WARNING_TS = 0.0
_BRIEF_READ_RETRIES = 3


def _brief_dir() -> str:
    """Resolve data/ directory relative to project root."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _brief_disk_cache_path() -> str:
    return os.path.join(_brief_dir(), "cache", "brief_latest.json")


def _read_brief_file(path: str) -> Dict[str, Any]:
    """Read one brief JSON file with short retries (macOS bind mounts / iCloud)."""
    last_exc: Exception | None = None
    for attempt in range(_BRIEF_READ_RETRIES):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except OSError as exc:
            last_exc = exc
            if exc.errno == errno.EDEADLK and attempt < _BRIEF_READ_RETRIES - 1:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last_exc = exc
            break
    if last_exc:
        raise last_exc
    return {}


def _write_brief_disk_cache(data: Dict[str, Any]) -> None:
    if not data:
        return
    path = _brief_disk_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:
        logger.debug("[BriefData] Disk cache write skipped: %s", exc)


def _load_brief_disk_cache() -> Dict[str, Any]:
    path = _brief_disk_cache_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("[BriefData] Disk cache read failed: %s", exc)
        return {}


def load_brief() -> Dict[str, Any]:
    """
    Load the latest brief-*.json file. Cached for 2 minutes.
    Returns empty dict on failure — never raises.
    """
    global _BRIEF_CACHE, _BRIEF_CACHE_FAILED, _BRIEF_CACHE_TS, _BRIEF_LAST_WARNING_TS

    now = time.time()
    cache_ttl = _BRIEF_FAILURE_CACHE_TTL if _BRIEF_CACHE_FAILED else _BRIEF_CACHE_TTL
    if _BRIEF_CACHE is not None and (now - _BRIEF_CACHE_TS) < cache_ttl:
        return _BRIEF_CACHE

    try:
        files = sorted(glob.glob(os.path.join(_brief_dir(), "brief-*.json")))
        if files:
            data = _read_brief_file(files[-1])
            if data:
                _BRIEF_CACHE = data
                _BRIEF_CACHE_TS = now
                _BRIEF_CACHE_FAILED = False
                _write_brief_disk_cache(data)
                logger.debug("[BriefData] Loaded %s", os.path.basename(files[-1]))
                return data
    except OSError as exc:
        if exc.errno == errno.EDEADLK:
            logger.debug("[BriefData] Brief file temporarily unavailable: %s", exc)
        elif now - _BRIEF_LAST_WARNING_TS > 300:
            logger.warning("[BriefData] Brief file unavailable: %s", exc)
            _BRIEF_LAST_WARNING_TS = now
    except Exception as exc:
        if now - _BRIEF_LAST_WARNING_TS > 300:
            logger.warning("[BriefData] Failed to load brief file: %s", exc)
            _BRIEF_LAST_WARNING_TS = now

    cached = _load_brief_disk_cache()
    if cached:
        _BRIEF_CACHE = cached
        _BRIEF_CACHE_TS = now
        _BRIEF_CACHE_FAILED = False
        logger.debug("[BriefData] Loaded brief from disk cache")
        return cached

    _BRIEF_CACHE = {}
    _BRIEF_CACHE_TS = now
    _BRIEF_CACHE_FAILED = True
    return _BRIEF_CACHE


def find_signal(ticker: str, brief_data: Optional[Dict] = None) -> tuple:
    """
    Find a ticker in brief data. Returns (signal_dict, section_name).
    If brief_data is None, loads it automatically.
    """
    if brief_data is None:
        brief_data = load_brief()

    ticker = ticker.upper()
    for section in ("actionable", "watch", "review"):
        for item in brief_data.get(section, []):
            if item.get("ticker", "").upper() == ticker:
                return item, section
    return {}, "unknown"


def build_brief_lookup(brief_data: Optional[Dict] = None) -> Dict[str, Dict]:
    """Build a ticker → signal lookup from brief data."""
    if brief_data is None:
        brief_data = load_brief()

    lookup: Dict[str, Dict] = {}
    for section in ("actionable", "watch", "review"):
        for item in brief_data.get(section, []):
            t = item.get("ticker", "").upper()
            if t:
                lookup[t] = item
    return lookup


def all_brief_tickers(brief_data: Optional[Dict] = None) -> List[str]:
    """Return deduplicated list of all tickers across brief sections."""
    if brief_data is None:
        brief_data = load_brief()

    seen: List[str] = []
    for section in ("actionable", "watch", "review"):
        for item in brief_data.get(section, []):
            t = item.get("ticker", "").upper()
            if t and t not in seen:
                seen.append(t)
    return seen


# ─── Class wrapper (backwards-compat) ───────────────────────────────────────
class BriefDataService:
    """
    Class facade over module-level functions.
    Callers that do ``from ... import BriefDataService`` get this.
    All methods delegate to the cached module-level implementations.
    """

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Load (or return cached) brief data."""
        return load_brief()

    @classmethod
    def find_signal(cls, ticker: str, brief_data: Optional[Dict] = None) -> tuple:
        """Find a ticker in brief data. Returns (signal_dict, section_name)."""
        return find_signal(ticker, brief_data)

    @classmethod
    def build_lookup(cls, brief_data: Optional[Dict] = None) -> Dict[str, Dict]:
        """Build ticker → signal lookup."""
        return build_brief_lookup(brief_data)

    @classmethod
    def all_tickers(cls, brief_data: Optional[Dict] = None) -> List[str]:
        """Return all tickers across brief sections."""
        return all_brief_tickers(brief_data)

    @classmethod
    def invalidate_cache(cls) -> None:
        """Force a cache miss on next load."""
        global _BRIEF_CACHE, _BRIEF_CACHE_FAILED, _BRIEF_CACHE_TS
        _BRIEF_CACHE = None
        _BRIEF_CACHE_FAILED = False
        _BRIEF_CACHE_TS = 0
