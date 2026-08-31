"""MIE Phase 1 — surface usage log for trust / deletion ceremony (CCX-132)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_LOG_PATH = _DATA_DIR / "surface_usage.jsonl"
_AI_LOG_PATH = _DATA_DIR / "ai_usage.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_surface_event(
    *,
    surface: str,
    event: str,
    tab: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Log open / expand / dismiss / ignore for Meta Intelligence."""
    row = {
        "as_of": _utcnow_iso(),
        "surface": str(surface or "unknown")[:64],
        "event": str(event or "open")[:32],
        "tab": str(tab or "")[:32],
        "meta": meta or {},
        "authority": "research_only",
    }
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        logger.debug("usage log persist failed: %s", exc)
    return row


def load_usage_events(*, limit: int = 500) -> List[Dict[str, Any]]:
    if not _LOG_PATH.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in _LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def record_ai_call(
    *,
    task: str,
    provider: str,
    model: str = "",
    success: bool = True,
    chars: int = 0,
    error: str = "",
) -> Dict[str, Any]:
    """Log LLM invocation for CCX-132 meta intelligence (research_only)."""
    row = {
        "as_of": _utcnow_iso(),
        "task": str(task or "unknown")[:64],
        "provider": str(provider or "none")[:32],
        "model": str(model or "")[:64],
        "success": bool(success),
        "chars": int(chars or 0),
        "error": str(error or "")[:200],
        "authority": "research_only",
    }
    try:
        _AI_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AI_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        logger.debug("ai usage log persist failed: %s", exc)
    return row


def build_usage_summary(*, days: int = 90) -> Dict[str, Any]:
    rows = load_usage_events(limit=2000)
    counts: Dict[str, int] = {}
    dismiss: Dict[str, int] = {}
    for r in rows:
        surf = str(r.get("surface") or "unknown")
        counts[surf] = counts.get(surf, 0) + 1
        if str(r.get("event") or "") in ("dismiss", "ignore"):
            dismiss[surf] = dismiss.get(surf, 0) + 1
    zero_use_candidates = [
        s
        for s in (
            "buffett_strip",
            "rank_hero_wait",
            "discovery_equal_nav",
            "ai_narrative",
            "duplicate_gate",
        )
        if counts.get(s, 0) == 0
    ]
    return {
        "as_of": _utcnow_iso(),
        "authority": "research_only",
        "window_days": days,
        "total_events": len(rows),
        "by_surface": counts,
        "dismiss_by_surface": dismiss,
        "deletion_candidates": zero_use_candidates,
        "recent": rows[-10:],
    }
