from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class TaskService:
    """SQLite-backed CRUD service for task management."""

    def __init__(self, db_path: str | None = None):
        default_path = (
            Path(__file__).resolve().parents[2] / "data" / "tasks.db"
        )
        configured_path = os.environ.get("TASKS_DB_PATH")
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
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        priority TEXT NOT NULL DEFAULT 'medium',
                        due_date TEXT,
                        completed INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "due_date": row["due_date"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_tasks(
        self,
        *,
        completed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM tasks"
        params: list[Any] = []

        if completed is not None:
            query += " WHERE completed = ?"
            params.append(1 if completed else 0)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = self._now_iso()
        completed = bool(payload.get("completed", False))

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO tasks (
                        title, description, priority, due_date, completed, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["title"],
                        payload.get("description"),
                        payload.get("priority", "medium"),
                        payload.get("due_date"),
                        1 if completed else 0,
                        now,
                        now,
                    ),
                )
                task_id = cur.lastrowid
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                conn.commit()

        return self._row_to_dict(row)

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
        return self._row_to_dict(row) if row else None

    def update_task(self, task_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not updates:
            return self.get_task(task_id)

        allowed = {"title", "description", "priority", "due_date", "completed"}
        fields: List[str] = []
        values: List[Any] = []

        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "completed":
                value = 1 if bool(value) else 0
            fields.append(f"{key} = ?")
            values.append(value)

        if not fields:
            return self.get_task(task_id)

        fields.append("updated_at = ?")
        values.append(self._now_iso())
        values.append(task_id)

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                    values,
                )
                if cur.rowcount == 0:
                    return None
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                conn.commit()

        return self._row_to_dict(row)

    def delete_task(self, task_id: int) -> bool:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
        return cur.rowcount > 0
