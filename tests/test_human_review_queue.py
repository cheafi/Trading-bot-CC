"""Human review queue — audit trail only."""

from __future__ import annotations

from src.services.human_review_queue import (
    HumanReviewQueue,
    HumanReviewTask,
    make_task_id,
    tasks_from_review_items,
)


def test_enqueue_and_transition(tmp_path):
    queue = HumanReviewQueue(tasks_path=str(tmp_path / "tasks.jsonl"))
    task = HumanReviewTask(task_id=make_task_id(), title="Overfit guard", status="open")
    queue.enqueue(task)
    updated = queue.transition(task.task_id, new_status="acknowledged", note="seen")
    assert updated is not None
    assert updated["status"] == "acknowledged"
    assert updated["may_change_thresholds"] is False
    assert updated["audit_trail"][-1]["threshold_change"] is False


def test_open_tasks_excludes_accepted(tmp_path):
    queue = HumanReviewQueue(tasks_path=str(tmp_path / "tasks.jsonl"))
    t1 = HumanReviewTask(task_id=make_task_id(), title="Open", status="open")
    t2 = HumanReviewTask(task_id=make_task_id(), title="Done", status="open")
    queue.enqueue(t1)
    queue.enqueue(t2)
    queue.transition(t2.task_id, new_status="accepted")
    open_rows = queue.open_tasks()
    assert len(open_rows) == 1
    assert open_rows[0]["task_id"] == t1.task_id


def test_tasks_from_review_items():
    items = [
        {
            "item_id": "i1",
            "title": "Missed opp",
            "requires_human_review": True,
            "category": "missed_opportunity",
        },
        {"item_id": "i2", "title": "Monitor", "requires_human_review": False},
    ]
    tasks = tasks_from_review_items(items, report_id="r1")
    assert len(tasks) == 1
    assert tasks[0].may_change_thresholds is False
    assert tasks[0].authority_effect == "none"
