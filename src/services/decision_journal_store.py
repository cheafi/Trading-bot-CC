"""
Decision Journal Store — append-only persistence for DecisionEvent records.

JSONL under data/decision_journal/ with optional SQLite index for lookups.
Corrections are new events (never in-place edits). Research surfaces always
authority_effect=none; blocked events strip sizing/handoff fields.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.services.decision_journal import (
    DecisionEvent,
    EVENT_TYPES,
    _RESEARCH_SURFACES,
    _strip_sizing_if_blocked,
)

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal"
)
_EVENTS_PATH = os.environ.get("DECISION_JOURNAL_EVENTS_PATH") or os.path.join(
    _DATA_DIR, "events.jsonl"
)
_INDEX_PATH = os.environ.get("DECISION_JOURNAL_INDEX_PATH") or os.path.join(
    _DATA_DIR, "index.db"
)

_SIZING_FIELDS = frozenset({"position_shares", "position_dollar", "risk_pct"})


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _get_index(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _INDEX_PATH
    _ensure_dir(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS journal_events (
            event_id       TEXT PRIMARY KEY,
            timestamp      TEXT NOT NULL,
            session_id     TEXT,
            surface        TEXT,
            ticker         TEXT,
            event_type     TEXT,
            authority_effect TEXT DEFAULT 'none',
            line_offset    INTEGER,
            correction_of  TEXT,
            recorded_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_je_session ON journal_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_je_ticker ON journal_events(ticker);
        CREATE INDEX IF NOT EXISTS idx_je_type ON journal_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_je_ts ON journal_events(timestamp);
        """
    )
    return conn


def event_from_dict(data: Dict[str, Any]) -> DecisionEvent:
    """Reconstruct DecisionEvent from persisted dict."""
    fields = {k: v for k, v in data.items() if k in DecisionEvent.__dataclass_fields__}
    return DecisionEvent(**fields)


def _sanitize_for_persist(event: DecisionEvent) -> DecisionEvent:
    """Enforce append-only store rules before write."""
    if event.event_type not in EVENT_TYPES:
        event.event_type = "WATCH_CANDIDATE"
    event = _strip_sizing_if_blocked(event)
    if str(event.surface or "").lower() in _RESEARCH_SURFACES:
        event.blocked_actions = sorted(
            set(event.blocked_actions or [])
            | {"deploy", "size", "live_handoff", "paper_draft"}
        )
        event.authority_effect = "none"
    blocked = set(a.lower() for a in (event.blocked_actions or []))
    if "deploy" in blocked or "size" in blocked or "live_handoff" in blocked:
        event.position_shares = None
        event.position_dollar = None
        event.risk_pct = None
    event.authority_effect = "none"
    return event


