"""Forward outcomes — T+1/T+5/T+20 marks for calibration (Sprint 118)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_OUTCOMES_PATH = _DATA_DIR / "forward_outcomes.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_forward_outcome(
    *,
    decision_id: str,
    ticker: str,
    horizon: str,
    mark_r: Optional[float] = None,
    mark_bps: Optional[float] = None,
    alpha_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append forward outcome mark linked to decision_id."""
    row = {
        "decision_id": decision_id,
        "ticker": ticker.upper(),
        "horizon": horizon,
        "mark_r": mark_r,
        "mark_bps": mark_bps,
        "alpha_id": alpha_id,
        "as_of": _utcnow_iso(),
        "authority": "research_only",
    }
    try:
        _OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _OUTCOMES_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        logger.debug("forward outcome persist failed: %s", exc)
    return row


def load_forward_outcomes(
    *,
    decision_id: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    if not _OUTCOMES_PATH.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in _OUTCOMES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if decision_id and row.get("decision_id") != decision_id:
            continue
        if ticker and str(row.get("ticker") or "").upper() != ticker.upper():
            continue
        rows.append(row)
    return rows[-limit:]
