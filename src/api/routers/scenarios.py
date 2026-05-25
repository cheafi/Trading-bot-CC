"""Portfolio stress scenarios."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request

from src.engines.scenario_engine import ScenarioEngine

router = APIRouter(prefix="/api/scenarios", tags=["risk"])
_scenario_engine = ScenarioEngine()


async def _proxy_portfolio(request: Request, limit: int = 10) -> List[Dict[str, Any]]:
    scan = getattr(request.app.state, "scan_signals", None)
    if scan is None:
        return [{"ticker": "SPY", "weight": 1.0, "entry_price": 500}]
    try:
        scanned, _ = await scan(limit=limit)
        if not scanned:
            raise ValueError("empty scan")
        return [
            {
                "ticker": r.get("ticker", ""),
                "weight": 1.0 / max(len(scanned), 1),
                "entry_price": r.get("entry_price", 100),
            }
            for r in scanned
        ]
    except Exception:
        return [{"ticker": "SPY", "weight": 1.0, "entry_price": 500}]


@router.get("")
async def list_scenarios():
    """List available stress test scenarios."""
    return {"scenarios": _scenario_engine.list_scenarios()}


@router.post("/run")
async def run_stress_scenario(
    request: Request,
    scenario_key: str = Query(..., description="Scenario key"),
):
    """Run portfolio through a stress scenario."""
    positions = await _proxy_portfolio(request, limit=10)
    result = _scenario_engine.run_scenario(scenario_key, positions)
    return result.to_dict()


@router.get("/run-all")
async def run_all_scenarios(request: Request):
    """Run portfolio through ALL stress scenarios."""
    positions = await _proxy_portfolio(request, limit=10)
    results = _scenario_engine.run_all_scenarios(positions)
    return {"portfolio_size": len(positions), "scenarios": results}
