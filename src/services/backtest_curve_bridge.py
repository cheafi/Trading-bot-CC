"""Bridge Backtest Lab walk-forward output to strategy curve health metrics."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.signal_provenance import (
    SIGNAL_STRATEGY_CURVE,
    build_provenance_envelope,
)
from src.services.strategy_curve_health import build_curve_metrics


def _normalize_pct(value: Any) -> float:
    if value is None:
        return 0.0
    v = float(value)
    if abs(v) > 1.5:
        return abs(v)
    return abs(v) * 100.0


def _normalize_win_rate(value: Any, trade_review: Dict[str, Any]) -> float:
    if value is None:
        wr = trade_review.get("win_rate")
        if wr is None:
            return 0.0
        v = float(wr)
        return v / 100.0 if v > 1.0 else v
    v = float(value)
    return v / 100.0 if v > 1.0 else v


def curve_metrics_from_lab(
    walk_forward: Dict[str, Any],
    trade_review: Dict[str, Any],
    *,
    strategy_id: str = "lab_best",
    ticker: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Derive curve health from walk-forward windows — research only, not live edge.
    """
    windows = list((walk_forward or {}).get("windows") or [])
    if not windows:
        return None

    usable = [w for w in windows if not w.get("error")]
    if not usable:
        return None

    recent = next(
        (w for w in usable if w.get("window") == "recent"),
        usable[0],
    )
    sharpe_vals = [
        float(w.get("sharpe") or 0)
        for w in usable
        if w.get("sharpe") is not None
    ]
    if sharpe_vals:
        sharpe_wf = sum(sharpe_vals) / len(sharpe_vals)
    else:
        sharpe_wf = float(recent.get("sharpe") or 0)

    dd_vals = [
        _normalize_pct(w.get("max_dd"))
        for w in usable
        if w.get("max_dd") is not None
    ]
    if dd_vals:
        max_dd = max(dd_vals)
    else:
        max_dd = _normalize_pct(recent.get("max_dd"))

    n_trades = int(
        recent.get("trades") or trade_review.get("trade_count") or 0
    )
    win_rate = _normalize_win_rate(recent.get("win_rate"), trade_review)

    ret_vals = [float(w.get("return_pct") or 0) for w in usable]
    expectancy_r = (sum(ret_vals) / len(ret_vals) / 100.0) if ret_vals else 0.0

    metrics = build_curve_metrics(
        sharpe_wf=sharpe_wf,
        max_dd_pct=max_dd,
        win_rate=win_rate,
        n_trades=n_trades,
        expectancy_r=expectancy_r,
    )
    metrics["strategy_id"] = strategy_id
    metrics["ticker_scope"] = ticker.upper().strip()
    metrics["data_source"] = "backtest_lab_walk_forward"
    metrics["degraded"] = n_trades < 5
    return metrics


def build_curve_health_envelope(
    walk_forward: Dict[str, Any],
    trade_review: Dict[str, Any],
    *,
    strategy_id: str = "lab_best",
    ticker: str = "",
) -> Optional[Dict[str, Any]]:
    metrics = curve_metrics_from_lab(
        walk_forward,
        trade_review,
        strategy_id=strategy_id,
        ticker=ticker,
    )
    if not metrics:
        return None
    sym = ticker.upper().strip() or "LAB"
    body = {
        "ticker": sym,
        "strategies": [metrics],
        "data_tier": "backtest_walk_forward",
        "surface_hint": "btlab",
        "deploy_from_curve_alone": False,
        "backtest_not_live_edge": True,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_STRATEGY_CURVE,
        source="backtest-lab-walk-forward",
        degraded=metrics.get("degraded", False) or n_trades_low(metrics),
        extra=body,
    )


def n_trades_low(metrics: Dict[str, Any]) -> bool:
    inner = metrics.get("metrics") or {}
    return int(inner.get("n_trades") or 0) < 20
