"""Guide tab — consolidated project briefing for ChatGPT advisory."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from src.api.deps import sanitize_for_json
from src.services.guide_briefing import load_guide_briefing

router = APIRouter(prefix="/api/v7/guide", tags=["guide"])


@router.get("/briefing")
async def guide_briefing(
    format: str = Query(default="json", alias="format"),
) -> Any:
    """
    Return CC consolidated briefing for external advisor prompts.

    ``?format=markdown`` returns raw markdown (fixed repo path — no user input).
    """
    payload = load_guide_briefing()
    if format == "markdown":
        body = payload.get("full_markdown") or ""
        return PlainTextResponse(
            content=body,
            media_type="text/markdown; charset=utf-8",
        )
    return sanitize_for_json(payload)
