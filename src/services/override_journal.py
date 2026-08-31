"""Override journal — log when operator bypasses CC advice (CCX-044 / CCX-133)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_JOURNAL_PATH = _DATA_DIR / "override_journal.jsonl"
_COOLDOWN_HOURS = 24


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_override(
    *,
    advice_class: str,
    action: str,
    reason: str = "",
    ticker: str = "",
    decision_id: str = "",
) -> Dict[str, Any]:
    """Append override event — research/audit only."""
    row = {
        "as_of": _utcnow_iso(),
        "advice_class": str(advice_class or "unknown")[:64],
        "action": str(action or "ignored")[:32],
        "reason": str(reason or "")[:500],
        "ticker": str(ticker or "").upper()[:10],
        "decision_id": str(decision_id or "")[:64],
        "authority": "research_only",
    }
    try:
        _JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _JOURNAL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        logger.debug("override journal persist failed: %s", exc)
    return row


def load_overrides(*, limit: int = 50) -> List[Dict[str, Any]]:
    if not _JOURNAL_PATH.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in _JOURNAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def cooldown_status(*, hours: int = _COOLDOWN_HOURS) -> Dict[str, Any]:
    """True if an override occurred within cooldown window."""
    rows = load_overrides(limit=20)
    if not rows:
        return {"in_cooldown": False, "last_override": None, "cooldown_hours": hours}
    last = rows[-1]
    last_ts = str(last.get("as_of") or "")
    in_cooldown = False
    try:
        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        delta_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
        in_cooldown = delta_h < float(hours)
    except ValueError:
        pass
    return {
        "in_cooldown": in_cooldown,
        "last_override": last,
        "cooldown_hours": hours,
        "authority": "research_only",
    }


def build_override_summary() -> Dict[str, Any]:
    rows = load_overrides(limit=100)
    by_class: Dict[str, int] = {}
    for r in rows:
        cls = str(r.get("advice_class") or "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
    return {
        "total": len(rows),
        "by_advice_class": by_class,
        "recent": rows[-5:],
        "cooldown": cooldown_status(),
        "authority": "research_only",
        "as_of": _utcnow_iso(),
    }
