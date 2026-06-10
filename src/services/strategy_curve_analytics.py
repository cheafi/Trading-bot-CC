"""
Strategy curve analytics — time-series health from an actual equity/trade series.

strategy_curve_health.py classifies health from scalar inputs (sharpe, dd, win
rate). This module adds the *series* analytics a Strategy Curve Console needs and
that nothing else computes:

  - rolling Sharpe (windowed)            - drawdown duration (underwater length)
  - rolling / current / max drawdown     - drawdown acceleration
  - expectancy trend, hit-rate trend     - turnover / cost & execution drag
  - live-vs-backtest divergence          - stale-to-live (calibration age)
  - strategy decay score (0-100)         - sample-depth badge
  - curve_state: full_size/reduced/pilot_only/paused

It reuses resolve_health_state() for the discrete state and the Wave-3
execution-drag overlay for the execution-cost dimension — no duplication.

Authority: research_only. Curve health NEVER authorizes deploy or upgrades
sizing — it is Backtest-Lab / Funds research and a monitor-only Dashboard hint.
Pure-Python (statistics only), deterministic, clock-free: calibration age is
passed in as days, never read from the wall clock.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_STRATEGY_CURVE,
    build_provenance_envelope,
)
from src.services.strategy_curve_health import (
    HEALTH_PAUSED,
    HEALTH_PILOT,
    HEALTH_REDUCED,
    resolve_health_state,
)

# Curve states (align names with the brief; map onto strategy_curve_health states).
CURVE_FULL_SIZE = "full_size"
CURVE_REDUCED = "reduced"
CURVE_PILOT_ONLY = "pilot_only"
CURVE_PAUSED = "paused"

CALIB_FRESH = "fresh"
CALIB_AGING = "aging"
CALIB_STALE = "stale"

SAMPLE_THIN = "thin"
SAMPLE_MODERATE = "moderate"
SAMPLE_ROBUST = "robust"

_PERIODS_PER_YEAR = 252  # daily series default


# ---------------------------------------------------------------------------
# Series primitives
# ---------------------------------------------------------------------------
def returns_from_equity(equity: List[float]) -> List[float]:
    """Simple period returns from an equity curve."""
    out: List[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev:
            out.append(equity[i] / prev - 1.0)
    return out


def sharpe(returns: List[float], periods_per_year: int = _PERIODS_PER_YEAR) -> Optional[float]:
    """Annualized Sharpe of a return series. None if undefined."""
    if len(returns) < 2:
        return None
    mean = statistics.fmean(returns)
    sd = statistics.pstdev(returns)
    if sd == 0:
        return None
    return round(mean / sd * math.sqrt(periods_per_year), 2)


def rolling_sharpe(
    returns: List[float], window: int = 20, periods_per_year: int = _PERIODS_PER_YEAR
) -> Dict[str, Any]:
    """Rolling Sharpe series + latest value + first-vs-last trend label."""
    if len(returns) < window:
        s = sharpe(returns, periods_per_year)
        return {"window": window, "series": [], "latest": s, "trend": "insufficient_sample"}
    series: List[float] = []
    for i in range(window, len(returns) + 1):
        s = sharpe(returns[i - window:i], periods_per_year)
        if s is not None:
            series.append(s)
    if not series:
        return {"window": window, "series": [], "latest": None, "trend": "insufficient_sample"}
    trend = "stable"
    if len(series) >= 2:
        if series[-1] < series[0] - 0.3:
            trend = "deteriorating"
        elif series[-1] > series[0] + 0.3:
            trend = "improving"
    return {"window": window, "series": [round(x, 2) for x in series], "latest": series[-1], "trend": trend}


def drawdown_profile(equity: List[float]) -> Dict[str, Any]:
    """Current/max drawdown, underwater durations, and drawdown acceleration."""
    if len(equity) < 2:
        return {
            "current_dd_pct": None, "max_dd_pct": None,
            "current_underwater_len": 0, "max_underwater_len": 0,
            "dd_accelerating": False, "degraded": True,
        }
    peak = equity[0]
    dd_series: List[float] = []
    max_dd = 0.0
    cur_uw = 0
    max_uw = 0
    for v in equity:
        if v > peak:
            peak = v
            cur_uw = 0
        else:
            cur_uw += 1
            max_uw = max(max_uw, cur_uw)
        dd = (v / peak - 1.0) * 100.0 if peak else 0.0
        dd_series.append(dd)
        max_dd = min(max_dd, dd)
    # Acceleration: recent worsening velocity vs earlier in the underwater stretch.
    accel = False
    if len(dd_series) >= 6:
        recent = dd_series[-3] - dd_series[-1]   # how much deeper in last 2 steps
        prior = dd_series[-6] - dd_series[-4]
        accel = recent > max(0.0, prior) and recent > 0.5
    return {
        "current_dd_pct": round(dd_series[-1], 2),
        "max_dd_pct": round(abs(max_dd), 2),
        "current_underwater_len": cur_uw,
        "max_underwater_len": max_uw,
        "dd_accelerating": accel,
        "degraded": False,
    }


def _half_trend(values: List[float], better: str = "higher") -> Dict[str, Any]:
    """Generic first-half vs second-half trend on a numeric series."""
    clean = [v for v in values if v is not None]
    if len(clean) < 4:
        return {"trend": "insufficient_sample", "n": len(clean)}
    mid = len(clean) // 2
    early = statistics.fmean(clean[:mid])
    late = statistics.fmean(clean[mid:])
    delta = late - early
    eps = (abs(early) * 0.1) or 0.05
    if abs(delta) <= eps:
        label = "stable"
    elif (delta > 0) == (better == "higher"):
        label = "improving"
    else:
        label = "decaying"
    return {"trend": label, "early": round(early, 3), "late": round(late, 3), "n": len(clean)}


def expectancy_trend(r_multiples: List[float]) -> Dict[str, Any]:
    return _half_trend(r_multiples, better="higher")


def hit_rate_trend(win_flags: List[bool]) -> Dict[str, Any]:
    return _half_trend([1.0 if w else 0.0 for w in win_flags], better="higher")


# ---------------------------------------------------------------------------
# Divergence / calibration / decay
# ---------------------------------------------------------------------------
def live_vs_backtest_divergence(
    live_expectancy_r: Optional[float], backtest_expectancy_r: Optional[float]
) -> Dict[str, Any]:
    """Ratio of live to backtest expectancy + an honest label."""
    if not backtest_expectancy_r or live_expectancy_r is None:
        return {"ratio": None, "label": "Divergence unknown — no live sample", "degraded": True}
    ratio = round(live_expectancy_r / backtest_expectancy_r, 2)
    if ratio < 0.5:
        label = "Live edge far below backtest — decay / overfit risk"
    elif ratio < 0.8:
        label = "Live edge below backtest — reduce template in research"
    elif ratio <= 1.2:
        label = "Live tracks backtest — within tolerance"
    else:
        label = "Live above backtest — small sample, do not extrapolate"
    return {"ratio": ratio, "label": label, "degraded": False}


def calibration_status(days_since_calibration: Optional[int]) -> Dict[str, Any]:
    if days_since_calibration is None:
        return {"badge": CALIB_STALE, "days": None, "label": "Calibration age unknown — treat as stale"}
    d = int(days_since_calibration)
    if d <= 30:
        badge = CALIB_FRESH
    elif d <= 90:
        badge = CALIB_AGING
    else:
        badge = CALIB_STALE
    return {"badge": badge, "days": d, "label": f"Calibrated {d}d ago — {badge}"}


def sample_depth_badge(n_trades: int) -> str:
    if n_trades < 20:
        return SAMPLE_THIN
    if n_trades < 60:
        return SAMPLE_MODERATE
    return SAMPLE_ROBUST


def strategy_decay_score(
    *,
    rolling_sharpe_trend: str,
    dd_accelerating: bool,
    expectancy_trend_label: str,
    divergence_ratio: Optional[float],
    calibration_badge: str,
    execution_drag_bps: Optional[float],
) -> Dict[str, Any]:
    """Composite 0-100 decay score (higher = more decay). Componentized & honest."""
    comp: Dict[str, float] = {}
    comp["rolling_sharpe"] = 25.0 if rolling_sharpe_trend == "deteriorating" else 0.0
    comp["drawdown"] = 20.0 if dd_accelerating else 0.0
    comp["expectancy"] = 20.0 if expectancy_trend_label == "decaying" else 0.0
    if divergence_ratio is not None:
        comp["live_vs_backtest"] = round(min(20.0, max(0.0, (1.0 - divergence_ratio) * 25.0)), 1)
    comp["calibration"] = {CALIB_FRESH: 0.0, CALIB_AGING: 5.0, CALIB_STALE: 10.0}.get(calibration_badge, 10.0)
    if execution_drag_bps is not None:
        comp["execution_drag"] = round(min(15.0, max(0.0, execution_drag_bps / 2.0)), 1)
    score = round(min(100.0, sum(comp.values())), 1)
    if score >= 55:
        band = "high_decay"
    elif score >= 30:
        band = "moderate_decay"
    else:
        band = "low_decay"
    return {"score": score, "band": band, "components": comp}


def resolve_curve_state(
    *, sharpe_wf: float, max_dd_pct: float, win_rate: float, n_trades: int, decay_band: str
) -> str:
    """Discrete curve state, with decay as a downgrade-only override."""
    base = resolve_health_state(
        sharpe_wf=sharpe_wf, max_dd_pct=max_dd_pct, win_rate=win_rate, n_trades=n_trades
    )
    mapping = {
        "full_size": CURVE_FULL_SIZE,
        HEALTH_REDUCED: CURVE_REDUCED,
        HEALTH_PILOT: CURVE_PILOT_ONLY,
        "monitor": CURVE_PILOT_ONLY,
        HEALTH_PAUSED: CURVE_PAUSED,
    }
    state = mapping.get(base, CURVE_PILOT_ONLY)
    # Decay can only downgrade, never upgrade.
    if decay_band == "high_decay" and state in (CURVE_FULL_SIZE, CURVE_REDUCED):
        state = CURVE_PILOT_ONLY
    return state


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------
def build_strategy_curve_analytics(
    *,
    strategy_id: str = "momentum_breakout_v2",
    equity_curve: Optional[List[float]] = None,
    r_multiples: Optional[List[float]] = None,
    win_flags: Optional[List[bool]] = None,
    live_expectancy_r: Optional[float] = None,
    backtest_expectancy_r: Optional[float] = None,
    days_since_calibration: Optional[int] = None,
    execution_drag_bps: Optional[float] = None,
    window: int = 20,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Full time-series curve analytics, wrapped in research-only provenance."""
    equity = equity_curve or []
    rets = returns_from_equity(equity)
    roll = rolling_sharpe(rets, window=window)
    dd = drawdown_profile(equity)
    exp_t = expectancy_trend(r_multiples or [])
    hit_t = hit_rate_trend(win_flags or [])
    div = live_vs_backtest_divergence(live_expectancy_r, backtest_expectancy_r)
    calib = calibration_status(days_since_calibration)
    n_trades = len(r_multiples or [])
    depth = sample_depth_badge(n_trades)
    decay = strategy_decay_score(
        rolling_sharpe_trend=roll["trend"],
        dd_accelerating=dd["dd_accelerating"],
        expectancy_trend_label=exp_t["trend"],
        divergence_ratio=div["ratio"],
        calibration_badge=calib["badge"],
        execution_drag_bps=execution_drag_bps,
    )
    overall_sharpe = sharpe(rets) or 0.0
    win_rate = (sum(1 for w in (win_flags or []) if w) / n_trades) if n_trades else 0.0
    state = resolve_curve_state(
        sharpe_wf=overall_sharpe,
        max_dd_pct=dd.get("max_dd_pct") or 0.0,
        win_rate=win_rate,
        n_trades=n_trades,
        decay_band=decay["band"],
    )
    is_degraded = degraded or not equity or n_trades < 4 or div["degraded"]
    body = {
        "strategy_id": strategy_id,
        "curve_state": state,
        "rolling_sharpe": roll,
        "overall_sharpe": overall_sharpe,
        "drawdown": dd,
        "expectancy_trend": exp_t,
        "hit_rate_trend": hit_t,
        "live_vs_backtest": div,
        "calibration": calib,
        "sample_depth": depth,
        "n_trades": n_trades,
        "decay": decay,
        "execution_drag_bps": execution_drag_bps,
        "deploy_from_curve_alone": False,
        "backtest_not_live_edge": True,
        "surface_hint": "btlab",
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_STRATEGY_CURVE,
        source="strategy_curve_analytics" if equity else "strategy_curve_analytics-empty",
        degraded=is_degraded,
        data_mode="research_only",
        extra=body,
    )
