"""CUSIP → ticker resolution for 13F holdings (research lookup table + issuer hints)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional

_MAP_PATH = Path("data/research/cusip_ticker_map.json")
_CACHE: Optional[Dict[str, str]] = None

# Common US large-cap CUSIPs (extend via data/research/cusip_ticker_map.json).
_BUILTIN: Dict[str, str] = {
    "037833100": "AAPL",
    "594918104": "MSFT",
    "67066G104": "NVDA",
    "02079K305": "GOOGL",
    "02079K107": "GOOG",
    "023135106": "AMZN",
    "88160R101": "TSLA",
    "30303M102": "META",
    "78462F103": "SPY",
    "464287200": "SPY",
}


def _load_map() -> Dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    merged = dict(_BUILTIN)
    if _MAP_PATH.exists():
        try:
            with open(_MAP_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str):
                        merged[k.upper().strip()] = v.upper().strip()
        except Exception:
            pass
    _CACHE = merged
    return merged


def resolve_ticker_from_cusip(cusip: str, *, issuer: str = "") -> Optional[str]:
    c = str(cusip or "").upper().strip()
    if len(c) == 9 and c.isalnum():
        hit = _load_map().get(c)
        if hit:
            return hit
    name = str(issuer or "").upper()
    m = re.search(r"\b([A-Z]{1,6})\b(?:\s+CORP|\s+INC|\s+CO\b|\s+LTD)", name)
    if m:
        return m.group(1)
    return None
