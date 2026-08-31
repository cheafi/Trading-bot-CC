"""Forward outcomes — T+1/T+5/T+20 marks for calibration (Sprint 118)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_OUTCOMES_PATH = _DATA_DIR / "forward_outcomes.jsonl"
_CLOSED_TRADES_PATH = _DATA_DIR / "closed_trades.jsonl"
_HORIZON_DAYS = {"T+1": 1, "T+5": 5, "T+20": 20}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _existing_marks() -> Set[Tuple[str, str]]:
    marks: Set[Tuple[str, str]] = set()
    for row in load_forward_outcomes(limit=10000):
        did = str(row.get("decision_id") or "").strip()
        horizon = str(row.get("horizon") or "").strip()
        if did and horizon:
            marks.add((did, horizon))
    return marks


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


def run_forward_outcome_marks(*, as_of: Optional[date] = None) -> Dict[str, Any]:
    """Scheduler hook — append due T+1/T+5/T+20 marks for closed trades."""
    today = as_of or datetime.now(timezone.utc).date()
    if not _CLOSED_TRADES_PATH.is_file():
        return {"recorded": 0, "skipped": 0, "reason": "no_closed_trades"}

    existing = _existing_marks()
    recorded = 0
    skipped = 0
    for line in _CLOSED_TRADES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            trade = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        decision_id = str(trade.get("decision_id") or "").strip()
        if not decision_id:
            skipped += 1
            continue
        exit_day = _parse_date(trade.get("exit_time"))
        if not exit_day:
            skipped += 1
            continue
        ticker = str(trade.get("ticker") or "").upper()
        alpha_id = trade.get("alpha_id")
        mark_r = trade.get("r_multiple")
        mark_r_val: Optional[float] = None
        if mark_r is not None:
            try:
                mark_r_val = round(float(mark_r), 3)
            except (TypeError, ValueError):
                mark_r_val = None
        days_since = (today - exit_day).days
        for horizon, offset in _HORIZON_DAYS.items():
            if days_since < offset:
                continue
            if (decision_id, horizon) in existing:
                continue
            record_forward_outcome(
                decision_id=decision_id,
                ticker=ticker,
                horizon=horizon,
                mark_r=mark_r_val,
                alpha_id=str(alpha_id) if alpha_id else None,
            )
            existing.add((decision_id, horizon))
            recorded += 1
    return {"recorded": recorded, "skipped": skipped, "as_of": today.isoformat()}
