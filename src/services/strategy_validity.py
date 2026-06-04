"""
Strategy validity — decay score, OOS holdout, overfit flags (research).

Backtest / walk-forward metrics ≠ live edge; no deploy from validity alone.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.signal_provenance import (
    SIGNAL_STRATEGY_VALIDITY,
    build_provenance_envelope,
)

FLAG_OOS_PASS = "oos_pass"
FLAG_OOS_FAIL = "oos_fail"
FLAG_OVERFIT = "overfit_suspect"
FLAG_DECAY = "expectancy_decay"


def compute_decay_score(
    *,
    in_sample_sharpe: float,
    oos_sharpe: float,
    recent_expectancy_r: float,
    baseline_expectancy_r: float,
) -> float:
    """0–100 — higher = healthier (less decay)."""
    sharpe_gap = max(0.0, in_sample_sharpe - oos_sharpe)
    exp_ratio = (
        recent_expectancy_r / baseline_expectancy_r
        if baseline_expectancy_r > 0
        else 0.5
    )
    penalty = sharpe_gap * 25 + (1.0 - min(1.0, exp_ratio)) * 35
    return round(max(0.0, min(100.0, 100.0 - penalty)), 1)


def evaluate_validity_flags(
    *,
    in_sample_sharpe: float,
    oos_sharpe: float,
    oos_trades: int,
    param_count: int = 8,
    n_trades: int = 80,
) -> Dict[str, Any]:
    flags: list[str] = []
    if oos_trades < 15:
        flags.append(FLAG_OOS_FAIL)
    elif oos_sharpe >= 0.5 and oos_sharpe >= in_sample_sharpe * 0.6:
        flags.append(FLAG_OOS_PASS)
    else:
        flags.append(FLAG_OOS_FAIL)

    if param_count > 6 and n_trades < param_count * 12:
        flags.append(FLAG_OVERFIT)
    if in_sample_sharpe > 1.5 and oos_sharpe < 0.3:
        flags.append(FLAG_OVERFIT)
    if oos_sharpe < in_sample_sharpe * 0.4:
        flags.append(FLAG_DECAY)

    decay = compute_decay_score(
        in_sample_sharpe=in_sample_sharpe,
        oos_sharpe=oos_sharpe,
        recent_expectancy_r=oos_sharpe * 0.2,
        baseline_expectancy_r=in_sample_sharpe * 0.25,
    )
    investable_research = FLAG_OOS_PASS in flags and FLAG_OVERFIT not in flags
    return {
        "decay_score": decay,
        "flags": flags,
        "oos_sharpe": oos_sharpe,
        "in_sample_sharpe": in_sample_sharpe,
        "overfit_risk": FLAG_OVERFIT in flags,
        "investable_in_research_only": investable_research,
        "live_edge_claim": False,
        "deploy_from_validity_alone": False,
    }


def build_strategy_validity_context(
    strategy_id: str = "momentum_breakout_v2",
    *,
    in_sample_sharpe: float = 1.1,
    oos_sharpe: float = 0.75,
    oos_trades: int = 28,
    degraded: bool = False,
) -> Dict[str, Any]:
    validity = evaluate_validity_flags(
        in_sample_sharpe=in_sample_sharpe,
        oos_sharpe=oos_sharpe,
        oos_trades=oos_trades,
    )
    body = {
        "strategy_id": strategy_id,
        "validity": validity,
        "backtest_not_live_edge": True,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_STRATEGY_VALIDITY,
        source="mock-validity-stub",
        degraded=degraded or True,
        extra=body,
    )
