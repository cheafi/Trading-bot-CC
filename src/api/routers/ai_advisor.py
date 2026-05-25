from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json
from src.services.ai_service import get_ai_service
from src.services.fund_ai_service import get_fund_ai_service
from src.services.trade_memory_service import get_trade_memory_service
from src.services.trade_review_ai_service import get_trade_review_ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-advisor", tags=["ai-advisor"])


async def _get_fund_cards(request: Request, benchmark: str) -> Dict[str, Any]:
    from src.services.fund_lab_service import get_fund_lab_service
    from src.services.model_funds import get_model_fund_service

    regime = "unknown"
    try:
        regime_service = getattr(request.app.state, "regime_service", None)
        if regime_service is not None:
            regime_payload = await regime_service.get()
            regime = (
                regime_payload.get("label")
                or regime_payload.get("trend")
                or regime_payload.get("regime")
                or "unknown"
            )
    except Exception:
        logger.debug("ai-advisor regime fetch failed", exc_info=True)

    market_data = getattr(request.app.state, "market_data", None)
    fund_lab_service = get_fund_lab_service()
    model_fund_service = get_model_fund_service()
    lab_payload = await fund_lab_service.run(
        market_data,
        period="1y",
        benchmark=benchmark.upper(),
        top_n=5,
        regime=regime,
    )
    cards = await model_fund_service.build_cards(
        lab_payload,
        regime=regime,
        benchmark=benchmark.upper(),
    )
    return {
        "cards": cards,
        "regime": regime,
        "benchmark": benchmark.upper(),
    }


@router.get("/status")
async def ai_advisor_status() -> Dict[str, Any]:
    ai_service = get_ai_service()
    return sanitize_for_json(ai_service.stats)


@router.get("/model-funds/{fund_id}/memo")
async def fund_pm_memo(
    fund_id: str,
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    payload = await _get_fund_cards(request, benchmark)
    card = next(
        (row for row in payload["cards"] if row.get("id") == fund_id.upper()), None
    )
    if card is None:
        raise HTTPException(status_code=404, detail=f"Unknown fund_id {fund_id}")
    service = get_fund_ai_service()
    return sanitize_for_json(
        await service.build_pm_memo(card, payload["regime"], payload["benchmark"])
    )


@router.get("/model-funds/{fund_id}/overview")
async def fund_ai_overview(
    fund_id: str,
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    payload = await _get_fund_cards(request, benchmark)
    card = next(
        (row for row in payload["cards"] if row.get("id") == fund_id.upper()), None
    )
    if card is None:
        raise HTTPException(status_code=404, detail=f"Unknown fund_id {fund_id}")
    service = get_fund_ai_service()
    memo = await service.build_pm_memo(card, payload["regime"], payload["benchmark"])
    expert_view = await service.build_expert_view(card, payload["regime"])
    return sanitize_for_json(
        {
            "fund_id": card.get("id"),
            "memo": memo,
            "expert_view": expert_view,
            "regime": payload["regime"],
            "benchmark": payload["benchmark"],
        }
    )


@router.get("/model-funds/{fund_id}/expert-view")
async def fund_expert_view(
    fund_id: str,
    request: Request,
    benchmark: str = Query(default="SPY"),
) -> Dict[str, Any]:
    payload = await _get_fund_cards(request, benchmark)
    card = next(
        (row for row in payload["cards"] if row.get("id") == fund_id.upper()), None
    )
    if card is None:
        raise HTTPException(status_code=404, detail=f"Unknown fund_id {fund_id}")
    service = get_fund_ai_service()
    return sanitize_for_json(await service.build_expert_view(card, payload["regime"]))


@router.get("/trades/review")
async def trade_review(
    ticker: Optional[str] = Query(default=None),
    entry_time: Optional[str] = Query(default=None),
    similar_limit: int = Query(default=3, ge=1, le=8),
) -> Dict[str, Any]:
    memory_service = get_trade_memory_service()
    trade = await memory_service.find_trade(ticker=ticker, entry_time=entry_time)
    if trade is None:
        raise HTTPException(status_code=404, detail="No matching closed trade found")
    review_service = get_trade_review_ai_service()
    return sanitize_for_json(
        await review_service.review_trade(trade, similar_limit=similar_limit)
    )


@router.get("/trades/similar")
async def similar_trades(
    ticker: Optional[str] = Query(default=None),
    entry_time: Optional[str] = Query(default=None),
    limit: int = Query(default=3, ge=1, le=8),
) -> Dict[str, Any]:
    memory_service = get_trade_memory_service()
    trade = await memory_service.find_trade(ticker=ticker, entry_time=entry_time)
    if trade is None:
        raise HTTPException(status_code=404, detail="No matching closed trade found")
    cases = await memory_service.find_similar_cases(trade, limit=limit)
    return sanitize_for_json({"trade": trade, "similar_cases": cases})
