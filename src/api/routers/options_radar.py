"""Options flow radar — unusual activity as evidence, not decisions."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.api.deps import sanitize_for_json
from src.engines.options_flow_radar import OptionsFlowRadar
from src.services.options_flow_mock import MockOptionsFlowProvider
from src.services.options_flow_persistence import get_options_flow_persistence
from src.services.options_flow_polygon import PolygonOptionsFlowProvider
from src.services.options_flow_provider import OptionsFlowProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/options-radar", tags=["options-radar"])


def _resolve_provider() -> Optional[OptionsFlowProvider]:
    mode = (os.getenv("OPTIONS_RADAR_PROVIDER") or "auto").strip().lower()
    if mode == "mock":
        return MockOptionsFlowProvider()
    if mode == "polygon":
        return PolygonOptionsFlowProvider()
    if mode == "none" or mode == "off":
        return None
    polygon_key = os.getenv("POLYGON_API_KEY", "").strip()
    if polygon_key:
        return PolygonOptionsFlowProvider(api_key=polygon_key)
    return MockOptionsFlowProvider()


async def _scan_with_fallback(
    tickers: Optional[List[str]],
    *,
    limit: int,
    min_grade: str,
) -> Dict[str, Any]:
    """Scan options radar; fall back to mock or last-good if live feed is empty."""
    provider = _resolve_provider()
    radar = OptionsFlowRadar(provider)
    snapshot = await radar.scan(tickers, limit=limit, min_grade=min_grade)
    payload = snapshot.to_dict()
    candidates = payload.get("candidates") or []

    if candidates:
        return payload

    mode = (os.getenv("OPTIONS_RADAR_PROVIDER") or "auto").strip().lower()
    use_polygon = mode == "polygon" or (
        mode == "auto" and os.getenv("POLYGON_API_KEY", "").strip()
    )
    if not use_polygon:
        return payload

    # Polygon configured but no scorable contracts — try last-good snapshot
    try:
        last = get_options_flow_persistence().latest_snapshot()
        if last and (last.get("candidates") or []):
            last["warning"] = (
                "Polygon scan returned no candidates; serving last-good snapshot."
            )
            last["trust"] = {
                **(last.get("trust") or {}),
                "fallback": "persistence",
            }
            return last
    except Exception:
        logger.debug("options radar persistence fallback skipped", exc_info=True)

    # Final fallback: mock with explicit synthetic flag
    mock_snap = await OptionsFlowRadar(MockOptionsFlowProvider()).scan(
        tickers, limit=limit, min_grade=min_grade
    )
    mock_payload = mock_snap.to_dict()
    mock_payload["warning"] = (
        "Polygon scan returned no candidates; serving mock synthetic fallback."
    )
    trust = mock_payload.get("trust") or {}
    trust["fallback"] = "mock"
    trust["synthetic"] = True
    mock_payload["trust"] = trust
    for row in mock_payload.get("candidates") or []:
        row_trust = row.get("trust") or {}
        row_trust["synthetic"] = True
        row["trust"] = row_trust
    return mock_payload


@router.get("/health")
async def options_radar_health() -> Dict[str, Any]:
    provider = _resolve_provider()
    if provider is None:
        return {
            "provider": "none",
            "enabled": False,
            "mode": "unavailable",
            "status": "unavailable",
            "message": "Options radar disabled (OPTIONS_RADAR_PROVIDER=none).",
        }
    status = await provider.health()
    return sanitize_for_json(status.to_dict())


@router.get("/top")
async def options_radar_top(
    limit: int = Query(20, ge=1, le=100),
    min_grade: str = Query("C", pattern="^[ABC]$"),
    universe: Optional[str] = Query(
        None, description="Comma-separated tickers; empty = provider default universe"
    ),
) -> Dict[str, Any]:
    """Top unusual options candidates ranked by radar score."""
    tickers: Optional[List[str]] = None
    if universe:
        tickers = [t.strip().upper() for t in universe.split(",") if t.strip()]

    payload = await _scan_with_fallback(
        tickers, limit=limit, min_grade=min_grade
    )
    payload["candidates"] = payload.get("candidates") or []
    if payload["candidates"]:
        trust = payload["candidates"][0].get("trust") or {}
        if trust.get("mode") == "mock":
            trust["synthetic"] = True
    try:
        get_options_flow_persistence().save_snapshot(payload)
    except Exception:
        logger.debug("options radar persistence skipped", exc_info=True)
    return sanitize_for_json(payload)


@router.get("/ticker/{ticker}")
async def options_radar_ticker(
    ticker: str,
    limit: int = Query(10, ge=1, le=50),
    min_grade: str = Query("C", pattern="^[ABC]$"),
) -> Dict[str, Any]:
    """Options flow evidence for a single underlying."""
    ticker = ticker.upper().strip()
    payload = await _scan_with_fallback(
        [ticker], limit=limit, min_grade=min_grade
    )
    candidates = [
        row
        for row in (payload.get("candidates") or [])
        if (row.get("underlying") or "").upper() == ticker
    ]
    return sanitize_for_json(
        {
            "ticker": ticker,
            "count": len(candidates),
            "candidates": candidates,
            "summary": payload.get("summary"),
            "trust": payload.get("trust"),
            "status": payload.get("status"),
            "source": payload.get("source"),
            "warning": payload.get("warning"),
        }
    )
