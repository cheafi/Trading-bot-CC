"""
Strategy curve health — walk-forward / paper metrics, not deploy permission.

Distinct from strategy_health_service (realized closed trades).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_STRATEGY_CURVE,
    build_provenance_envelope,
)

HEALTH_FULL_SIZE = "full_size"
HEALTH_REDUCED = "reduced"
HEALTH_PILOT = "pilot"
HEALTH_MONITOR = "monitor"
HEALTH_PAUSED = "paused"

HEALTH_LABELS: Dict[str, str] = {
    HEALTH_FULL_SIZE: "Curve healthy — research suggests full-size template only",
    HEALTH_REDUCED: "Curve soft — reduced template in research",
    HEALTH_PILOT: "Curve unproven — pilot template only",
    HEALTH_MONITOR: "Curve watch — monitor, no size change from curve alone",
    HEALTH_PAUSED: "Curve broken — paused in research; board gate still required",
}

# Regime filter sub-labels (curve diagnostics — not deploy gates).
TREND_UP = "trend_up"
TREND_FLAT = "trend_flat"
TREND_DOWN = "trend_down"
DD_ACCEL = "dd_accelerating"
DD_STABLE = "dd_stable"
EXPECTANCY_DECAY = "expectancy_decay"
EXPECTANCY_STABLE = "expectancy_stable"
SAMPLE_LOW = "sample_low"
SAMPLE_OK = "sample_ok"

CURVE_FILTER_LABELS: Dict[str, str] = {
    TREND_UP: "Equity curve trend up (walk-forward)",
    TREND_FLAT: "Flat curve — no size upgrade from trend alone",
    TREND_DOWN: "Downsloping curve — research pause bias",
    DD_ACCEL: "Drawdown accelerating — reduce template in research",
    DD_STABLE: "Drawdown stable within band",
    EXPECTANCY_DECAY: "Expectancy decay vs baseline",
    EXPECTANCY_STABLE: "Expectancy stable",
    SAMPLE_LOW: "Sample size low — monitor only",
    SAMPLE_OK: "Sample size adequate for research tier",
}


def resolve_health_state(
    *,
    sharpe_wf: float,
    max_dd_pct: float,
    win_rate: float,
    n_trades: int,
) -> str:
    if n_trades < 20:
        return HEALTH_MONITOR
    if max_dd_pct > 25 or sharpe_wf < 0:
        return HEALTH_PAUSED
    if sharpe_wf >= 1.2 and max_dd_pct < 12 and win_rate >= 0.45:
        return HEALTH_FULL_SIZE
    if sharpe_wf >= 0.6 and max_dd_pct < 18:
        return HEALTH_REDUCED
    if sharpe_wf >= 0.3:
        return HEALTH_PILOT
    return HEALTH_MONITOR


def evaluate_regime_filter(
    *,
    equity_slope: float = 0.02,
    dd_velocity: float = 0.5,
    expectancy_ratio: float = 0.95,
    n_trades: int = 42,
) -> Dict[str, Any]:
    """Trend, DD acceleration, expectancy decay, and sample-size labels."""
    trend = TREND_UP if equity_slope > 0.01 else TREND_DOWN if equity_slope < -0.01 else TREND_FLAT
    dd_tag = DD_ACCEL if dd_velocity > 1.2 else DD_STABLE
    exp_tag = EXPECTANCY_DECAY if expectancy_ratio < 0.75 else EXPECTANCY_STABLE
    sample = SAMPLE_LOW if n_trades < 20 else SAMPLE_OK
    return {
        "trend": trend,
        "trend_label": CURVE_FILTER_LABELS[trend],
        "dd_regime": dd_tag,
        "dd_label": CURVE_FILTER_LABELS[dd_tag],
        "expectancy": exp_tag,
        "expectancy_label": CURVE_FILTER_LABELS[exp_tag],
        "sample": sample,
        "sample_label": CURVE_FILTER_LABELS[sample],
        "regime_blocks_size_upgrade": trend == TREND_DOWN or dd_tag == DD_ACCEL or sample == SAMPLE_LOW,
    }


def build_curve_metrics(
    *,
    sharpe_wf: float = 0.85,
    max_dd_pct: float = 14.5,
    win_rate: float = 0.48,
    n_trades: int = 42,
    expectancy_r: float = 0.35,
) -> Dict[str, Any]:
    state = resolve_health_state(
        sharpe_wf=sharpe_wf,
        max_dd_pct=max_dd_pct,
        win_rate=win_rate,
        n_trades=n_trades,
    )
    regime = evaluate_regime_filter(
        equity_slope=expectancy_r * 0.05,
        dd_velocity=max_dd_pct / 12.0,
        expectancy_ratio=min(1.2, expectancy_r / 0.4) if expectancy_r else 0.8,
        n_trades=n_trades,
    )
    return {
        "health_state": state,
        "health_label": HEALTH_LABELS.get(state, ""),
        "curve_label": state,
        "regime_filter": regime,
        "metrics": {
            "sharpe_walk_forward": sharpe_wf,
            "max_drawdown_pct": max_dd_pct,
            "win_rate": win_rate,
            "n_trades": n_trades,
            "expectancy_r": expectancy_r,
        },
        "deploy_from_curve_alone": False,
        "backtest_not_live_edge": True,
        "monitor_trigger_type": "strategy_health",
    }


def build_strategy_curve_context(
    ticker: str,
    *,
    strategy_id: str = "momentum_breakout_v2",
    degraded: bool = False,
) -> Dict[str, Any]:
    sym = ticker.upper().strip()
    now = datetime.now(timezone.utc).isoformat()
    curves = [
        {
            "strategy_id": strategy_id,
            "ticker_scope": sym,
            **build_curve_metrics(),
        }
    ]
    body = {
        "ticker": sym,
        "strategies": curves,
        "data_tier": "mock",
        "surface_hint": "btlab",
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_STRATEGY_CURVE,
        source="mock-curve-stub",
        as_of=now,
        degraded=degraded or True,
        extra=body,
    )
