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
    Loads the latest data/brief-*.json for real actionable signals.
    """
    import json, glob, os
    from src.services.regime_service import RegimeService

    regime = RegimeService.get()

    # Load latest brief file for real setups
    brief_data = {}
    try:
        brief_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
        files = sorted(glob.glob(os.path.join(brief_dir, "brief-*.json")))
        if files:
            with open(files[-1]) as f:
                brief_data = json.load(f)
    except Exception:
        pass

    actionable = brief_data.get("actionable", [])
    watch = brief_data.get("watch", [])
    top_setups = actionable[:5] if actionable else watch[:3]

    return {
        "regime": regime,
        "date": brief_data.get("date"),
        "headline": brief_data.get("headline", "No brief available"),
        "top_setups": top_setups,
        "portfolio_heat": {"positions": len(brief_data.get("holdings_with_signals", [])), "max": 10},
        "risk_watch": regime.get("signals", [])[:3],
        "synthetic": regime.get("synthetic", False),
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


@router.get("/changelog")
async def changelog():
    """Recent changes since last deployment."""
    import json
    import os
    import subprocess

    entries = []

    # Try git first (works locally, not in Docker)
    for cwd in [
        "/app",
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(__file__))
            )
        ),
    ]:
        try:
            out = subprocess.check_output(
                ["git", "log", "--oneline", "-20"],
                cwd=cwd,
                text=True,
                timeout=5,
                stderr=subprocess.DEVNULL,
            ).strip()
            for line in out.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    entries.append({
                        "hash": parts[0],
                        "message": parts[1],
                    })
            if entries:
                break
        except Exception:
            pass

    # Fallback: baked changelog.json (Docker)
    if not entries:
        for p in ["/app/changelog.json", "changelog.json"]:
            if os.path.isfile(p):
                try:
                    with open(p) as f:
                        entries = json.load(f)
                    break
                except Exception:
                    pass
    return {"entries": entries, "count": len(entries)}


@router.get("/circuit-breaker")
async def circuit_breaker_status():
    """Check drawdown circuit breaker status."""
    from src.engines.drawdown_breaker import DrawdownCircuitBreaker
    breaker = DrawdownCircuitBreaker()
    # Default: check with sample values
    result = breaker.check(100000, 100000, 100000)
    return result.to_dict()
