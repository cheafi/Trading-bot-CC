"""P2 platform endpoints — backtest lab, quote workstation, portfolio analytics."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json
from src.services.backtest_lab import build_backtest_lab
from src.services.cross_asset_confirmation import build_cross_asset_confirmation
from src.services.portfolio_equity import build_portfolio_equity_series
from src.services.quote_workstation import build_quote_workstation
from src.services.rebalance_sim import simulate_rebalance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-p2"])


@router.get("/backtest-lab")
async def backtest_lab(
    request: Request,
    ticker: str = Query("AAPL"),
    strategy: str = Query("all"),
    period: str = Query("6mo"),
    walk_forward: bool = Query(True, description="Set false for faster single run"),
):
    """Attribution + walk-forward + trade-level review."""
    try:
        return sanitize_for_json(
            await build_backtest_lab(
                request,
                ticker=ticker,
                strategy=strategy,
                period=period,
                walk_forward=walk_forward,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:200]) from exc


@router.get("/quote-workstation/{ticker}")
async def quote_workstation(ticker: str, request: Request):
    """Six-panel quote command center."""
    return sanitize_for_json(await build_quote_workstation(request, ticker))


@router.get("/portfolio-equity")
async def portfolio_equity(
    request: Request,
    period: str = Query("6mo"),
    benchmark: str = Query("SPY"),
):
    positions = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        positions = _user_portfolio.get("holdings") or []
    except Exception:
        pass
    return sanitize_for_json(
        await build_portfolio_equity_series(
            request, positions, period=period, benchmark=benchmark
        )
    )


@router.get("/cross-asset-confirmation")
async def cross_asset_confirmation(request: Request):
    """Cross-asset alignment for Today."""
    regime = {}
    should_trade = True
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    if today:
        regime = today.get("market_regime") or {}
        should_trade = bool(regime.get("should_trade", True))
    return sanitize_for_json(
        await build_cross_asset_confirmation(
            request, regime=regime, should_trade=should_trade
        )
    )


@router.post("/rebalance-sim")
async def rebalance_sim_v2(
    request: Request,
    policy: str = Query("equal_weight"),
    targets: Optional[str] = Query(
        None, description='JSON map ticker→weight pct e.g. {"AAPL":40,"MSFT":30}'
    ),
):
    positions = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        positions = _user_portfolio.get("holdings") or []
    except Exception:
        pass
    target_weights = None
    if targets:
        try:
            raw = json.loads(targets)
            if isinstance(raw, dict):
                target_weights = {k: float(v) / 100.0 for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid targets JSON") from exc
    return sanitize_for_json(
        simulate_rebalance(positions, policy=policy, target_weights=target_weights)
    )


@router.post("/scenario-shock")
async def scenario_shock(
    request: Request,
    scenario_key: str = Query(..., description="Scenario key from /api/scenarios"),
):
    """Run portfolio through stress scenario engine."""
    from src.engines.scenario_engine import ScenarioEngine

    positions = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        for p in _user_portfolio.get("holdings") or []:
            positions.append(
                {
                    "ticker": p.get("ticker"),
                    "weight": float(p.get("market_value") or 0),
                    "entry_price": float(p.get("avg_cost") or p.get("current_price") or 100),
                }
            )
    except Exception:
        pass
    if not positions:
        raise HTTPException(status_code=400, detail="No portfolio positions")
    total = sum(p["weight"] for p in positions) or 1.0
    for p in positions:
        p["weight"] = p["weight"] / total
    engine = ScenarioEngine()
    result = engine.run_scenario(scenario_key, positions)
    return sanitize_for_json(result.to_dict())
