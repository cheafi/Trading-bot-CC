from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
_task_service = TaskService()


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    due_date: Optional[str] = None
    completed: bool = False


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")
    due_date: Optional[str] = None
    completed: Optional[bool] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: str
    due_date: Optional[str] = None
    completed: bool
    created_at: str
    updated_at: str


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    completed: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return _task_service.list_tasks(completed=completed, limit=limit, offset=offset)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate):
    return _task_service.create_task(task.model_dump())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    record = _task_service.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    return record


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task: TaskUpdate):
    updates = task.model_dump(exclude_unset=True)
    record = _task_service.update_task(task_id, updates)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    return record


@router.delete("/{task_id}")
async def delete_task(task_id: int):
    deleted = _task_service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True, "task_id": task_id}
