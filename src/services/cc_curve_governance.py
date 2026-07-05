"""
Strategy curve / sleeve governance — research and allocator support only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.strategy_curve_health import (
    HEALTH_MONITOR,
    HEALTH_PAUSED,
    HEALTH_PILOT,
    HEALTH_REDUCED,
    build_curve_metrics,
    evaluate_regime_filter,
    resolve_health_state,
)

SLEEVE_FULL = "full"
SLEEVE_REDUCED = "reduced"
SLEEVE_PILOT = "pilot"
SLEEVE_PAUSED = "paused"
SLEEVE_MONITOR = "monitor"

_STATE_MACHINE: Dict[str, str] = {
    "full_size": SLEEVE_FULL,
    "reduced": SLEEVE_REDUCED,
    "pilot": SLEEVE_PILOT,
    "paused": SLEEVE_PAUSED,
    "monitor": SLEEVE_MONITOR,
}


def _sleeve_state_from_health(health_state: str) -> Dict[str, Any]:
    sleeve = _STATE_MACHINE.get(health_state, SLEEVE_MONITOR)
    restore = "Board gate + curve trend up + DD stable"
    if sleeve == SLEEVE_PAUSED:
        restore = "Walk-forward Sharpe > 0.6 and max DD < 18% for 2 windows"
    elif sleeve == SLEEVE_REDUCED:
        restore = "Expectancy stable and DD not accelerating"
    return {
        "sleeve_state": sleeve,
        "health_state": health_state,
        "restore_hint": restore,
        "deploy_from_sleeve_alone": False,
        "research_only": True,
    }


def build_curve_governance_context(
    *,
    sharpe_wf: float = 0.85,
    max_dd_pct: float = 14.5,
    win_rate: float = 0.48,
    n_trades: int = 42,
    expectancy_r: float = 0.35,
    live_sharpe: Optional[float] = None,
    paper_sharpe: Optional[float] = None,
    sleeve_cards: Optional[List[Dict[str, Any]]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Curve + sleeve governance bundle for Backtest Lab / Funds."""
    metrics = build_curve_metrics(
        sharpe_wf=sharpe_wf,
        max_dd_pct=max_dd_pct,
        win_rate=win_rate,
        n_trades=n_trades,
        expectancy_r=expectancy_r,
    )
    regime = metrics.get("regime_filter") or evaluate_regime_filter(n_trades=n_trades)
    health = metrics.get("health_state") or HEALTH_MONITOR
    sleeve = _sleeve_state_from_health(health)

    divergence: Dict[str, Any] = {"label": "Divergence unknown — insufficient live sample"}
    if live_sharpe is not None and sharpe_wf:
        gap = float(live_sharpe) - float(sharpe_wf)
        if gap < -0.4:
            divergence = {
                "gap": round(gap, 2),
                "label": f"Live vs backtest divergence {gap:+.2f} Sharpe — validity downgrade",
                "downgrade_only": True,
            }
        else:
            divergence = {
                "gap": round(gap, 2),
                "label": f"Live vs backtest within band ({gap:+.2f} Sharpe)",
            }

    overfit_risk = "elevated" if n_trades < 20 or sharpe_wf > 2.0 else "moderate" if n_trades < 40 else "low"

    sleeves: List[Dict[str, Any]] = []
    for card in (sleeve_cards or [])[:5]:
        name = str(card.get("name") or card.get("sleeve") or "sleeve")
        ret = float(card.get("return_pct") or card.get("ytd_return") or 0)
        eff = round(ret / max(max_dd_pct, 1), 2)
        sleeves.append(
            {
                "name": name,
                "capital_efficiency": eff,
                "label": f"{name} efficiency proxy {eff} — hypothetical research",
            }
        )

    return {
        "authority": "research_only",
        "may_authorize_deploy": False,
        "degraded": degraded or n_trades < 5,
        "curve_metrics": metrics,
        "rolling_trackers": {
            "sharpe_wf": sharpe_wf,
            "max_dd_pct": max_dd_pct,
            "win_rate": win_rate,
            "expectancy_r": expectancy_r,
            "sample_depth": "low" if n_trades < 20 else "adequate",
        },
        "sleeve_governance": sleeve,
        "live_vs_backtest": divergence,
        "live_vs_paper": {
            "gap": (
                round(float(live_sharpe or 0) - float(paper_sharpe or 0), 2)
                if live_sharpe is not None and paper_sharpe is not None
                else None
            ),
            "label": "Paper vs live compare — ops research only",
        },
        "overfit_risk": {
            "level": overfit_risk,
            "label": f"Overfit risk {overfit_risk} — sample {n_trades} trades",
        },
        "sleeve_efficiency": sleeves,
        "regime_filter": regime,
        "strip_line": (
            f"Curve {health} · sleeve {sleeve['sleeve_state']} — "
            "research governance only"
        ),
    }
