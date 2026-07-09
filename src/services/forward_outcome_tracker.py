"""
Forward Outcome Tracker — forward outcome study for watch/blocked/deploy names.

Reference levels are structure references only unless a real/paper trade existed.
Label all outputs as "forward outcome study" — not trade results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

HORIZONS_DAYS: tuple[int, ...] = (1, 3, 5, 10, 20)
STUDY_LABEL = "forward outcome study"


@dataclass
class ForwardOutcome:
    ticker: str
    event_id: str
    event_timestamp: str
    horizon: int
    forward_return_pct: Optional[float] = None
    forward_r: Optional[float] = None
    max_favorable_excursion_r: Optional[float] = None
    max_adverse_excursion_r: Optional[float] = None
    hit_reference_target: Optional[bool] = None
    breached_reference_stop: Optional[bool] = None
    upgraded_to_deploy: bool = False
    downgraded_to_rejected: bool = False
    remained_watch: bool = True
    opportunity_missed: bool = False
    avoided_loss: bool = False
    post_cost_estimate_r: Optional[float] = None
    study_label: str = STUDY_LABEL
    is_trade_result: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["label"] = STUDY_LABEL
        d["not_trade_result"] = not self.is_trade_result
        return d


def _risk_per_share(entry: float, stop: float) -> float:
    if entry <= 0 or stop <= 0:
        return 0.0
    return abs(entry - stop)


def _return_pct(entry: float, future: float) -> float:
    if entry <= 0:
        return 0.0
    return round((future / entry - 1.0) * 100.0, 2)


def _forward_r(entry: float, stop: float, future: float) -> Optional[float]:
    risk = _risk_per_share(entry, stop)
    if risk <= 0:
        return None
    return round((future - entry) / risk, 2)


def compute_forward_outcome(
    *,
    ticker: str,
    event_id: str,
    event_timestamp: str,
    horizon: int,
    entry_ref: Optional[float] = None,
    stop_ref: Optional[float] = None,
    target_ref: Optional[float] = None,
    future_price: Optional[float] = None,
    price_path: Optional[Sequence[float]] = None,
    event_type: str = "WATCH_CANDIDATE",
    cost_bps: float = 15.0,
    had_real_trade: bool = False,
) -> ForwardOutcome:
    """Compute one horizon outcome — study unless had_real_trade."""
    entry = float(entry_ref or 0)
    stop = float(stop_ref or 0)
    target = float(target_ref or 0)
    future = float(future_price) if future_price is not None else None
    path = list(price_path or [])

    fwd_ret: Optional[float] = None
    fwd_r: Optional[float] = None
    mfe_r: Optional[float] = None
    mae_r: Optional[float] = None
    hit_target: Optional[bool] = None
    hit_stop: Optional[bool] = None

    if entry > 0 and future is not None:
        fwd_ret = _return_pct(entry, future)
        fwd_r = _forward_r(entry, stop, future)
        if stop > 0:
            hit_stop = future <= stop if entry > stop else future >= stop
        if target > 0:
            hit_target = future >= target if target > entry else future <= target

    if entry > 0 and stop > 0 and path:
        risk = _risk_per_share(entry, stop)
        if risk > 0:
            favorable = max((p - entry) / risk for p in path)
            adverse = min((p - entry) / risk for p in path)
            mfe_r = round(favorable, 2)
            mae_r = round(adverse, 2)
            if hit_stop is None:
                hit_stop = adverse <= -1.0
            if hit_target is None and target > 0:
                rr_target = abs(target - entry) / risk
                hit_target = favorable >= rr_target

    post_cost_r: Optional[float] = None
    if fwd_r is not None:
        cost_r = (cost_bps / 10000.0) * entry / max(_risk_per_share(entry, stop), entry * 0.01)
        post_cost_r = round(fwd_r - cost_r, 2)

    blocked = event_type in ("BOARD_BLOCKED", "NO_EDGE_TODAY", "AUTHORITY_GUARDRAIL_BLOCKED")
    avoided = blocked and fwd_r is not None and fwd_r < 0
    missed = event_type in ("WATCH_CANDIDATE", "NEAR_MISS") and fwd_r is not None and fwd_r > 1.0

    return ForwardOutcome(
        ticker=str(ticker or "").upper(),
        event_id=event_id,
        event_timestamp=event_timestamp,
        horizon=int(horizon),
        forward_return_pct=fwd_ret,
        forward_r=fwd_r,
        max_favorable_excursion_r=mfe_r,
        max_adverse_excursion_r=mae_r,
        hit_reference_target=hit_target,
        breached_reference_stop=hit_stop,
        remained_watch=event_type in ("WATCH_CANDIDATE", "NEAR_MISS"),
        opportunity_missed=missed,
        avoided_loss=avoided,
        post_cost_estimate_r=post_cost_r,
        is_trade_result=had_real_trade,
    )


def build_forward_outcome_study(
    event: Dict[str, Any],
    *,
    price_series: Optional[Dict[int, float]] = None,
    had_real_trade: bool = False,
) -> List[Dict[str, Any]]:
    """
    Build forward outcome study across horizons for one journal event.
    price_series maps horizon days → price at that horizon (optional).
    """
    series = dict(price_series or {})
    entry = event.get("entry_ref")
    stop = event.get("stop_ref")
    target = event.get("target_ref")
    out: List[Dict[str, Any]] = []
    for h in HORIZONS_DAYS:
        outcome = compute_forward_outcome(
            ticker=str(event.get("ticker") or ""),
            event_id=str(event.get("event_id") or ""),
            event_timestamp=str(event.get("timestamp") or ""),
            horizon=h,
            entry_ref=float(entry) if entry is not None else None,
            stop_ref=float(stop) if stop is not None else None,
            target_ref=float(target) if target is not None else None,
            future_price=series.get(h),
            event_type=str(event.get("event_type") or "WATCH_CANDIDATE"),
            had_real_trade=had_real_trade,
        )
        out.append(outcome.to_dict())
    return out


def summarize_forward_outcomes(
    studies: List[List[Dict[str, Any]]],
    *,
    window: int = 20,
) -> Dict[str, Any]:
    """Aggregate forward outcome studies — no fake precision when n low."""
    flat: List[Dict[str, Any]] = []
    for study in studies or []:
        flat.extend(study or [])
    flat = flat[-window * len(HORIZONS_DAYS) :]
    with_r = [s for s in flat if s.get("forward_r") is not None]
    n = len(with_r)
    avoided = sum(1 for s in flat if s.get("avoided_loss"))
    missed = sum(1 for s in flat if s.get("opportunity_missed"))
    deploy_studies = [s for s in with_r if s.get("horizon") == 5]
    avg_r: Optional[float] = None
    if deploy_studies:
        avg_r = round(
            sum(float(s["forward_r"]) for s in deploy_studies) / len(deploy_studies), 2
        )
    learning = n < 5
    return {
        "label": STUDY_LABEL,
        "sample_size": n,
        "horizons": list(HORIZONS_DAYS),
        "avg_forward_r_5d": avg_r if n >= 5 else None,
        "avoided_loss_count": avoided,
        "opportunity_missed_count": missed,
        "watch_to_deploy_conversion": None,
        "false_deploy_rate": None,
        "learning_mode": learning,
        "insufficient_evidence": n < 5,
        "display_note": (
            "Learning mode — not enough live forward outcomes for calibration"
            if learning
            else f"Forward outcome study · n={n}"
        ),
        "may_authorize_deploy": False,
    }


def build_no_edge_outcome_tracking(
    *,
    truth: Optional[Dict[str, Any]] = None,
    market_forward: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """Track no-edge day quality — measurable only with sample."""
    t = dict(truth or {})
    series = dict(market_forward or {})
    outcomes = []
    for h in (1, 3, 5):
        px = series.get(h)
        outcomes.append(
            {
                "horizon": h,
                "market_forward_return_pct": round(px, 2) if px is not None else None,
                "label": STUDY_LABEL,
            }
        )
    n = sum(1 for o in outcomes if o.get("market_forward_return_pct") is not None)
    return {
        "no_edge_day": True,
        "market_outcomes": outcomes,
        "top_rejected_forward_r": None,
        "avoided_drawdown": None,
        "missed_opportunity": None,
        "reason_accuracy": None,
        "quality_label": "learning" if n < 3 else "insufficient_history",
        "sample_size": n,
        "label": STUDY_LABEL,
        "primary_blocker": str(t.get("primary_blocker") or ""),
    }
