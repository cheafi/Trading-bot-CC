"""PM research memory — append-only notes per ticker (fixed store path)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STORE = Path("data") / "pm_memory.json"
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _sanitize_ticker(ticker: str) -> Optional[str]:
    t = (ticker or "").strip().upper()
    return t if t and _TICKER_RE.match(t) else None


def _load() -> Dict[str, Any]:
    if not _STORE.exists():
        return {"entries": {}}
    try:
        with open(_STORE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("pm_memory load: %s", exc)
    return {"entries": {}}


def _save(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_memory(ticker: str) -> Dict[str, Any]:
    t = _sanitize_ticker(ticker)
    if not t:
        return {"ticker": ticker, "entries": [], "summary": None}
    data = _load()
    entries = (data.get("entries") or {}).get(t, [])
    summary = None
    if entries:
        latest = entries[-1]
        summary = {
            "why_liked": latest.get("why_liked"),
            "original_thesis": latest.get("original_thesis"),
            "expected_catalyst": latest.get("expected_catalyst"),
            "when": latest.get("created_at"),
            "next_review": latest.get("next_review"),
        }
    return {"ticker": t, "entries": entries[-20:], "summary": summary}


def append_note(
    ticker: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    t = _sanitize_ticker(ticker)
    if not t:
        raise ValueError("Invalid ticker")
    entry = {
        "created_at": _now(),
        "why_liked": (body.get("why_liked") or "")[:500],
        "original_thesis": (body.get("original_thesis") or "")[:500],
        "expected_catalyst": (body.get("expected_catalyst") or "")[:200],
        "pm_note": (body.get("pm_note") or "")[:1000],
        "challenge_memo": (body.get("challenge_memo") or "")[:1000],
        "next_review": body.get("next_review"),
        "post_trade_lesson": (body.get("post_trade_lesson") or "")[:500],
    }
    data = _load()
    data.setdefault("entries", {}).setdefault(t, []).append(entry)
    _save(data)
    return entry


def build_thesis_block(ticker: str, stock_intel: Dict[str, Any]) -> Dict[str, Any]:
    """Composite thesis for 360 page."""
    narrative = stock_intel.get("narrative") or {}
    pm_answer = stock_intel.get("pm_answer") or {}
    unified = stock_intel.get("unified_decision") or {}
    mem = get_memory(ticker)
    return {
        "bull_case": narrative.get("bull_case") or [],
        "bear_case": narrative.get("bear_case") or [],
        "base_case": pm_answer.get("one_line") or narrative.get("one_line_bull"),
        "improves_conviction": pm_answer.get("thesis_confirms") or [],
        "weakens_conviction": narrative.get("contradictions") or [],
        "invalidates": unified.get("invalidation") or pm_answer.get("thesis_breaks"),
        "monitor_next": [
            "Catalyst calendar",
            "Stop / invalidation",
            "Regime gate",
        ],
        "pm_memory": mem.get("summary"),
        "challenge_memo": (mem.get("entries") or [{}])[-1].get("challenge_memo")
        if mem.get("entries")
        else None,
    }
