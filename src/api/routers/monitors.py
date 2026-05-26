"""CRUD for institutional monitors — /api/v7/monitors."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json
from src.services.monitors_store import (
    create_monitor,
    delete_monitor,
    evaluate_monitors,
    list_monitors,
    update_monitor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-monitors"])


@router.get("/monitors")
async def get_monitors(active_only: bool = Query(False)):
    return sanitize_for_json(list_monitors(active_only=active_only))


@router.post("/monitors")
async def post_monitor(body: Dict[str, Any]):
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body required")
    return sanitize_for_json(create_monitor(body))


@router.patch("/monitors/{monitor_id}")
async def patch_monitor(monitor_id: str, body: Dict[str, Any]):
    updated = update_monitor(monitor_id, body or {})
    if not updated:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return sanitize_for_json(updated)


@router.delete("/monitors/{monitor_id}")
async def remove_monitor(monitor_id: str):
    if not delete_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"ok": True, "id": monitor_id}


@router.get("/monitors/evaluate")
async def monitors_evaluate(request: Request):
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    positions = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        positions = _user_portfolio.get("holdings") or []
    except Exception:
        logger.debug("monitors evaluate holdings failed", exc_info=True)
    return sanitize_for_json(
        {"alerts": evaluate_monitors(today=today, positions=positions)}
    )
