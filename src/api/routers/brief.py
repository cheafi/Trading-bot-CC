"""
Morning Brief Router — Sprint 64
===================================
/api/brief — Top 3 setups, regime, portfolio heat, risk.
/api/brief/diff — What changed since yesterday.
/api/brief/regime — Current regime with history.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/brief", tags=["brief"])


@router.get("")
async def morning_brief():
    """
    Morning brief: regime, top setups, portfolio heat, risk.
    """
    from src.engines.macro_regime_engine import MacroRegimeEngine

    engine = MacroRegimeEngine()

    # Generate synthetic regime from defaults if no live data
    spy = [500 + i * 0.1 for i in range(60)]
    result = engine.compute(spy)

    return {
        "regime": result.to_dict(),
        "top_setups": [],
        "portfolio_heat": {"positions": 0, "max": 10},
        "risk_watch": result.signals[:3] if result.signals else [],
        "note": "Wire live data for real-time brief",
    }


@router.get("/diff")
async def decision_diff():
    """What changed since yesterday."""
    try:
        from src.engines.decision_tracker import DecisionTracker
        tracker = DecisionTracker()
        diffs = tracker.get_diffs()
        tracker.close()
        return {
            "diffs": diffs,
            "count": len(diffs),
            "upgrades": sum(1 for d in diffs if d["change"] == "UPGRADE"),
            "downgrades": sum(
                1 for d in diffs if d["change"] == "DOWNGRADE"
            ),
            "new": sum(1 for d in diffs if d["change"] == "NEW"),
        }
    except Exception as e:
        return {"error": str(e), "diffs": []}


@router.get("/regime")
async def regime_status():
    """Current regime with history."""
    try:
        from src.engines.decision_tracker import DecisionTracker
        tracker = DecisionTracker()
        history = tracker.get_regime_history(limit=10)
        tracker.close()
        return {
            "current": history[0] if history else None,
            "history": history,
        }
    except Exception as e:
        return {"error": str(e), "current": None, "history": []}


@router.get("/strategies")
async def available_strategies():
    """List available fund strategies."""
    from src.engines.fund_builder import STRATEGY_PROFILES
    return {"strategies": STRATEGY_PROFILES}


@router.get("/circuit-breaker")
async def circuit_breaker_status():
    """Check drawdown circuit breaker status."""
    from src.engines.drawdown_breaker import DrawdownCircuitBreaker
    breaker = DrawdownCircuitBreaker()
    # Default: check with sample values
    result = breaker.check(100000, 100000, 100000)
    return result.to_dict()
