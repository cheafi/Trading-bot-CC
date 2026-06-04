"""
Drawdown budget sizing — template reduction from book DD, not deploy permission.

Blocked entirely in research_only / confirm-only / fallback / stale modes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.signal_provenance import (
    SIGNAL_DRAWDOWN_SIZER,
    build_provenance_envelope,
)

MODE_FULL = "full"
MODE_REDUCED = "reduced"
MODE_MINIMAL = "minimal"
MODE_BLOCKED = "blocked"

MODE_LABELS: Dict[str, str] = {
    MODE_FULL: "Full template — DD within budget",
    MODE_REDUCED: "Reduced size — DD pressure",
    MODE_MINIMAL: "Minimal pilot — DD elevated",
    MODE_BLOCKED: "Sizing blocked — surface not authoritative",
}


def evaluate_drawdown_sizing(
    *,
    current_dd_pct: float,
    dd_budget_pct: float = 15.0,
    peak_dd_pct: float = 0.0,
    research_only: bool = False,
    confirm_only: bool = False,
    fallback_or_stale: bool = False,
) -> Dict[str, Any]:
    """
    Map portfolio drawdown to sizing mode.

    research_only / confirm_only / fallback_or_stale => MODE_BLOCKED (no authority).
    """
    if research_only or confirm_only or fallback_or_stale:
        return {
            "sizing_mode": MODE_BLOCKED,
            "sizing_label": MODE_LABELS[MODE_BLOCKED],
            "size_multiplier": 0.0,
            "has_sizing_authority": False,
            "blocked_reason": (
                "confirm_only"
                if confirm_only
                else "research_only"
                if research_only
                else "fallback_or_stale"
            ),
            "restore_when": "Board deploy authority + live book sync",
        }

    budget = max(5.0, float(dd_budget_pct))
    dd = max(0.0, float(current_dd_pct))
    peak = max(dd, float(peak_dd_pct))
    utilization = dd / budget if budget else 1.0

    if dd >= budget or peak >= budget * 1.2:
        mode = MODE_MINIMAL
        mult = 0.25
        restore = f"DD < {budget * 0.6:.0f}% for 5 sessions"
    elif utilization >= 0.75:
        mode = MODE_REDUCED
        mult = 0.5
        restore = f"DD < {budget * 0.5:.0f}% and no DD acceleration"
    else:
        mode = MODE_FULL
        mult = 1.0
        restore = "Within drawdown budget"

    return {
        "sizing_mode": mode,
        "sizing_label": MODE_LABELS[mode],
        "size_multiplier": mult,
        "has_sizing_authority": mode != MODE_BLOCKED,
        "dd_utilization_pct": round(utilization * 100, 1),
        "dd_budget_pct": budget,
        "current_dd_pct": round(dd, 2),
        "restore_when": restore,
        "deploy_from_sizer_alone": False,
    }


def build_drawdown_sizer_context(
    *,
    current_dd_pct: float = 8.5,
    dd_budget_pct: float = 15.0,
    research_only: bool = False,
    degraded: bool = False,
) -> Dict[str, Any]:
    sizing = evaluate_drawdown_sizing(
        current_dd_pct=current_dd_pct,
        dd_budget_pct=dd_budget_pct,
        research_only=research_only or degraded,
        fallback_or_stale=degraded,
    )
    return build_provenance_envelope(
        signal_type=SIGNAL_DRAWDOWN_SIZER,
        source="mock-dd-sizer-stub",
        degraded=degraded or True,
        extra={"sizing": sizing, "surface_hint": "portfolio"},
    )
