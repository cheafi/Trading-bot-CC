"""Sprint 71 — Task REST API CRUD coverage."""

import asyncio

import pytest


class TestTaskRoutes:
    def test_task_routes_registered(self):
        from src.api.routers.tasks import router

        paths = [r.path for r in router.routes]
        assert "/api/tasks" in paths
        assert "/api/tasks/{task_id}" in paths


class TestTaskCrud:
    @pytest.fixture()
    def isolated_router(self, monkeypatch, tmp_path):
        from src.api.routers import tasks as tasks_router_module
        from src.services.task_service import TaskService

        test_db = tmp_path / "tasks_test.db"
        monkeypatch.setattr(tasks_router_module, "_task_service", TaskService(str(test_db)))
        return tasks_router_module

    def test_crud_flow(self, isolated_router):
        module = isolated_router

        created = asyncio.run(
            module.create_task(
                module.TaskCreate(
                    title="Write tests",
                    description="Add sprint validation",
                    priority="high",
                    due_date="2026-05-05",
                )
            )
        )
        assert created["id"] > 0
        assert created["title"] == "Write tests"
        assert created["completed"] is False

        fetched = asyncio.run(module.get_task(created["id"]))
        assert fetched["id"] == created["id"]
        assert fetched["priority"] == "high"

        patched = asyncio.run(
            module.update_task(
                created["id"],
                module.TaskUpdate(completed=True, title="Write API tests"),
            )
        )
        assert patched["completed"] is True
        assert patched["title"] == "Write API tests"

        listed = asyncio.run(module.list_tasks(completed=True, limit=10, offset=0))
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]

        deleted = asyncio.run(module.delete_task(created["id"]))
        assert deleted["deleted"] is True

    def test_missing_task_404(self, isolated_router):
        from fastapi import HTTPException

        module = isolated_router
        with pytest.raises(HTTPException) as exc:
            asyncio.run(module.get_task(999999))

        assert exc.value.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
