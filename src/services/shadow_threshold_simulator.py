"""
Shadow Threshold Simulator — historical what-if simulation for proposals.

Computes would_promote/reject counts, forward_r_delta, false_positive_delta.
Advisory only — no live Playbook changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.services.threshold_registry import get_threshold, is_risk_reducing


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _score_for_row(row: Dict[str, Any]) -> float:
    for key in ("composite_score", "score", "quality_score", "decision_score"):
        v = row.get(key)
        if v is not None:
            return _float(v)
    return 0.0


def _rr_for_row(row: Dict[str, Any]) -> float:
    for key in ("risk_reward", "rr", "reward_risk"):
        v = row.get(key)
        if v is not None:
            return _float(v)
    return 0.0


def _forward_r(row: Dict[str, Any]) -> Optional[float]:
    for key in ("forward_r_5d", "forward_r", "outcome_r"):
        v = row.get(key)
        if v is not None:
            return _float(v)
    return None


def would_pass_threshold(
    row: Dict[str, Any],
    threshold_key: str,
    threshold_value: float,
) -> bool:
    if threshold_key == "playbook.deploy_score_min":
        return _score_for_row(row) >= threshold_value
    if threshold_key == "playbook.deploy_rr_min":
        return _rr_for_row(row) >= threshold_value
    if threshold_key == "playbook.thesis_min":
        return _float(row.get("thesis_confidence")) >= threshold_value
    if threshold_key == "playbook.timing_min":
        return _float(row.get("timing_score", row.get("setup_score"))) >= threshold_value
    if threshold_key == "discovery.strict_filter_min":
        return _score_for_row(row) >= threshold_value
    if threshold_key == "capital.max_position_risk_pct":
        return _float(row.get("position_risk_pct", 0)) <= threshold_value
    if threshold_key == "capital.cash_floor":
        return _float(row.get("cash_pct", 1)) >= threshold_value
    if threshold_key == "opportunity.max_cost_drag_r":
        return _float(row.get("cost_drag_r", 0)) <= threshold_value
    if threshold_key == "alpha.max_overfit_risk":
        return _float(row.get("overfit_risk_score", 0)) <= threshold_value
    if threshold_key == "governor.false_deploy_rate_max":
        return _float(row.get("false_deploy_rate", 0)) <= threshold_value
    return _score_for_row(row) >= threshold_value


def simulate_threshold_change(
    *,
    threshold_key: str,
    current_value: float,
    proposed_value: float,
    historical_rows: Sequence[Dict[str, Any]],
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Historical simulation: compare current vs proposed threshold on past rows.
    """
    rows = list(historical_rows or [])
    outcomes = {str(o.get("ticker") or o.get("symbol") or i): o for i, o in enumerate(forward_outcomes or [])}

    would_promote = 0
    would_reject = 0
    unchanged = 0
    forward_r_current: List[float] = []
    forward_r_proposed: List[float] = []
    false_positive_current = 0
    false_positive_proposed = 0
    false_positive_delta = 0

    for i, row in enumerate(rows):
        cur_pass = would_pass_threshold(row, threshold_key, current_value)
        prop_pass = would_pass_threshold(row, threshold_key, proposed_value)

        if cur_pass and not prop_pass:
            would_reject += 1
        elif not cur_pass and prop_pass:
            would_promote += 1
        else:
            unchanged += 1

        ticker = str(row.get("ticker") or row.get("symbol") or i)
        outcome = outcomes.get(ticker) or row
        fr = _forward_r(outcome)
        if fr is not None:
            if cur_pass:
                forward_r_current.append(fr)
                if fr < 0:
                    false_positive_current += 1
            if prop_pass:
                forward_r_proposed.append(fr)
                if fr < 0:
                    false_positive_proposed += 1

    n = len(rows)
    avg_current = sum(forward_r_current) / len(forward_r_current) if forward_r_current else 0.0
    avg_proposed = sum(forward_r_proposed) / len(forward_r_proposed) if forward_r_proposed else 0.0
    forward_r_delta = round(avg_proposed - avg_current, 4)
    false_positive_delta = false_positive_proposed - false_positive_current

    risk_reducing = is_risk_reducing(threshold_key, proposed_value, current_value=current_value)
    recommendation = _recommendation(
        would_promote=would_promote,
        would_reject=would_reject,
        forward_r_delta=forward_r_delta,
        false_positive_delta=false_positive_delta,
        risk_reducing=risk_reducing,
        n=n,
    )

    return {
        "threshold_key": threshold_key,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "sample_size": n,
        "would_promote": would_promote,
        "would_reject": would_reject,
        "unchanged": unchanged,
        "forward_r_delta": forward_r_delta,
        "false_positive_delta": false_positive_delta,
        "avg_forward_r_current": round(avg_current, 4),
        "avg_forward_r_proposed": round(avg_proposed, 4),
        "risk_reducing": risk_reducing,
        "recommendation": recommendation,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
    }


def _recommendation(
    *,
    would_promote: int,
    would_reject: int,
    forward_r_delta: float,
    false_positive_delta: int,
    risk_reducing: bool,
    n: int,
) -> str:
    if n < 5:
        return "collect_more_samples"
    if not risk_reducing:
        return "reject_loosen"
    if false_positive_delta < 0 and forward_r_delta >= 0:
        return "approve_shadow"
    if false_positive_delta <= 0 and forward_r_delta > 0:
        return "approve_shadow"
    if would_reject > would_promote and false_positive_delta <= 0:
        return "approve_shadow"
    if false_positive_delta > 2:
        return "defer"
    if forward_r_delta < -0.1:
        return "reject"
    return "defer"


def simulate_proposal(
    proposal: Dict[str, Any],
    *,
    historical_rows: Sequence[Dict[str, Any]],
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run simulation for a single governance proposal."""
    key = str(proposal.get("threshold_key") or "")
    current = _float(proposal.get("current_value"))
    proposed = proposal.get("proposed_value")
    if proposed is None:
        defn = get_threshold(key)
        return {
            "threshold_key": key,
            "recommendation": "collect_more_samples",
            "authority_effect": "none",
            "may_authorize_deploy": False,
            "no_live_changes": True,
        }
    result = simulate_threshold_change(
        threshold_key=key,
        current_value=current,
        proposed_value=_float(proposed),
        historical_rows=historical_rows,
        forward_outcomes=forward_outcomes,
    )
    result["proposal_id"] = proposal.get("proposal_id")
    result["proposal_type"] = proposal.get("proposal_type")
    return result


def batch_simulate_proposals(
    proposals: Sequence[Dict[str, Any]],
    *,
    historical_rows: Sequence[Dict[str, Any]],
    forward_outcomes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Simulate all open/shadow proposals."""
    results = [
        simulate_proposal(p, historical_rows=historical_rows, forward_outcomes=forward_outcomes)
        for p in proposals
        if p.get("proposed_value") is not None
    ]
    approve = sum(1 for r in results if r.get("recommendation") == "approve_shadow")
    defer = sum(1 for r in results if r.get("recommendation") == "defer")
    reject = sum(1 for r in results if r.get("recommendation") in ("reject", "reject_loosen"))
    return {
        "simulations": results,
        "count": len(results),
        "approve_shadow_count": approve,
        "defer_count": defer,
        "reject_count": reject,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
    }
