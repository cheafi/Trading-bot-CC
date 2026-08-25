"""Ops diagnostics — changelog, session error log, engine controls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Request

from src.api.app_state import get_engine
from src.api.deps import sanitize_for_json, verify_api_key
from src.core.config import get_settings
from src.services.platform_error_log import get_error_log, load_changelog
from src.services.runtime_truth import engine_runtime_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ops", tags=["ops"])


def _engine_snapshot(engine) -> Dict[str, Any]:
    return engine_runtime_snapshot(engine)


async def _start_engine_loop(app) -> Dict[str, Any]:
    engine = get_engine(app)
    if not engine:
        return {"ok": False, "error": "AutoTradingEngine failed to initialize"}

    if bool(getattr(engine, "_running", False)):
        return {"ok": True, "already_running": True, "engine": _engine_snapshot(engine)}

    existing = getattr(app.state, "engine_task", None)
    if existing and not existing.done():
        return {"ok": True, "already_running": True, "engine": _engine_snapshot(engine)}

    task = asyncio.create_task(engine.run())
    app.state.engine_task = task

    def _log_task_result(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.info("[EngineControl] engine loop task cancelled")
        except Exception as exc:
            logger.error("[EngineControl] engine loop exited with error: %s", exc)

    task.add_done_callback(_log_task_result)
    logger.info("[EngineControl] AutoTradingEngine loop started via API")
    return {"ok": True, "started": True, "engine": _engine_snapshot(engine)}


async def _stop_engine_loop(app) -> Dict[str, Any]:
    engine = get_engine(app)
    if not engine:
        return {"ok": False, "error": "AutoTradingEngine failed to initialize"}

    await engine.stop()
    task = getattr(app.state, "engine_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    app.state.engine_task = None
    logger.info("[EngineControl] AutoTradingEngine stopped via API")
    return {"ok": True, "stopped": True, "engine": _engine_snapshot(engine)}


async def _run_engine_cycle_once(app) -> Dict[str, Any]:
    engine = get_engine(app)
    if not engine:
        return {"ok": False, "error": "AutoTradingEngine failed to initialize"}

    if bool(getattr(engine, "_running", False)):
        return {
            "ok": False,
            "error": "Engine loop already running — wait for the next scheduled cycle",
            "engine": _engine_snapshot(engine),
        }

    result = await engine.run_one_cycle()
    return {"ok": True, "cycle": result, "engine": _engine_snapshot(engine)}


@router.get("/changelog")
async def ops_changelog():
    """Platform version and release notes from data/changelog.json."""
    return sanitize_for_json(load_changelog())


@router.get("/error-log")
async def ops_error_log(
    severity: str = Query("all", description="all | critical | warning | info"),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent platform errors captured this API process session."""
    settings = get_settings()
    include_stack = settings.environment != "production"
    return sanitize_for_json(
        get_error_log(severity=severity, limit=limit, include_stack=include_stack)
    )


@router.get("/engine/status")
async def ops_engine_status(request: Request):
    """Trading engine loop state for Ops diagnostics."""
    engine = get_engine(request.app)
    task = getattr(request.app.state, "engine_task", None)
    return sanitize_for_json(
        {
            "engine": _engine_snapshot(engine),
            "loop_task": ("running" if task and not task.done() else "idle"),
            "auto_start_env": "CC_AUTO_START_ENGINE",
        }
    )


@router.post("/engine/start")
async def ops_engine_start(request: Request, _: bool = Depends(verify_api_key)):
    """Start the AutoTradingEngine background loop (paper/dry-run by default)."""
    return sanitize_for_json(await _start_engine_loop(request.app))


@router.post("/engine/stop")
async def ops_engine_stop(request: Request, _: bool = Depends(verify_api_key)):
    """Stop the AutoTradingEngine background loop."""
    return sanitize_for_json(await _stop_engine_loop(request.app))


@router.post("/engine/run-cycle")
async def ops_engine_run_cycle(request: Request, _: bool = Depends(verify_api_key)):
    """Run one scan cycle on demand (dev helper when loop is not running)."""
    return sanitize_for_json(await _run_engine_cycle_once(request.app))
