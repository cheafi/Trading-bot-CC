"""
Self-Learn Router — Sprint 96 / 98 / 103
==========================================
Exposes the SelfLearningEngine, regime-conditioned params, fund
weight auto-tuner, Brier calibration tracker, A/B shadow harness,
Thompson RL sizing engine, and feature IC decay detector.

Routes:
  GET  /api/v7/self-learn/status              — engine state + recent audit log
  GET  /api/v7/self-learn/regime-params       — per-regime parameter table
  GET  /api/v7/self-learn/fund-weights        — current fund sleeve allocations
  GET  /api/v7/self-learn/calibration         — Brier score + drift alert      (Sprint 98)
  GET  /api/v7/self-learn/calibration/by-strategy — per-strategy Brier         (Sprint 102)
  GET  /api/v7/self-learn/ab-status           — A/B shadow harness state        (Sprint 98)
  GET  /api/v7/self-learn/thompson            — all Thompson arms               (Sprint 103)
  GET  /api/v7/self-learn/feature-ic          — feature IC decay status         (Sprint 103)
  POST /api/v7/self-learn/trigger             — run one analysis+adjust cycle
  POST /api/v7/self-learn/fund-tune           — update fund weights from latest metrics
  POST /api/v7/self-learn/regime-tune         — auto-tune per-regime params     (Sprint 98)
  POST /api/v7/self-learn/ab-propose          — propose a challenger param       (Sprint 98)
  POST /api/v7/self-learn/ab-evaluate         — evaluate A/B promotion           (Sprint 98)
  POST /api/v7/self-learn/thompson/update     — record trade outcome → update arm (Sprint 103)
  POST /api/v7/self-learn/feature-ic/record   — record feature values + outcome  (Sprint 103)
  POST /api/v7/self-learn/disable             — kill switch
  POST /api/v7/self-learn/enable              — re-enable
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.engines.self_learning import (
    SelfLearningEngine,
    analyze_regime_performance,
    evaluate_ab_promotion,
    get_ab_status,
    get_calibration_status,
    get_params_for_regime,
    load_fund_weights,
    load_regime_params,
    propose_ab_shadow,
    pull_closed_trades_from_learning_loop,
    record_prediction_outcome,
    tune_fund_weights,
    tune_regime_params,
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


# ── Regime-param auto-tune  (Sprint 98) ──────────────────────────────────────


@router.post("/regime-tune")
async def regime_tune(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Auto-adjust per-regime params based on closed-trade win-rates.
    Requires ≥15 trades per regime before making changes.
    """
    trades = pull_closed_trades_from_learning_loop()
    if not trades:
        return {"status": "skipped", "reason": "no closed trades", "changes": {}}
    changes = tune_regime_params(trades)
    return sanitize_for_json(
        {"status": "ok", "trades_analysed": len(trades), "changes": changes}
    )


# ── Calibration drift (Sprint 98) ────────────────────────────────────────────


@router.get("/calibration")
async def calibration_status(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Brier score + calibration drift alert."""
    return sanitize_for_json(get_calibration_status())


@router.post("/calibration/record")
async def record_outcome(
    confidence: float,
    win: bool,
    strategy: str = "",
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Record one (confidence, outcome) pair and update Brier score."""
    result = record_prediction_outcome(confidence, win, strategy=strategy)
    return sanitize_for_json(result)


@router.get("/calibration/by-strategy")
async def calibration_by_strategy(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Per-strategy Brier score decomposition."""
    status = get_calibration_status()
    return sanitize_for_json(
        {
            "by_strategy": status.get("by_strategy", {}),
            "overall_brier": status.get("brier_score"),
            "overall_window": status.get("window", 0),
        }
    )


# ── A/B shadow harness (Sprint 98) ───────────────────────────────────────────


@router.get("/ab-status")
async def ab_status(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Current A/B shadow harness state for all tracked params."""
    return sanitize_for_json(get_ab_status())


@router.post("/ab-propose")
async def ab_propose(
    param: str,
    challenger_value: float,
    reason: str = "",
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Propose a challenger param value for shadow testing."""
    result = propose_ab_shadow(param, challenger_value, reason)
    return sanitize_for_json({"status": "proposed", "challenger": result})


@router.post("/ab-evaluate")
async def ab_evaluate(
    param: str,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Evaluate A/B promotion eligibility for a tracked param."""
    result = evaluate_ab_promotion(param)
    return sanitize_for_json(result)


# ── Thompson RL Sizing (Sprint 103) ──────────────────────────────────────────


@router.get("/thompson")
async def thompson_arms(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """All Thompson sampling arms (strategy×regime Beta distributions)."""
    from src.engines.thompson_sizing import get_thompson_engine  # noqa: PLC0415

    eng = get_thompson_engine()
    arms = eng.get_all_arms()
    best = eng.recommend_best_arm()
    return sanitize_for_json(
        {
            "arms": arms,
            "total_arms": len(arms),
            "best_arm": best,
        }
    )


@router.post("/thompson/update")
async def thompson_update(
    strategy: str,
    regime: str,
    win: bool,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Record trade outcome and update Thompson arm for (strategy, regime)."""
    from src.engines.thompson_sizing import get_thompson_engine  # noqa: PLC0415

    arm = get_thompson_engine().update(strategy, regime, win)
    return sanitize_for_json({"status": "updated", "arm": arm.to_dict()})


@router.get("/thompson/sample")
async def thompson_sample(
    strategy: str,
    regime: str,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Sample a sizing multiplier from the Thompson arm for (strategy, regime)."""
    from src.engines.thompson_sizing import get_thompson_engine  # noqa: PLC0415

    eng = get_thompson_engine()
    multiplier = eng.sample(strategy, regime)
    arm = eng.get_arm(strategy, regime)
    return sanitize_for_json(
        {
            "strategy": strategy.upper(),
            "regime": regime.upper(),
            "multiplier": round(multiplier, 4),
            "arm": arm.to_dict() if arm else None,
        }
    )


# ── Feature IC Decay (Sprint 103) ─────────────────────────────────────────────


@router.get("/feature-ic")
async def feature_ic_status(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Feature IC scores, peaks, decay and alerts."""
    from src.engines.feature_ic import get_feature_ic_status  # noqa: PLC0415

    return sanitize_for_json(get_feature_ic_status())


@router.post("/feature-ic/record")
async def record_feature_ic(
    win: bool,
    final_confidence: float = 0.0,
    rs_composite: float = 0.0,
    mtf_confluence_score: float = 0.0,
    thesis_confidence: float = 0.0,
    timing_confidence: float = 0.0,
    vix: float = 0.0,
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Record feature values + outcome for IC tracking."""
    from src.engines.feature_ic import record_feature_outcomes  # noqa: PLC0415

    feats = {
        "final_confidence": final_confidence or None,
        "rs_composite": rs_composite or None,
        "mtf_confluence_score": mtf_confluence_score or None,
        "thesis_confidence": thesis_confidence or None,
        "timing_confidence": timing_confidence or None,
        "vix": vix or None,
    }
    feats = {k: v for k, v in feats.items() if v is not None}
    result = record_feature_outcomes(feats, win)
    return sanitize_for_json(result)
