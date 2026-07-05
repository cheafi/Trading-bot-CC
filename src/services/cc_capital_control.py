"""
Capital control layer — sizing support advisory unless on deploy surfaces.

Blocked on research-only / confirm-only / stale / fallback paths.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.drawdown_sizer import (
    MODE_BLOCKED,
    MODE_FULL,
    MODE_MINIMAL,
    MODE_REDUCED,
    evaluate_drawdown_sizing,
)

AUTHORITY_RESEARCH = "research_only"
AUTHORITY_ADVISORY = "deploy_surface_support"


def build_capital_control_context(
    *,
    current_dd_pct: float = 0.0,
    dd_budget_pct: float = 15.0,
    vix: Optional[float] = None,
    tradeability: str = "WAIT",
    execution_fill_status: Optional[str] = None,
    event_risk_blocked: bool = False,
    liquidity_fit: str = "unknown",
    research_only: bool = False,
    fallback_or_stale: bool = False,
    on_deploy_surface: bool = False,
) -> Dict[str, Any]:
    """
    Unified capital control — DD, vol, execution, event, liquidity haircuts.
    """
    base = evaluate_drawdown_sizing(
        current_dd_pct=current_dd_pct,
        dd_budget_pct=dd_budget_pct,
        research_only=research_only,
        fallback_or_stale=fallback_or_stale,
    )
    mult = float(base.get("size_multiplier") or 0.0)
    haircuts: Dict[str, float] = {}
    notes: list[str] = []

    if vix is not None and float(vix) > 24:
        haircuts["vol_scaled"] = 0.85
        mult *= 0.85
        notes.append("Vol-scaled haircut — VIX elevated")
    elif vix is not None and float(vix) < 14:
        haircuts["vol_scaled"] = 1.0
        notes.append("Vol compression band — no vol haircut")

    if execution_fill_status in ("degraded", "unknown"):
        haircuts["execution_quality"] = 0.9
        mult *= 0.9
        notes.append("Execution-quality haircut — fill sample weak")

    if event_risk_blocked:
        haircuts["event_risk"] = 0.75
        mult *= 0.75
        notes.append("Event-risk haircut — downgrade-only")

    if liquidity_fit == "tight":
        haircuts["liquidity"] = 0.8
        mult *= 0.8
        notes.append("Liquidity-fit haircut — capacity pressure")

    tb = (tradeability or "").upper()
    if tb == "WAIT":
        haircuts["regime_band"] = 0.5
        mult = min(mult, 0.5)
        notes.append("Regime WAIT — capital band capped in research")

    mult = round(max(0.0, min(1.0, mult)), 2)
    mode = base.get("sizing_mode") or MODE_BLOCKED
    if mode == MODE_BLOCKED:
        mult = 0.0

    authority = AUTHORITY_ADVISORY if on_deploy_surface and mode != MODE_BLOCKED else AUTHORITY_RESEARCH

    restore = str(base.get("restore_when") or "DD within budget + board gate")
    if mult < 1.0 and mode != MODE_BLOCKED:
        restore = f"{restore}; remove haircuts as vol/event/execution clear"

    return {
        "authority": authority,
        "research_only": authority == AUTHORITY_RESEARCH,
        "may_authorize_deploy": False,
        "deploy_from_sizer_alone": False,
        "degraded": fallback_or_stale or research_only,
        "base_sizing": base,
        "combined_multiplier": mult,
        "haircuts": haircuts,
        "haircut_notes": notes,
        "vol_scaled_support": haircuts.get("vol_scaled") is not None,
        "regime_capital_band": tb,
        "restore_logic": restore,
        "strip_line": (
            f"Capital control: {mode} · {mult}× template"
            + (" — advisory on deploy surface" if on_deploy_surface else " — research only")
        ),
    }
