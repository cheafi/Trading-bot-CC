"""
Opportunity Baseline Comparison — OI lift vs reference cohorts.

Lift reported only when sample threshold met and horizons align.
authority_effect=none; never authorizes deploy.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence

from src.services.forward_outcome_tracker import HORIZONS_DAYS

BASELINE_NAMES: tuple[str, ...] = (
    "random_liquid",
    "raw_scanner_hits",
    "sector_leaders",
    "previous_playbook_top",
    "equal_weight_watchlist",
    "rejected_names",
    "no_trade_cash",
)

MIN_SAMPLES_LIFT = 12
DEFAULT_HORIZON = 5


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _mean_forward_r(
    rows: Sequence[Dict[str, Any]],
    *,
    horizon: int = DEFAULT_HORIZON,
) -> Optional[float]:
    vals: List[float] = []
    for row in rows:
        h_key = f"forward_r_{horizon}d"
        if row.get(h_key) is not None:
            vals.append(_float(row[h_key]))
        elif row.get("horizon") == horizon and row.get("forward_r") is not None:
            vals.append(_float(row["forward_r"]))
        elif row.get("forward_r") is not None and horizon == DEFAULT_HORIZON:
            vals.append(_float(row["forward_r"]))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 3)


def _cohort_from_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    horizon: int = DEFAULT_HORIZON,
) -> Dict[str, Any]:
    n = len(rows)
    mean_r = _mean_forward_r(rows, horizon=horizon)
    cost_adj_vals = [
        _float(r.get("post_cost_estimate_r") or r.get("cost_adj_r"))
        for r in rows
        if r.get("post_cost_estimate_r") is not None or r.get("cost_adj_r") is not None
    ]
    cost_adj = round(sum(cost_adj_vals) / len(cost_adj_vals), 3) if cost_adj_vals else None
    return {
        "sample_size": n,
        "mean_forward_r": mean_r,
        "cost_adj_expectancy": cost_adj,
        "horizon_days": horizon,
        "learning_mode": n < MIN_SAMPLES_LIFT,
        "display": "learning" if n < MIN_SAMPLES_LIFT else (f"{mean_r:+.2f}R" if mean_r is not None else "insufficient"),
    }


def _random_liquid_cohort(
    liquid_universe: Optional[Sequence[str]] = None,
    *,
    seed: int = 42,
    k: int = 20,
) -> List[Dict[str, Any]]:
    universe = list(liquid_universe or ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "META"])
    rng = random.Random(seed)
    picks = rng.sample(universe, min(k, len(universe)))
    return [{"ticker": t, "forward_r": 0.0, "source": "random_liquid"} for t in picks]


def compare_oi_to_baselines(
    *,
    oi_outcomes: Sequence[Dict[str, Any]],
    forward_summary: Optional[Dict[str, Any]] = None,
    discovery_hits: Optional[Sequence[Dict[str, Any]]] = None,
    playbook_rows: Optional[Sequence[Dict[str, Any]]] = None,
    near_miss_rows: Optional[Sequence[Dict[str, Any]]] = None,
    rejected_rows: Optional[Sequence[Dict[str, Any]]] = None,
    watchlist_rows: Optional[Sequence[Dict[str, Any]]] = None,
    sector_leaders: Optional[Sequence[Dict[str, Any]]] = None,
    previous_playbook_top: Optional[Sequence[Dict[str, Any]]] = None,
    horizon: int = DEFAULT_HORIZON,
    min_sample: int = MIN_SAMPLES_LIFT,
) -> Dict[str, Any]:
    """Compare OI cohort expectancy vs baseline cohorts at same horizon."""
    oi_cohort = _cohort_from_rows(oi_outcomes, horizon=horizon)
    fwd = dict(forward_summary or {})
    baselines: Dict[str, Dict[str, Any]] = {}

    scanner_rows = list(discovery_hits or [])
    baselines["raw_scanner_hits"] = _cohort_from_rows(scanner_rows, horizon=horizon)
    baselines["sector_leaders"] = _cohort_from_rows(sector_leaders or [], horizon=horizon)
    baselines["previous_playbook_top"] = _cohort_from_rows(
        previous_playbook_top or playbook_rows or [], horizon=horizon
    )
    baselines["equal_weight_watchlist"] = _cohort_from_rows(watchlist_rows or [], horizon=horizon)
    baselines["rejected_names"] = _cohort_from_rows(rejected_rows or near_miss_rows or [], horizon=horizon)
    baselines["random_liquid"] = _cohort_from_rows(_random_liquid_cohort(), horizon=horizon)
    baselines["no_trade_cash"] = {
        "sample_size": max(1, int(fwd.get("no_edge_samples") or 1)),
        "mean_forward_r": 0.0,
        "cost_adj_expectancy": 0.0,
        "horizon_days": horizon,
        "learning_mode": False,
        "display": "0.00R",
    }

    oi_mean = oi_cohort.get("mean_forward_r")
    lifts: Dict[str, Any] = {}
    best_baseline = "no_trade_cash"
    best_baseline_r = 0.0
    for name, cohort in baselines.items():
        base_r = cohort.get("mean_forward_r")
        if base_r is not None and base_r > best_baseline_r:
            best_baseline_r = _float(base_r)
            best_baseline = name
        n_ok = (
            oi_cohort["sample_size"] >= min_sample
            and cohort["sample_size"] >= min_sample
            and oi_mean is not None
            and base_r is not None
        )
        if n_ok:
            lift = round(oi_mean - base_r, 3)
            lifts[name] = {
                "lift_r": lift,
                "display": f"{lift:+.2f}R vs {name}",
                "sample_ok": True,
            }
        else:
            lifts[name] = {
                "lift_r": None,
                "display": "learning",
                "sample_ok": False,
            }

    oi_n = oi_cohort["sample_size"]
    primary_lift = lifts.get(best_baseline, {})
    if oi_n >= min_sample and oi_mean is not None and primary_lift.get("lift_r") is not None:
        oi_lift_display = primary_lift["display"]
    else:
        oi_lift_display = "learning"

    return {
        "oi_cohort": oi_cohort,
        "baselines": baselines,
        "lifts": lifts,
        "best_baseline": best_baseline,
        "oi_lift_display": oi_lift_display,
        "horizon_days": horizon,
        "horizons_aligned": horizon in HORIZONS_DAYS,
        "min_sample": min_sample,
        "learning_mode": oi_n < min_sample,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "evidence_only": True,
    }
