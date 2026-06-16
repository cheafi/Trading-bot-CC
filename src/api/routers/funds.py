"""Active fund manager / model fund sleeves — PM-facing cards."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fund-lab", tags=["funds"])


async def _build_payload(
    request: Request,
    *,
    benchmark: str,
    period: str,
    top_n: int,
) -> Dict[str, Any]:
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
        logger.debug("fund-lab regime fetch failed", exc_info=True)

    market_data = getattr(request.app.state, "market_data", None)
    lab = await get_fund_lab_service().run(
        market_data,
        period=period,
        benchmark=benchmark.upper(),
        top_n=top_n,
        regime=regime,
    )
    cards = await get_model_fund_service().build_cards(
        lab,
        regime=regime,
        benchmark=benchmark.upper(),
    )
    market_regime_label = ""
    tradeability = ""
    today_trend = ""
    today_tradeability = ""
    vix_val: float | None = None
    breadth_val: float | None = None
    best_action_liner = ""
    fund_lab_sync_ts: float | None = None
    try:
        cached_funds = getattr(request.app.state, "fund_cards_cache", None)
        if isinstance(cached_funds, dict) and cached_funds.get("ts"):
            fund_lab_sync_ts = float(cached_funds["ts"])
        cache = getattr(request.app.state, "regime_cache", None)
        if cache is not None:
            if isinstance(cache, dict):
                trend = cache.get("trend")
                trade = cache.get("tradeability")
                vix_val = cache.get("vix")
                breadth_val = cache.get("breadth")
            else:
                trend = getattr(cache, "trend", None)
                trade = getattr(cache, "tradeability", None)
                vix_val = getattr(cache, "vix", None)
                breadth_val = getattr(cache, "breadth", None)
            if trend:
                today_trend = str(trend)
                market_regime_label = f"{trend} · {trade or 'WAIT'}"
            if trade:
                today_tradeability = str(trade)
            tradeability = str(trade or "")
        today_cache = getattr(request.app.state, "today_v7_cache", None)
        if isinstance(today_cache, dict):
            ba = today_cache.get("best_action") or {}
            best_action_liner = str(ba.get("stance_one_liner") or "")
            mr = today_cache.get("market_regime") or {}
            if not today_trend:
                today_trend = str(mr.get("trend") or "")
            if not today_tradeability:
                today_tradeability = str(mr.get("tradeability") or "")
            if not market_regime_label and today_trend:
                market_regime_label = f"{today_trend} · {today_tradeability or 'WAIT'}"
            if not tradeability:
                tradeability = today_tradeability
            if vix_val is None and mr.get("vix") is not None:
                vix_val = float(mr.get("vix"))
            if breadth_val is None and mr.get("breadth") is not None:
                breadth_val = float(mr.get("breadth"))
    except Exception:
        logger.debug("fund-lab regime/today context failed", exc_info=True)

    from src.services.fund_manager_console import _is_unknown_regime

    if _is_unknown_regime(regime) and market_regime_label:
        regime = market_regime_label.split("·")[0].strip() or regime

    execution_readiness: Dict[str, Any] = {}
    try:
        from src.api.app_state import get_engine
        from src.services.execution_readiness import build_execution_readiness
        from src.services.ibkr_service import get_ibkr_service
        from src.services.runtime_truth import (
            engine_runtime_snapshot,
            merge_execution_runtime_truth,
        )

        ibkr_st = get_ibkr_service().status()
        engine = get_engine(request.app)
        runtime = engine_runtime_snapshot(engine)
        execution_readiness = build_execution_readiness(
            ibkr_connected=bool(ibkr_st.get("connected")),
            ibkr_mode=ibkr_st.get("mode") or "paper",
            engine_running=bool(runtime.get("running")),
            circuit_breaker=bool(runtime.get("circuit_breaker")),
        )
        execution_readiness = merge_execution_runtime_truth(
            execution_readiness,
            engine=engine,
        )
    except Exception:
        logger.debug("fund-lab execution_readiness failed", exc_info=True)

    from src.services.fund_manager_console import build_fund_console_payload

    run_ts = time.time()
    console = build_fund_console_payload(
        cards=cards,
        regime=regime,
        benchmark=benchmark.upper(),
        execution_readiness=execution_readiness,
        market_regime_label=market_regime_label,
        today_trend=today_trend,
        today_tradeability=today_tradeability,
        fund_lab_sync_ts=fund_lab_sync_ts or run_ts,
        period=period,
        benchmark_return_pct=float(lab.get("benchmark_return_pct") or 0),
        tradeability=tradeability,
        best_action_liner=best_action_liner,
        vix=float(vix_val) if vix_val is not None else None,
        breadth=float(breadth_val) if breadth_val is not None else None,
    )
    payload = {
        "regime": console["regime"],
        "regime_display": console["regime_display"],
        "benchmark": benchmark.upper(),
        "benchmark_return_pct": lab.get("benchmark_return_pct", 0),
        "period": period,
        "lab": lab,
        "cards": console["cards"],
        "console": console,
        "count": len(cards),
    }
    try:
        request.app.state.fund_cards_cache = {
            "cards": cards,
            "regime": regime,
            "ts": run_ts,
        }
    except Exception:
        pass
    return payload


@router.get("/live")
async def fund_lab_live(
    request: Request,
    benchmark: str = Query(default="SPY"),
    period: str = Query(default="1y"),
    top_n: int = Query(default=5, ge=1, le=20),
) -> Dict[str, Any]:
    """Live fund-lab run + productized model fund cards."""
    return sanitize_for_json(
        await _build_payload(request, benchmark=benchmark, period=period, top_n=top_n)
    )


@router.get("/console")
async def fund_manager_console(
    request: Request,
    benchmark: str = Query(default="SPY"),
    period: str = Query(default="1y"),
) -> Dict[str, Any]:
    """PM fund operating console — allocation, monitor, comparison, execution."""
    payload = await _build_payload(
        request, benchmark=benchmark, period=period, top_n=5
    )
    return sanitize_for_json(payload.get("console") or payload)


@router.get("/cards")
async def model_fund_cards(
    request: Request,
    benchmark: str = Query(default="SPY"),
    period: str = Query(default="1y"),
) -> Dict[str, Any]:
    """Model fund cards only (lighter payload for dashboard strip)."""
    payload = await _build_payload(
        request, benchmark=benchmark, period=period, top_n=5
    )
    return sanitize_for_json(
        {
            "regime": payload["regime"],
            "benchmark": payload["benchmark"],
            "cards": payload["cards"],
            "count": payload["count"],
        }
    )
