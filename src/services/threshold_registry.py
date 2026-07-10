"""
Threshold Registry — SSOT for governed threshold definitions.

All thresholds: can_auto_loosen=False globally.
can_auto_tighten only when risk-reducing; deploy/capital require human approval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

THRESHOLD_DOMAINS: Tuple[str, ...] = (
    "playbook",
    "opportunity",
    "alpha",
    "capital",
    "discovery",
    "strategy",
    "governor",
)

RISK_DIRECTIONS: Tuple[str, ...] = (
    "higher_is_stricter",
    "lower_is_stricter",
)


@dataclass(frozen=True)
class ThresholdDefinition:
    key: str
    domain: str
    current_value: float
    value_type: str = "float"
    description: str = ""
    unit: str = ""
    can_auto_loosen: bool = False
    can_auto_tighten: bool = False
    requires_human_approval: bool = False
    risk_direction: str = "higher_is_stricter"
    rollback_value: Optional[float] = None
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["can_auto_loosen"] = False
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        return d


def _def(
    key: str,
    domain: str,
    current_value: float,
    *,
    value_type: str = "float",
    description: str = "",
    unit: str = "",
    can_auto_tighten: bool = False,
    requires_human_approval: bool = False,
    risk_direction: str = "higher_is_stricter",
    rollback_value: Optional[float] = None,
) -> ThresholdDefinition:
    return ThresholdDefinition(
        key=key,
        domain=domain,
        current_value=current_value,
        value_type=value_type,
        description=description,
        unit=unit,
        can_auto_loosen=False,
        can_auto_tighten=can_auto_tighten,
        requires_human_approval=requires_human_approval,
        risk_direction=risk_direction,
        rollback_value=rollback_value if rollback_value is not None else current_value,
    )


# SSOT registry — values are live defaults; changes require governance workflow.
THRESHOLD_REGISTRY: Dict[str, ThresholdDefinition] = {
    "playbook.deploy_score_min": _def(
        "playbook.deploy_score_min",
        "playbook",
        72.0,
        description="Minimum composite score for deploy-tier playbook row",
        unit="score",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="higher_is_stricter",
    ),
    "playbook.deploy_rr_min": _def(
        "playbook.deploy_rr_min",
        "playbook",
        2.5,
        description="Minimum reward-to-risk for deploy-tier playbook row",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="higher_is_stricter",
    ),
    "playbook.thesis_min": _def(
        "playbook.thesis_min",
        "playbook",
        0.55,
        description="Minimum thesis confidence for deploy consideration",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="higher_is_stricter",
    ),
    "playbook.timing_min": _def(
        "playbook.timing_min",
        "playbook",
        0.45,
        description="Minimum timing/setup score for deploy consideration",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="higher_is_stricter",
    ),
    "opportunity.min_sample": _def(
        "opportunity.min_sample",
        "opportunity",
        12.0,
        value_type="int",
        description="Minimum forward outcomes before opportunity lift labels",
        unit="samples",
        can_auto_tighten=False,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "opportunity.min_sample_successful": _def(
        "opportunity.min_sample_successful",
        "opportunity",
        8.0,
        value_type="int",
        description="Minimum successful outcomes before opportunity success labels",
        unit="samples",
        can_auto_tighten=False,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "opportunity.max_cost_drag_r": _def(
        "opportunity.max_cost_drag_r",
        "opportunity",
        0.35,
        description="Maximum tolerated cost/slippage drag in R units",
        unit="r",
        can_auto_tighten=True,
        requires_human_approval=False,
        risk_direction="lower_is_stricter",
    ),
    "alpha.min_sample_lift": _def(
        "alpha.min_sample_lift",
        "alpha",
        12.0,
        value_type="int",
        description="Minimum samples before alpha lift vs baseline is labeled",
        unit="samples",
        can_auto_tighten=False,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "alpha.min_sample_learning": _def(
        "alpha.min_sample_learning",
        "alpha",
        5.0,
        value_type="int",
        description="Minimum samples before alpha exits pure learning mode",
        unit="samples",
        can_auto_tighten=False,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "alpha.max_overfit_risk": _def(
        "alpha.max_overfit_risk",
        "alpha",
        0.55,
        description="Maximum tolerated overfit risk score before tightening gates",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=False,
        risk_direction="lower_is_stricter",
    ),
    "capital.max_position_risk_pct": _def(
        "capital.max_position_risk_pct",
        "capital",
        1.5,
        description="Maximum per-position risk budget as % of equity",
        unit="pct",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="lower_is_stricter",
    ),
    "capital.cash_floor": _def(
        "capital.cash_floor",
        "capital",
        0.15,
        description="Minimum cash reserve floor as fraction of equity",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="higher_is_stricter",
    ),
    "discovery.strict_filter_min": _def(
        "discovery.strict_filter_min",
        "discovery",
        65.0,
        description="Minimum scanner score for strict discovery filter",
        unit="score",
        can_auto_tighten=True,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "strategy.validation_min_sample": _def(
        "strategy.validation_min_sample",
        "strategy",
        30.0,
        value_type="int",
        description="Minimum out-of-sample trades before strategy validation label",
        unit="samples",
        can_auto_tighten=False,
        requires_human_approval=False,
        risk_direction="higher_is_stricter",
    ),
    "governor.false_deploy_rate_max": _def(
        "governor.false_deploy_rate_max",
        "governor",
        0.35,
        description="Maximum tolerated false-deploy rate before governor tightens",
        unit="ratio",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="lower_is_stricter",
    ),
    "governor.dd_budget_pct": _def(
        "governor.dd_budget_pct",
        "governor",
        15.0,
        description="Drawdown budget before capital de-risk mode",
        unit="pct",
        can_auto_tighten=True,
        requires_human_approval=True,
        risk_direction="lower_is_stricter",
    ),
}


def get_threshold(key: str) -> Optional[ThresholdDefinition]:
    return THRESHOLD_REGISTRY.get(key)


def list_thresholds(*, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = []
    for defn in THRESHOLD_REGISTRY.values():
        if domain and defn.domain != domain:
            continue
        rows.append(defn.to_dict())
    return sorted(rows, key=lambda r: r["key"])


def registry_summary() -> Dict[str, Any]:
    deploy_capital = [
        k
        for k, d in THRESHOLD_REGISTRY.items()
        if d.requires_human_approval
    ]
    auto_tighten = [
        k for k, d in THRESHOLD_REGISTRY.items() if d.can_auto_tighten
    ]
    return {
        "total_thresholds": len(THRESHOLD_REGISTRY),
        "domains": list(THRESHOLD_DOMAINS),
        "can_auto_loosen_globally": False,
        "human_approval_required": deploy_capital,
        "auto_tighten_eligible": auto_tighten,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "collapsed": True,
    }


def is_risk_reducing(
    key: str,
    proposed_value: float,
    *,
    current_value: Optional[float] = None,
) -> bool:
    """True when proposed value is stricter (risk-reducing) vs current."""
    defn = get_threshold(key)
    if not defn:
        return False
    cur = current_value if current_value is not None else defn.current_value
    if defn.risk_direction == "higher_is_stricter":
        return proposed_value > cur
    return proposed_value < cur


def validate_proposed_value(
    key: str,
    proposed_value: float,
    *,
    proposal_type: str = "tighten",
) -> Tuple[bool, str]:
    """Validate a proposed threshold change against registry policy."""
    defn = get_threshold(key)
    if not defn:
        return False, f"unknown threshold: {key}"
    if proposal_type == "loosen_review":
        return True, "loosen_review requires human approval; never auto-applied"
    if proposal_type in ("tighten", "retire_threshold"):
        if not is_risk_reducing(key, proposed_value):
            return False, "tighten must be risk-reducing"
        return True, "ok"
    if proposal_type in ("collect_more_samples", "no_change"):
        return True, "ok"
    return False, f"unsupported proposal type: {proposal_type}"
