"""
Agent Router — Sprint 77
========================
Agentic decision surfaces inspired by multi-agent trading research:
- researcher / macro / risk / execution / critic perspectives
- deterministic aggregation on top of existing ExpertCouncil
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/agents", tags=["agents"])


def _service_from_state(request: Request):
    svc = getattr(request.app.state, "agent_orchestrator", None)
    if svc is not None:
        return svc
    from src.services.agent_orchestrator_service import get_agent_orchestrator_service

    svc = get_agent_orchestrator_service()
    request.app.state.agent_orchestrator = svc
    return svc


@router.get("/run/{ticker}")
async def run_agent_for_ticker(
    request: Request,
    ticker: str,
    _: bool = Depends(verify_api_key),
):
    """Run multi-agent deliberation for one ticker."""
    svc = _service_from_state(request)
    result = await asyncio.to_thread(svc.run_ticker, ticker)
    return sanitize_for_json(result)


@router.get("/batch")
async def run_agent_batch(
    request: Request,
    tickers: str = Query(
        default="AAPL,MSFT,NVDA", description="Comma-separated tickers"
    ),
    limit: int = Query(default=10, ge=1, le=30),
    _: bool = Depends(verify_api_key),
):
    """Run multi-agent deliberation for a batch of tickers."""
    svc = _service_from_state(request)
    ticker_list: List[str] = [
        t.strip().upper() for t in tickers.split(",") if t.strip()
    ]
    result = await asyncio.to_thread(svc.run_batch, ticker_list, limit)
    return sanitize_for_json(result)


@router.get("/today")
async def run_agent_today(
    request: Request,
    limit: int = Query(default=10, ge=1, le=30),
    _: bool = Depends(verify_api_key),
):
    """Run multi-agent deliberation for today's brief universe."""
    svc = _service_from_state(request)
    result = await asyncio.to_thread(svc.run_today, limit)
    return sanitize_for_json(result)


@router.get("/status")
async def agent_status(
    request: Request,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Health/status of the agent orchestrator surface."""
    _ = _service_from_state(request)
    return {
        "status": "ok",
        "mode": "deterministic-multi-agent",
        "pipeline": ["research", "macro", "risk", "execution", "critic"],
        "version": "sprint77",
    }