class DecisionJournalStore:
    """Append-only JSONL store with optional SQLite index."""

    def __init__(
        self,
        events_path: Optional[str] = None,
        index_path: Optional[str] = None,
        *,
        use_index: bool = True,
    ) -> None:
        self.events_path = events_path or _EVENTS_PATH
        self.index_path = index_path or _INDEX_PATH
        self.use_index = use_index
        _ensure_dir(self.events_path)

    def _append_line(self, payload: Dict[str, Any]) -> int:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line)
            offset = f.tell() - len(line.encode("utf-8"))
        return max(0, offset)

    def _index_event(
        self,
        event: DecisionEvent,
        *,
        line_offset: int,
        correction_of: Optional[str] = None,
    ) -> None:
        if not self.use_index:
            return
        try:
            conn = _get_index(self.index_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO journal_events
                (event_id, timestamp, session_id, surface, ticker, event_type,
                 authority_effect, line_offset, correction_of, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.session_id,
                    event.surface,
                    event.ticker,
                    event.event_type,
                    event.authority_effect,
                    line_offset,
                    correction_of,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("journal index write failed: %s", exc)

    def persist(
        self,
        event: DecisionEvent,
        *,
        correction_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append one event — never updates existing rows."""
        event = _sanitize_for_persist(event)
        payload = event.to_dict()
        payload["record_type"] = "decision_event"
        if correction_of:
            payload["correction_of"] = correction_of
            payload["notes"] = (
                f"correction of {correction_of}; "
                + str(payload.get("notes") or "")
            ).strip()
        offset = self._append_line(payload)
        self._index_event(event, line_offset=offset, correction_of=correction_of)
        return payload

    def persist_batch(
        self,
        events: List[DecisionEvent],
        *,
        session_id: str = "",
        dedupe_keys: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Persist multiple events; optional dedupe by ticker+type+session."""
        written = 0
        deduped = 0
        seen = set(dedupe_keys or [])
        for evt in events:
            key = f"{evt.session_id}:{evt.ticker}:{evt.event_type}"
            if key in seen:
                deduped += 1
                continue
            if session_id and not evt.session_id:
                evt.session_id = session_id
            self.persist(evt)
            seen.add(key)
            written += 1
        return {"written": written, "deduped": deduped, "total_indexed": self.count()}

    def load_all(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.events_path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.events_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if limit is not None:
            return rows[-limit:]
        return rows

    def load_by_event_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        if self.use_index:
            try:
                conn = _get_index(self.index_path)
                row = conn.execute(
                    "SELECT line_offset FROM journal_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                conn.close()
                if row and row["line_offset"] is not None:
                    return self._read_at_offset(int(row["line_offset"]))
            except Exception:
                pass
        for rec in reversed(self.load_all()):
            if rec.get("event_id") == event_id:
                return rec
        return None

    def _read_at_offset(self, offset: int) -> Optional[Dict[str, Any]]:
        try:
            with open(self.events_path, encoding="utf-8") as f:
                f.seek(offset)
                line = f.readline()
                if line.strip():
                    return json.loads(line)
        except (OSError, json.JSONDecodeError):
            return None
        return None

    def load_by_type(
        self, event_type: str, *, limit: int = 50
    ) -> List[Dict[str, Any]]:
        matches = [
            r
            for r in self.load_all()
            if str(r.get("event_type") or "") == event_type
        ]
        return matches[-limit:]

    def load_by_session(
        self, session_id: str, *, limit: int = 50
    ) -> List[Dict[str, Any]]:
        matches = [
            r for r in self.load_all() if str(r.get("session_id") or "") == session_id
        ]
        return matches[-limit:]

    def count(self) -> int:
        if not os.path.isfile(self.events_path):
            return 0
        with open(self.events_path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def summary(self) -> Dict[str, Any]:
        events = self.load_all()
        by_type: Dict[str, int] = {}
        for e in events:
            et = str(e.get("event_type") or "UNKNOWN")
            by_type[et] = by_type.get(et, 0) + 1
        return {
            "total": len(events),
            "by_type": by_type,
            "store_path": self.events_path,
            "indexed": self.use_index,
            "evidence_only": True,
            "may_authorize_deploy": False,
            "authority_effect": "none",
        }

    def append_correction(
        self,
        original_event_id: str,
        corrections: Dict[str, Any],
        *,
        surface: str = "dashboard",
    ) -> Optional[Dict[str, Any]]:
        """Corrections are new events referencing the original — never in-place."""
        original = self.load_by_event_id(original_event_id)
        if not original:
            return None
        base = event_from_dict(original)
        for k, v in corrections.items():
            if hasattr(base, k) and k not in _SIZING_FIELDS:
                setattr(base, k, v)
        from src.services.decision_journal import _new_event_id

        base.event_id = _new_event_id()
        base.timestamp = datetime.now(timezone.utc).isoformat()
        base.surface = surface
        base.authority_effect = "none"
        return self.persist(base, correction_of=original_event_id)


def get_decision_journal_store(
    events_path: Optional[str] = None,
    index_path: Optional[str] = None,
) -> DecisionJournalStore:
    return DecisionJournalStore(events_path=events_path, index_path=index_path)


def persist_journal_batch(
    batch: Dict[str, Any],
    *,
    session_id: str = "",
    store: Optional[DecisionJournalStore] = None,
) -> Dict[str, Any]:
    """Persist events from build_journal_batch output."""
    st = store or get_decision_journal_store()
    events_raw = batch.get("events") or []
    event_objs: List[DecisionEvent] = []
    for raw in events_raw:
        if isinstance(raw, DecisionEvent):
            event_objs.append(raw)
        elif isinstance(raw, dict):
            event_objs.append(event_from_dict(raw))
    result = st.persist_batch(event_objs, session_id=session_id)
    return {**result, "summary": st.summary()}
