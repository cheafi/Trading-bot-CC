"""
API endpoints for the new intelligence engines:
  - Benchmark portfolio attribution
  - Symbol comparison (vs peers/sector/index)
  - Rejection analysis
  - Self-learning status

Mount these in the main FastAPI app or use standalone.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v6", tags=["intelligence"])


# ── Dependency: API key verification ──────────────────────────────

from src.api.deps import verify_api_key as _verify_api_key_dep


async def _verify_api_key() -> bool:
    """Shared verify_api_key dependency from deps.py."""
    return await _verify_api_key_dep()


# ═══════════════════════════════════════════════════════════════════
# BENCHMARK PORTFOLIO ATTRIBUTION
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/benchmark-attribution",
    summary="Portfolio vs benchmark attribution analysis",
)
async def benchmark_attribution(
    request: Request,
    _: bool = Depends(_verify_api_key),
):
    """
    Compute portfolio attribution vs SPY benchmark.

    Returns: Brinson attribution, factor exposures, risk metrics,
    sector contributions, alpha/beta.
    """
    try:
        from src.engines.benchmark_portfolio import (  # noqa: PLC0415
            BenchmarkPortfolioEngine,
            PositionSnapshot,
        )

        engine = BenchmarkPortfolioEngine(benchmark="SPY")

        # Build positions from today's trades (best-effort)
        positions = []
        try:
            eng = getattr(request.app.state, "engine", None)
            if eng and hasattr(eng, "_trades_today"):
                for t in eng._trades_today:
                    positions.append(PositionSnapshot(
                        ticker=t.get("ticker", ""),
                        weight=t.get("position_size_pct", 0.05),
                        return_pct=t.get("pnl_pct", 0),
                        sector=t.get("sector", "Unknown"),
                    ))
        except Exception:
            pass

        if not positions:
            return {
                "status": "no_data",
                "message": "No position data available for attribution",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        attribution = engine.compute_attribution(
            positions=positions,
            benchmark_return=0.0,
        )

        return {
            "status": "ok",
            "attribution": attribution.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Benchmark attribution error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# SYMBOL COMPARISON
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/compare/{ticker}",
    summary="Compare symbol vs peers/sector/index",
)
async def compare_symbol(
    request: Request,
    ticker: str,
    vs: str = Query("index", description="Comparison target: index, sector, peers"),
    benchmark: str = Query("SPY", description="Benchmark ticker for index comparison"),
    _: bool = Depends(_verify_api_key),
):
    """
    Compare a ticker against peers, sector ETF, or index.

    Returns: relative strength, momentum rank, beta, verdict.
    """
    try:
        import numpy as np
        from src.engines.symbol_comparison import SymbolComparisonEngine

        engine = SymbolComparisonEngine()
        ticker = ticker.upper().strip()

        # Fetch price data via MarketDataService (cached, thread-pool safe)
        try:
            svc = getattr(getattr(request, "app", None) and request.app.state, "market_data", None)
            if svc is None:
                return {"status": "error", "message": "market_data service not initialised"}

            ticker_df = await svc.get_history(ticker, period="1y", interval="1d")
            benchmark_df = await svc.get_history(benchmark, period="1y", interval="1d")

            if ticker_df is None or ticker_df.empty or benchmark_df is None or benchmark_df.empty:
                return {"status": "no_data", "ticker": ticker, "benchmark": benchmark}

            ticker_closes = ticker_df["Close"].dropna().values.flatten()
            benchmark_closes = benchmark_df["Close"].dropna().values.flatten()

            ticker_returns = np.diff(ticker_closes) / ticker_closes[:-1] * 100
            benchmark_returns = np.diff(benchmark_closes) / benchmark_closes[:-1] * 100

            result = engine.compare_vs_benchmark(
                ticker_returns, benchmark_returns,
                ticker, benchmark, vs,
            )

            return {
                "status": "ok",
                "comparison": result.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.error("Symbol comparison error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# REJECTION ANALYSIS
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/rejection-analysis",
    summary="Analyze rejected signals and confidence disagreements",
)
async def rejection_analysis(
    request: Request,
    _: bool = Depends(_verify_api_key),
):
    """
    Analyze rejected signals: categorization, false negatives,
    confidence disagreements, rule recommendations.
    """
    try:
        from src.engines.rejection_analysis import RejectionAnalysisEngine

        engine = RejectionAnalysisEngine()

        # Try to load rejections from the engine singleton
        try:
            eng = getattr(request.app.state, "engine", None)
            if eng and hasattr(eng, "_signals_today"):
                for sig in eng._signals_today:
                    if hasattr(sig, 'approval_status') and sig.approval_status == "rejected":
                        from src.engines.rejection_analysis import RejectionRecord
                        engine.record_rejection(RejectionRecord(
                            ticker=sig.ticker,
                            strategy=sig.strategy_id or "unknown",
                            direction=sig.direction.value if hasattr(sig.direction, 'value') else str(sig.direction),
                            confidence=sig.confidence,
                            rejection_reasons=[sig.why_not_trade] if sig.why_not_trade else ["rejected"],
                        ))
        except Exception:
            pass

        analysis = engine.analyze()

        return {
            "status": "ok",
            "analysis": analysis.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Rejection analysis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# SELF-LEARNING STATUS
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/self-learning",
    summary="Self-learning engine status and audit trail",
)
async def self_learning_status(
    _: bool = Depends(_verify_api_key),
):
    """
    Return current self-learning state: enabled/disabled,
    total adjustments, recent audit log, tunable rules.
    """
    try:
        from src.engines.self_learning import SelfLearningEngine, TUNABLE_RULES

        engine = SelfLearningEngine()

        return {
            "status": "ok",
            "state": engine.state.to_dict(),
            "tunable_rules": {
                k: {
                    "description": v["description"],
                    "min": v["min"],
                    "max": v["max"],
                    "default": v["default"],
                }
                for k, v in TUNABLE_RULES.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Self-learning status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/self-learning/disable",
    summary="Disable self-learning auto-tuning",
)
async def self_learning_disable(
    _: bool = Depends(_verify_api_key),
):
    """Kill switch: disable all auto-tuning."""
    from src.engines.self_learning import SelfLearningEngine
    engine = SelfLearningEngine()
    engine.disable()
    return {"status": "ok", "message": "Self-learning disabled"}


@router.post(
    "/self-learning/enable",
    summary="Enable self-learning auto-tuning",
)
async def self_learning_enable(
    _: bool = Depends(_verify_api_key),
):
    """Re-enable auto-tuning."""
    from src.engines.self_learning import SelfLearningEngine
    engine = SelfLearningEngine()
    engine.enable()
    return {"status": "ok", "message": "Self-learning enabled"}
