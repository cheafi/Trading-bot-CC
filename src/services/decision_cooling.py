"""Decision cooling — READY → COOLING → READY_TO_CONFIRM / CANCELLED (research_only)."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STATE_READY = "READY"
STATE_COOLING = "COOLING"
STATE_READY_TO_CONFIRM = "READY_TO_CONFIRM"
STATE_CANCELLED = "CANCELLED"

_CANCEL_REASONS = frozenset(
    {"WAIT", "quality_drop", "portfolio_change", "new_evidence", "operator_cancel"}
)

_sessions: Dict[str, Dict[str, Any]] = {}


def cooling_seconds() -> int:
    raw = os.getenv("DECISION_COOLING_SECONDS", "600")
    try:
        return max(1, int(raw))
    except ValueError:
        return 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def start_cooling(ticker: str, *, counterargument: str = "") -> Dict[str, Any]:
    """Begin cooling window — no deploy authority granted."""
    key = str(ticker or "").strip().upper()
    if not key:
        raise ValueError("ticker required")
    session_id = f"DC-{uuid.uuid4().hex[:10].upper()}"
    started = _now()
    ends = started + timedelta(seconds=cooling_seconds())
    session = {
        "session_id": session_id,
        "ticker": key,
        "state": STATE_COOLING,
        "started_at": _iso(started),
        "ends_at": _iso(ends),
        "counterargument": str(counterargument or "").strip(),
        "cancel_reason": None,
        "authority": "research_only",
    }
    _sessions[session_id] = session
    _log_workflow_event(key, "cooling_started", session_id=session_id)
    return get_status(session_id)


def get_status(session_id: str) -> Dict[str, Any]:
    sid = str(session_id or "").strip()
    session = _sessions.get(sid)
    if not session:
        raise ValueError("session not found")
    _advance_state(session)
    remaining = _remaining_seconds(session)
    return {
        **session,
        "cooling_seconds": cooling_seconds(),
        "remaining_seconds": remaining,
        "ready_to_confirm": session["state"] == STATE_READY_TO_CONFIRM,
        "cancelled": session["state"] == STATE_CANCELLED,
    }


def cancel_cooling(session_id: str, reason: str = "operator_cancel") -> Dict[str, Any]:
    sid = str(session_id or "").strip()
    session = _sessions.get(sid)
    if not session:
        raise ValueError("session not found")
    why = str(reason or "operator_cancel").strip()
    if why not in _CANCEL_REASONS:
        raise ValueError(f"reason must be one of: {', '.join(sorted(_CANCEL_REASONS))}")
    session["state"] = STATE_CANCELLED
    session["cancel_reason"] = why
    session["cancelled_at"] = _iso(_now())
    _log_workflow_event(session["ticker"], "cooling_cancelled", session_id=sid, reason=why)
    return get_status(sid)


def _remaining_seconds(session: Dict[str, Any]) -> int:
    if session["state"] in (STATE_CANCELLED, STATE_READY_TO_CONFIRM):
        return 0
    if session["state"] != STATE_COOLING:
        return cooling_seconds()
    try:
        ends = datetime.fromisoformat(str(session["ends_at"]).replace("Z", "+00:00"))
    except ValueError:
        return 0
    delta = (ends - _now()).total_seconds()
    return max(0, int(delta))


def _cooling_elapsed(session: Dict[str, Any]) -> bool:
    if session["state"] != STATE_COOLING:
        return False
    try:
        ends = datetime.fromisoformat(str(session["ends_at"]).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (ends - _now()).total_seconds() <= 0


def _advance_state(session: Dict[str, Any]) -> None:
    if session["state"] == STATE_COOLING and _cooling_elapsed(session):
        session["state"] = STATE_READY_TO_CONFIRM
        session["confirmed_at"] = _iso(_now())
        _log_workflow_event(
            session["ticker"],
            "cooling_ready_to_confirm",
            session_id=session["session_id"],
        )


def reset_sessions() -> None:
    """Test helper — clear in-memory cooling sessions."""
    _sessions.clear()


def _log_workflow_event(ticker: str, event: str, **meta: Any) -> None:
    try:
        from src.engines.decision_journal import DecisionJournal

        journal = DecisionJournal()
        journal.record(
            ticker=ticker,
            decision="WORKFLOW",
            notes=[f"workflow:{event}", *(f"{k}={v}" for k, v in meta.items())],
            factors={"workflow_event": event, **meta},
        )
    except Exception as exc:
        logger.debug("workflow journal hook skipped: %s", exc)
