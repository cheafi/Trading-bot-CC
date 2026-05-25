"""
Strategy Health Router — per-strategy realized-trade analytics.

Endpoints:
  GET /api/strategy-health/per-strategy?window=30  — per-strategy Sharpe / hit rate / expectancy

Reads `data/closed_trades.jsonl`. No external dependencies, no broker calls.
Surfaces sample-size status so the UI can warn on tiny samples.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.strategy_health_service import load_per_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy-health", tags=["strategy-health"])


@router.get("/per-strategy")
async def per_strategy(
    window: int = Query(
        30, ge=0, le=3650, description="Trailing window in days; 0=all-time"
    ),
    _=Depends(verify_api_key),
):
    """
    Per-strategy Sharpe + hit rate + expectancy over a trailing window.

    Returns:
        {
          strategies: [{strategy_id, n_trades, hit_rate, avg_r, sharpe_trade,
                        sharpe_annualized, status, ...}, ...],
          meta: {window_days, n_total, n_in_window, n_min_trusted, n_min_tentative},
          disclaimer: str
        }
    """
    result = load_per_strategy(window_days=window)
    return sanitize_for_json(result)
