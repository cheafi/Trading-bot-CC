"""
BriefDataService — Sprint 73 (debt reduction)
===============================================
Single source of truth for loading and caching brief JSON files.
Replaces 5 duplicate _load_brief() functions across routers.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BRIEF_CACHE: Optional[Dict] = None
_BRIEF_CACHE_TS: float = 0
_BRIEF_CACHE_TTL = 120  # 2 min — brief files change at most daily


def _brief_dir() -> str:
    """Resolve data/ directory relative to project root."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def load_brief() -> Dict[str, Any]:
    """
    Load the latest brief-*.json file. Cached for 2 minutes.
    Returns empty dict on failure — never raises.
    """
    global _BRIEF_CACHE, _BRIEF_CACHE_TS

    now = time.time()
    if _BRIEF_CACHE is not None and (now - _BRIEF_CACHE_TS) < _BRIEF_CACHE_TTL:
        return _BRIEF_CACHE

    try:
        files = sorted(glob.glob(os.path.join(_brief_dir(), "brief-*.json")))
        if files:
            with open(files[-1]) as f:
                data = json.load(f)
            _BRIEF_CACHE = data
            _BRIEF_CACHE_TS = now
            logger.debug("[BriefData] Loaded %s", os.path.basename(files[-1]))
            return data
    except Exception:
        logger.exception("[BriefData] Failed to load brief file")

    return {}


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
        global _BRIEF_CACHE, _BRIEF_CACHE_TS
        _BRIEF_CACHE = None
        _BRIEF_CACHE_TS = 0
