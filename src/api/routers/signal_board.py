"""Signal Board API — hourly BUY / SELL paper signals (read-only + keyed refresh)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import verify_api_key
from src.services import signal_board as sb

router = APIRouter(tags=["signal-board"])

_bg_tasks: set = set()


def _kick_refresh(source: str) -> bool:
    if sb.is_refreshing():
        return False
    task = asyncio.create_task(sb.refresh_signal_board(source=source))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return True


@router.get("/api/v7/signal-board")
async def get_signal_board() -> dict[str, Any]:
    board = sb.get_latest()
    headline = (board or {}).get("headline") or {}
    empty_signals = (
        bool(board)
        and not sb.is_refreshing()
        and int(headline.get("buy_count") or 0) + int(headline.get("sell_count") or 0) == 0
        and int((board.get("universe") or {}).get("liquid") or 0) == 0
    )
    if empty_signals:
        _kick_refresh("empty_board_recovery")
    if not board:
        started = _kick_refresh("first_request")
        return {
            "status": "warming",
            "refreshing": True,
            "started": started,
            "authority": sb.AUTHORITY,
            "method": sb.METHOD,
            "detail": "First scan of ~700 names (incl. crypto) takes 1–2 minutes — retry shortly.",
        }
    return {**board, "refreshing": sb.is_refreshing()}


@router.post("/api/v7/signal-board/refresh")
async def refresh_signal_board(_: bool = Depends(verify_api_key)) -> dict[str, Any]:
    started = _kick_refresh("manual")
    return {"status": "started" if started else "already_running", "refreshing": True}
