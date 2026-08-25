"""Advisor briefing page — full project context for ChatGPT / external advisors."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

from src.api.briefing_content import build_briefing_html, build_briefing_text

router = APIRouter(tags=["advisor-briefing"], include_in_schema=False)


@router.get("/briefing", response_class=HTMLResponse)
@router.get("/advisor-briefing", response_class=HTMLResponse)
async def advisor_briefing_html():
    """One-page briefing: consolidated doc + API shapes + ChatGPT prompts."""
    return HTMLResponse(content=build_briefing_html(), media_type="text/html; charset=utf-8")


@router.get("/briefing.txt", response_class=PlainTextResponse)
async def advisor_briefing_text():
    """Plain-text export of the same briefing."""
    return PlainTextResponse(content=build_briefing_text(), media_type="text/plain; charset=utf-8")
