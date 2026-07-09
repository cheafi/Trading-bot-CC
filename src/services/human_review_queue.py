"""
Human Review Queue — audit trail for operator review tasks.

No direct threshold changes; acknowledge/accept/reject/defer only.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TASK_STATUSES: tuple[str, ...] = (
    "open",
    "acknowledged",
    "accepted",
    "rejected",
    "deferred",
)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "human_review"
)
_TASKS_PATH = os.environ.get("HUMAN_REVIEW_TASKS_PATH") or os.path.join(
    _DATA_DIR, "tasks.jsonl"
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "hrt") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


@dataclass
class HumanReviewTask:
    task_id: str
    source: str = "alpha_review"
    title: str = ""
    summary: str = ""
    category: str = "alpha_review"
    severity: str = "info"
    status: str = "open"
    review_item_id: str = ""
    report_id: str = ""
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    may_change_thresholds: bool = False
    authority_effect: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_change_thresholds"] = False
        d["authority_effect"] = "none"
        return d


class HumanReviewQueue:
    """Append-only task log with status transitions recorded in audit trail."""

    def __init__(self, tasks_path: Optional[str] = None) -> None:
        self.tasks_path = tasks_path or _TASKS_PATH
        _ensure_dir(self.tasks_path)

    def _append(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(self.tasks_path, "a", encoding="utf-8") as f:
            f.write(line)

    def _load_all(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.tasks_path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.tasks_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _latest_by_id(self) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for row in self._load_all():
            tid = str(row.get("task_id") or "")
            if tid:
                latest[tid] = row
        return latest

    def enqueue(self, task: HumanReviewTask) -> str:
        payload = task.to_dict()
        self._append(payload)
        return task.task_id

    def transition(
        self,
        task_id: str,
        *,
        new_status: str,
        note: str = "",
        actor: str = "operator",
    ) -> Optional[Dict[str, Any]]:
        if new_status not in TASK_STATUSES:
            return None
        latest = self._latest_by_id().get(task_id)
        if not latest:
            return None
        updated = dict(latest)
        updated["status"] = new_status
        updated["updated_at"] = _now_iso()
        trail = list(updated.get("audit_trail") or [])
        trail.append(
            {
                "at": _now_iso(),
                "from": latest.get("status"),
                "to": new_status,
                "actor": actor,
                "note": note,
                "threshold_change": False,
            }
        )
        updated["audit_trail"] = trail
        updated["may_change_thresholds"] = False
        updated["authority_effect"] = "none"
        self._append(updated)
        return updated

    def open_tasks(self) -> List[Dict[str, Any]]:
        latest = self._latest_by_id()
        return [
            row
            for row in latest.values()
            if row.get("status") in ("open", "acknowledged", "deferred")
        ]

    def summary(self) -> Dict[str, Any]:
        latest = list(self._latest_by_id().values())
        open_n = sum(1 for r in latest if r.get("status") == "open")
        ack_n = sum(1 for r in latest if r.get("status") == "acknowledged")
        return {
            "total_tasks": len(latest),
            "open": open_n,
            "acknowledged": ack_n,
            "accepted": sum(1 for r in latest if r.get("status") == "accepted"),
            "rejected": sum(1 for r in latest if r.get("status") == "rejected"),
            "deferred": sum(1 for r in latest if r.get("status") == "deferred"),
            "may_change_thresholds": False,
            "authority_effect": "none",
        }


_queue: Optional[HumanReviewQueue] = None


def get_human_review_queue() -> HumanReviewQueue:
    global _queue
    if _queue is None:
        _queue = HumanReviewQueue()
    return _queue


def make_task_id() -> str:
    return _new_id()


def tasks_from_review_items(
    items: List[Dict[str, Any]],
    *,
    report_id: str = "",
    source: str = "alpha_review",
) -> List[HumanReviewTask]:
    """Create open tasks for items flagged requires_human_review."""
    out: List[HumanReviewTask] = []
    for item in items:
        if not item.get("requires_human_review"):
            continue
        out.append(
            HumanReviewTask(
                task_id=make_task_id(),
                source=source,
                title=str(item.get("title") or "Alpha review item"),
                summary=str(item.get("summary") or ""),
                category=str(item.get("category") or "alpha_review"),
                severity=str(item.get("severity") or "info"),
                review_item_id=str(item.get("item_id") or ""),
                report_id=report_id,
                audit_trail=[
                    {
                        "at": _now_iso(),
                        "event": "created",
                        "actor": "alpha_review_service",
                        "threshold_change": False,
                    }
                ],
            )
        )
    return out
