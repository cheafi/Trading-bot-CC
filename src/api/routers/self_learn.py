"""
Self-Learn Router — Sprint 96
==============================
Exposes the SelfLearningEngine, regime-conditioned params, and fund
weight auto-tuner over REST.

Routes:
  GET  /api/v7/self-learn/status          — engine state + recent audit log
  GET  /api/v7/self-learn/regime-params   — per-regime parameter table
  GET  /api/v7/self-learn/fund-weights    — current fund sleeve allocations
  POST /api/v7/self-learn/trigger         — run one analysis+adjust cycle
  POST /api/v7/self-learn/fund-tune       — update fund weights from latest metrics
  POST /api/v7/self-learn/disable         — kill switch
  POST /api/v7/self-learn/enable          — re-enable
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.engines.self_learning import (
    SelfLearningEngine,
    analyze_regime_performance,
    get_params_for_regime,
    load_fund_weights,
    load_regime_params,
    pull_closed_trades_from_learning_loop,
    tune_fund_weights,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/self-learn", tags=["self-learn"])

# Module-level engine singleton
_engine: SelfLearningEngine | None = None


def _get_engine() -> SelfLearningEngine:
    global _engine
    if _engine is None:
        _engine = SelfLearningEngine()
    return _engine


# ── Status ───────────────────────────────────────────────────────────────────


@router.get("/status")
async def self_learn_status(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Current learning engine state + recent audit log."""
    engine = _get_engine()
    trades = pull_closed_trades_from_learning_loop()
    regime_perf = analyze_regime_performance(trades) if trades else {}
    return sanitize_for_json(
        {
            "engine_state": engine.state.to_dict(),
            "closed_trades_available": len(trades),
            "regime_performance": regime_perf,
            "fund_weights": load_fund_weights(),
            "regime_params_summary": {
                regime: {k: v for k, v in params.items()}
                for regime, params in load_regime_params().items()
            },
        }
    )


# ── Regime params ─────────────────────────────────────────────────────────────


@router.get("/regime-params")
async def get_regime_params(
    regime: str = "BULL",
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Fetch the active parameter set for a given regime."""
    params = get_params_for_regime(regime)
    return {"regime": regime.upper(), "params": params}


# ── Fund weights ─────────────────────────────────────────────────────────────


@router.get("/fund-weights")
async def get_fund_weights(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Current Sharpe-based fund sleeve allocations."""
    return {"fund_weights": load_fund_weights()}


# ── Trigger learning cycle ────────────────────────────────────────────────────


@router.post("/trigger")
async def trigger_learning_cycle(
    request: Request,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Pull closed trades from LearningLoopPipeline, run analysis, apply
    approved adjustments (subject to guardrails), and return the diff.
    """
    engine = _get_engine()
    engine.reset_cycle()

    trades = pull_closed_trades_from_learning_loop()
    if not trades:
        return {
            "status": "skipped",
            "reason": "No closed trades available yet",
            "adjustments": [],
        }

    # Build current rules from live config
    try:
        from src.core.config import get_trading_config

        cfg = get_trading_config()
        current_rules: Dict[str, float] = {
            "stop_loss_pct": getattr(cfg, "stop_loss_pct", 0.03),
            "ensemble_min_score": getattr(cfg, "ensemble_min_score", 0.35),
            "signal_cooldown_hours": float(getattr(cfg, "signal_cooldown_hours", 4)),
            "max_position_pct": getattr(cfg, "max_position_pct", 0.05),
            "trailing_stop_pct": getattr(cfg, "trailing_stop_pct", 0.02),
        }
    except Exception:
        current_rules = {
            "stop_loss_pct": 0.03,
            "ensemble_min_score": 0.35,
            "signal_cooldown_hours": 4.0,
            "max_position_pct": 0.05,
            "trailing_stop_pct": 0.02,
        }

    recommendations = engine.analyze_and_recommend(trades, current_rules)
    applied = engine.apply_adjustments(recommendations)

    return sanitize_for_json(
        {
            "status": "ok",
            "trades_analysed": len(trades),
            "adjustments_applied": len(applied),
            "adjustments": [a.to_dict() for a in applied],
        }
    )


# ── Fund weight auto-tune ─────────────────────────────────────────────────────


@router.post("/fund-tune")
async def fund_weight_tune(
    request: Request,
    learning_rate: float = 0.10,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Fetch latest fund lab metrics and auto-tune sleeve weights by Sharpe.
    Reads the cached fund-lab/live result from app state or calls the service.
    """
    mds = getattr(
        getattr(request, "app", None) and request.app.state, "market_data", None
    )
    if mds is None:
        return {"error": "market_data service not initialised"}

    # Try reading from fund_lab cached result first (avoids extra yfinance calls)
    fund_metrics: List[Dict[str, Any]] = []
    try:
        from src.services.fund_lab_service import get_fund_lab_service

        regime = "unknown"
        try:
            regime_svc = getattr(request.app.state, "regime_service", None)
            if regime_svc is not None:
                r = await regime_svc.get()
                regime = (r or {}).get("trend", "unknown")
        except Exception:
            pass

        result = await get_fund_lab_service().run(
            mds, period="3mo", benchmark="SPY", top_n=5, regime=regime
        )
        fund_metrics = result.get("funds", [])
    except Exception as exc:
        logger.warning("fund-tune: could not fetch fund metrics: %s", exc)
        return {"error": str(exc)}

    new_weights = tune_fund_weights(fund_metrics, learning_rate=learning_rate)
    return sanitize_for_json(
        {
            "status": "ok",
            "new_weights": new_weights,
            "funds_used": [f.get("name") for f in fund_metrics],
        }
    )


# ── Kill switch ───────────────────────────────────────────────────────────────


@router.post("/disable")
async def disable_learning(_: bool = Depends(verify_api_key)) -> Dict[str, Any]:
    """Kill switch — disable all auto-tuning immediately."""
    _get_engine().disable()
    return {"status": "disabled"}


@router.post("/enable")
async def enable_learning(_: bool = Depends(verify_api_key)) -> Dict[str, Any]:
    """Re-enable auto-tuning."""
    _get_engine().enable()
    return {"status": "enabled"}
