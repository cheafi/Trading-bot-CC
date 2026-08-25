"""
Strategy / signal tracking — research-only surfaces.

GET /api/v7/tracking/signal-ledger   — funnel + cohort summary (default cohort)
GET /api/v7/tracking/cohorts          — cohort summary by chosen dimension
GET /api/v7/tracking/funnel           — conversion funnel only
GET /api/v7/tracking/regime-timeline  — regime-change timeline + persistence
GET /api/v7/tracking/market-pressure  — composite market pressure score

Every endpoint returns a provenance-wrapped payload with authority_ceiling
'research_only' and deploy_from_signal_alone=False. These surfaces inform
Discovery/Review/Market context; none of them can authorize a deploy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.market_regime_tracker import build_regime_timeline_context
from src.services.signal_tracker import (
    build_signal_tracking_context,
    get_tracker,
)

router = APIRouter(prefix="/api/v7/tracking", tags=["strategy-tracking"])

_COHORT_DIMENSIONS = {
    "regime",
    "vix_bucket",
    "sector",
    "rs_bucket",
    "strategy_family",
    "entry_mode",
    "follow_through_quality",
    "stop_type",
}


@router.get("/signal-ledger")
async def tracking_signal_ledger(
    cohort: str = Query("regime", max_length=32),
    _=Depends(verify_api_key),
):
    dim = cohort if cohort in _COHORT_DIMENSIONS else "regime"
    return sanitize_for_json(build_signal_tracking_context(cohort_dimension=dim))


@router.get("/cohorts")
async def tracking_cohorts(
    dimension: str = Query("regime", max_length=32),
    _=Depends(verify_api_key),
):
    dim = dimension if dimension in _COHORT_DIMENSIONS else "regime"
    ctx = build_signal_tracking_context(cohort_dimension=dim)
    return sanitize_for_json(ctx)


@router.get("/funnel")
async def tracking_funnel(_=Depends(verify_api_key)):
    return sanitize_for_json(get_tracker().conversion_funnel())


@router.get("/regime-timeline")
async def tracking_regime_timeline(_=Depends(verify_api_key)):
    return sanitize_for_json(build_regime_timeline_context())


@router.get("/market-pressure")
async def tracking_market_pressure(_=Depends(verify_api_key)):
    ctx = build_regime_timeline_context()
    return sanitize_for_json(
        {
            "signal_type": ctx["signal_type"],
            "authority_ceiling": ctx["authority_ceiling"],
            "degraded": ctx["degraded"],
            "market_pressure": ctx["market_pressure"],
            "distribution_days": ctx["distribution_days"],
            "follow_through": ctx["follow_through"],
        }
    )
