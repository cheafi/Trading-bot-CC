"""CC whole-page Time Travel replay endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from src.api.deps import optional_api_key
from src.services.cc_replay_service import (
    ReplaySnapshotError,
    list_replay_dates,
    replay_snapshot_error_detail,
)

router = APIRouter(prefix="/api/cc/replay", tags=["replay"])


@router.get("/dates")
async def replay_dates(_=optional_api_key) -> Dict[str, Any]:
    """Available brief snapshot dates for whole-page replay."""
    dates = list_replay_dates()
    return {
        "dates": dates,
        "count": len(dates),
        "hint": "選擇日期後，整個控制台會顯示該日的市場狀態、候選名單與決策（研究用，不可下單）",
    }


@router.get("/status")
async def replay_status(
    as_of: str = Query(..., description="Replay date YYYY-MM-DD"),
    _=optional_api_key,
) -> Dict[str, Any]:
    """Validate whether a replay date resolves to a brief snapshot."""
    from src.services.cc_replay_service import resolve_brief_for_as_of

    try:
        resolved, _brief, note = resolve_brief_for_as_of(as_of)
    except ReplaySnapshotError as exc:
        raise HTTPException(
            status_code=404,
            detail=replay_snapshot_error_detail(exc),
        ) from exc
    return {
        "ok": True,
        "replay_as_of": resolved,
        "replay_requested": as_of.strip(),
        "replay_note": note,
        "exact_match": resolved == as_of.strip(),
    }
