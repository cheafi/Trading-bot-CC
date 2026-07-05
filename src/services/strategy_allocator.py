"""
Strategy allocator — sleeve budgets and routing suggestions (research / hints).

Does not route live orders; strongest/weakest hints for mission panel only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_STRATEGY_ALLOCATION,
    build_provenance_envelope,
)

STATE_ACTIVE = "active"
STATE_REDUCED = "reduced"
STATE_PAUSED = "paused"
STATE_TRAINING = "training"


def _sleeve_state(
    *,
    budget_pct: float,
    utilization_pct: float,
    gate_status: str,
) -> str:
    gs = str(gate_status or "").upper()
    if gs == "PAUSED":
        return STATE_PAUSED
    if utilization_pct > 90 or gs == "REDUCED":
        return STATE_REDUCED
    if gs == "ACTIVE":
        return STATE_ACTIVE
    return STATE_TRAINING


def build_sleeve_budgets(
    sleeves: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Default sleeve budget table when none supplied."""
    default = sleeves or [
        {"id": "core_momentum", "name": "Core momentum", "budget_pct": 35, "utilization_pct": 62},
        {"id": "satellite_breakout", "name": "Satellite breakout", "budget_pct": 20, "utilization_pct": 40},
        {"id": "defensive_quality", "name": "Defensive quality", "budget_pct": 25, "utilization_pct": 28},
        {"id": "pilot_experimental", "name": "Pilot experimental", "budget_pct": 10, "utilization_pct": 15},
    ]
    out: List[Dict[str, Any]] = []
    for s in default:
        util = float(s.get("utilization_pct") or 0)
        budget = float(s.get("budget_pct") or 0)
        gate = s.get("gate_status") or "ACTIVE"
        state = _sleeve_state(budget_pct=budget, utilization_pct=util, gate_status=gate)
        out.append(
            {
                **s,
                "allocator_state": state,
                "headroom_pct": round(max(0, budget - util * budget / 100), 1) if budget else 0,
                "controls_capital": False,
            }
        )
    return out


def routing_suggestion(sleeves: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Strongest / weakest by utilization headroom — hint only."""
    if not sleeves:
        return {"strongest": None, "weakest": None, "suggestion": "No sleeves configured"}
    active = [s for s in sleeves if s.get("allocator_state") != STATE_PAUSED]
    if not active:
        return {"strongest": None, "weakest": None, "suggestion": "All sleeves paused — no routing hint"}
    by_headroom = sorted(active, key=lambda x: -(x.get("headroom_pct") or 0))
    strongest = by_headroom[0]
    weakest = by_headroom[-1]
    return {
        "strongest": {"id": strongest.get("id"), "name": strongest.get("name")},
        "weakest": {"id": weakest.get("id"), "name": weakest.get("name")},
        "suggestion": (
            f"Research hint: {strongest.get('name')} has most budget headroom; "
            f"{weakest.get('name')} most constrained — not a trade route"
        ),
    }


def downgrade_routing_suggestion(
    *,
    tradeability: str = "WAIT",
    sleeves: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Sleeve routing downgrade-only — never upgrades deploy posture."""
    ctx = build_allocator_context(sleeves=sleeves)
    route = ctx.get("routing") or {}
    tb = str(tradeability or "").upper()
    if tb in ("NO_TRADE", "WAIT"):
        route = {
            **route,
            "suggestion": "WAIT day — sleeve routing frozen (downgrade-only hint)",
            "downgrade_only": True,
        }
    else:
        route = {**route, "downgrade_only": True}
    ctx["routing"] = route
    ctx["downgrade_only"] = True
    return ctx


def build_allocator_context(
    *,
    sleeves: Optional[List[Dict[str, Any]]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    budgeted = build_sleeve_budgets(sleeves)
    route = routing_suggestion(budgeted)
    body = {
        "sleeves": budgeted,
        "routing": route,
        "sleeve_strip": {
            "strongest": route.get("strongest"),
            "weakest": route.get("weakest"),
        },
        "controls_capital": False,
        "deploy_from_allocator_alone": False,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_STRATEGY_ALLOCATION,
        source="mock-allocator-stub",
        degraded=degraded or True,
        extra=body,
    )
