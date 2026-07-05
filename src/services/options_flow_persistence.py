from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class OptionsFlowPersistence:
    """SQLite persistence for options-radar snapshots and normalized events."""

    def __init__(self, db_path: str | None = None):
        default_path = Path(__file__).resolve().parents[2] / "data" / "options_radar.db"
        configured_path = os.environ.get("OPTIONS_RADAR_DB_PATH")
        self._db_path = Path(db_path or configured_path or default_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS options_radar_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        source TEXT NOT NULL,
                        universe_size INTEGER NOT NULL DEFAULT 0,
                        grade_a INTEGER NOT NULL DEFAULT 0,
                        grade_b INTEGER NOT NULL DEFAULT 0,
                        grade_c INTEGER NOT NULL DEFAULT 0,
                        payload_json TEXT NOT NULL
                    )
                    """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS options_flow_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        underlying TEXT NOT NULL,
                        contract_symbol TEXT NOT NULL,
                        quality_grade TEXT NOT NULL,
                        action_label TEXT NOT NULL,
                        radar_score REAL NOT NULL,
                        premium REAL NOT NULL,
                        volume_oi_ratio REAL NOT NULL,
                        volume_vs_avg_ratio REAL NOT NULL,
                        payload_json TEXT NOT NULL,
                        FOREIGN KEY(snapshot_id) REFERENCES options_radar_snapshots(id)
                    )
                    """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_options_events_ticker ON options_flow_events(underlying, created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_options_snapshots_created ON options_radar_snapshots(created_at DESC)"
                )
                conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_snapshot(self, snapshot: Dict[str, Any]) -> int:
        created_at = snapshot.get("timestamp") or self._now_iso()
        summary = snapshot.get("summary") or {}
        candidates = snapshot.get("candidates") or []
        payload = json.dumps(snapshot, separators=(",", ":"), default=str)
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO options_radar_snapshots (
                        created_at, status, source, universe_size, grade_a, grade_b, grade_c, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        snapshot.get("status", "snapshot"),
                        snapshot.get("source", "unknown"),
                        int(snapshot.get("universe_size") or 0),
                        int(summary.get("grade_a") or 0),
                        int(summary.get("grade_b") or 0),
                        int(summary.get("grade_c") or 0),
                        payload,
                    ),
                )
                snapshot_id = int(cur.lastrowid)
                for event in candidates:
                    conn.execute(
                        """
                        INSERT INTO options_flow_events (
                            snapshot_id, created_at, underlying, contract_symbol, quality_grade, action_label,
                            radar_score, premium, volume_oi_ratio, volume_vs_avg_ratio, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id,
                            created_at,
                            event.get("underlying", ""),
                            event.get("contract_symbol", ""),
                            event.get("quality_grade", "C"),
                            event.get("action_label", "WATCH"),
                            float(event.get("radar_score") or 0),
                            float(event.get("premium") or 0),
                            float(event.get("volume_oi_ratio") or 0),
                            float(event.get("volume_vs_avg_ratio") or 0),
                            json.dumps(event, separators=(",", ":"), default=str),
                        ),
                    )
                conn.commit()
        return snapshot_id

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT payload_json FROM options_radar_snapshots ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
        return None if row is None else json.loads(row["payload_json"])

    def snapshot_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT payload_json FROM options_radar_snapshots ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def events_for_ticker(self, ticker: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT payload_json FROM options_flow_events
                    WHERE underlying = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (ticker.upper(), limit),
                ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]


_service: Optional[OptionsFlowPersistence] = None


def get_options_flow_persistence() -> OptionsFlowPersistence:
    global _service
    if _service is None:
        _service = OptionsFlowPersistence()
    return _service
