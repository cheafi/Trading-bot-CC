"""
Capital Allocation Governor — decide when capital should remain idle.

Capital mode cannot override page authority. Broker offline => no_capital or
paper_only. Manual/demo book => no_capital.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

CAPITAL_MODES: tuple[str, ...] = (
    "no_capital",
    "repair_only",
    "monitor_only",
    "paper_only",
    "pilot_review",
    "selective_deploy",
    "normal_deploy",
    "de_risk",
)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def evaluate_capital_allocation(
    *,
    truth: Optional[Dict[str, Any]] = None,
    opportunity_quality: Optional[Dict[str, Any]] = None,
    portfolio_context: Optional[Dict[str, Any]] = None,
    drawdown_pct: Optional[float] = None,
    dd_budget_pct: float = 15.0,
    open_r: float = 0.0,
    sector_concentration: float = 0.0,
    correlation_cluster: float = 0.0,
    false_deploy_rate: float = 0.0,
    recent_error_rate: float = 0.0,
    no_edge_quality: Optional[str] = None,
    signal_confidence: Optional[str] = None,
    vix: Optional[float] = None,
    sample_size: int = 0,
    alpha_quality_status: Optional[str] = None,
    false_positive_rate: float = 0.0,
    overfit_risk: Optional[str] = None,
    missed_opportunity_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate capital mode and risk limits — advisory only, cannot override authority.
    """
    t = dict(truth or {})
    pf = dict(portfolio_context or {})
    oq = dict(opportunity_quality or {})
    er = t.get("execution_readiness") or {}
    broker_connected = bool(er.get("broker_connected"))
    handoff_ready = bool(er.get("trade_handoff_ready"))
    manual_book = bool(pf.get("local_only") or pf.get("manual_only") or t.get("portfolio_local_only"))
    deploy_authority = bool(t.get("deploy_authority"))
    deploy_n = int(t.get("deploy_qualified_count") or 0)
    dd = _float(drawdown_pct, _float(t.get("equity_dd_pct")))
    reasons: List[str] = []
    learning_reasons: List[str] = []
    qa_reason_codes: List[str] = []
    risk_mode_adjustment: Optional[str] = None
    qa_adjustment: Optional[str] = None
    requires_human_review = False
    human_review_suggested = False
    mode = "monitor_only"

    if manual_book:
        mode = "no_capital"
        reasons.append("MANUAL_DEMO_BOOK")
    elif not broker_connected:
        mode = "paper_only" if deploy_authority else "no_capital"
        reasons.append("BROKER_OFFLINE")
    elif dd >= dd_budget_pct:
        mode = "de_risk"
        reasons.append("DRAWDOWN_BREACH")
    elif not deploy_authority or deploy_n < 1:
        mode = "monitor_only"
        reasons.append("NO_EDGE_TODAY")
    elif str(t.get("runtime_state") or "").lower() in ("degraded", "critical"):
        mode = "repair_only"
        reasons.append("RUNTIME_DEGRADED")
    elif false_deploy_rate > 0.25:
        mode = "pilot_review"
        reasons.append("HIGH_FALSE_DEPLOY_RATE")
    elif correlation_cluster > 0.65 or sector_concentration > 0.45:
        mode = "selective_deploy"
        reasons.append("CONCENTRATION_CLUSTER")
    elif deploy_authority and handoff_ready and deploy_n >= 1:
        mode = "normal_deploy" if dd < dd_budget_pct * 0.5 else "selective_deploy"
    else:
        mode = "paper_only"
        reasons.append("HANDOFF_NOT_READY")

    max_new_risk = 0.5
    max_position_risk = 0.25
    gross_limit = 1.0
    if mode == "no_capital":
        max_new_risk = 0.0
        max_position_risk = 0.0
        gross_limit = 0.0
    elif mode == "de_risk":
        max_new_risk = 0.15
        max_position_risk = 0.1
        gross_limit = 0.6
    elif mode in ("monitor_only", "repair_only"):
        max_new_risk = 0.0
        max_position_risk = 0.0
    elif mode == "paper_only":
        max_new_risk = 0.1
        max_position_risk = 0.05
    elif mode == "pilot_review":
        max_new_risk = 0.2
        max_position_risk = 0.1
    elif mode == "selective_deploy":
        max_new_risk = 0.35
        max_position_risk = 0.15

    if sample_size < 8:
        max_new_risk = min(max_new_risk, 0.2)
        reasons.append("LOW_SAMPLE_SIZE")
        learning_reasons.append("LOW_SAMPLE_SIZE")
    if false_deploy_rate > 0.15:
        max_new_risk = min(max_new_risk, 0.25)
        learning_reasons.append("FALSE_DEPLOY_ELEVATED")
        risk_mode_adjustment = "tighten"
    if false_deploy_rate > 0.25:
        risk_mode_adjustment = "tighten"
        learning_reasons.append("HIGH_FALSE_DEPLOY_RATE")
    if recent_error_rate > 0.2:
        max_new_risk = min(max_new_risk, 0.2)
        learning_reasons.append("RECENT_ERROR_ELEVATED")
        risk_mode_adjustment = "tighten"
    neq = str(no_edge_quality or "").lower()
    if neq == "too_conservative":
        requires_human_review = True
        learning_reasons.append("NO_EDGE_TOO_CONSERVATIVE")
    elif neq == "noisy":
        learning_reasons.append("NO_EDGE_NOISY")
    elif neq == "good_avoidance":
        learning_reasons.append("NO_EDGE_GOOD_AVOIDANCE")
    sig_conf = str(signal_confidence or "").lower()
    if sig_conf == "insufficient":
        max_new_risk = min(max_new_risk, 0.2)
        learning_reasons.append("SIGNAL_CONFIDENCE_LOW")
    elif sig_conf == "harmful":
        max_new_risk = min(max_new_risk, 0.15)
        risk_mode_adjustment = "tighten"
        learning_reasons.append("SIGNAL_FAMILY_HARMFUL")
        requires_human_review = True
    if correlation_cluster > 0.5:
        max_new_risk = min(max_new_risk, 0.3)
    if vix is not None and float(vix) > 28:
        max_new_risk = min(max_new_risk, 0.25)
        reasons.append("VOL_ELEVATED")
    if open_r > 3.0:
        max_new_risk = min(max_new_risk, 0.2)
        reasons.append("OPEN_R_ELEVATED")

    fp_rate = false_positive_rate if false_positive_rate > 0 else false_deploy_rate
    aq_status = str(alpha_quality_status or "").lower()
    of_risk = str(overfit_risk or "").lower()
    missed = dict(missed_opportunity_review or {})

    if aq_status in ("noisy", "deteriorating"):
        max_new_risk = min(max_new_risk, 0.2)
        qa_adjustment = "tighten"
        qa_reason_codes.append(f"ALPHA_QA_{aq_status.upper()}")
        learning_reasons.append(f"ALPHA_QA_{aq_status.upper()}")
    elif aq_status == "insufficient_data":
        max_new_risk = min(max_new_risk, 0.25)
        qa_reason_codes.append("ALPHA_QA_INSUFFICIENT_DATA")
        learning_reasons.append("ALPHA_QA_INSUFFICIENT_DATA")
    if fp_rate > 0.2:
        max_new_risk = min(max_new_risk, 0.2)
        qa_adjustment = "tighten"
        qa_reason_codes.append("QA_FALSE_POSITIVE_ELEVATED")
        learning_reasons.append("QA_FALSE_POSITIVE_ELEVATED")
    if of_risk == "high":
        max_new_risk = min(max_new_risk, 0.15)
        qa_adjustment = "tighten"
        qa_reason_codes.append("QA_OVERFIT_HIGH")
        learning_reasons.append("QA_OVERFIT_HIGH")
        human_review_suggested = True
    elif of_risk == "medium":
        max_new_risk = min(max_new_risk, 0.25)
        qa_reason_codes.append("QA_OVERFIT_MEDIUM")
        learning_reasons.append("QA_OVERFIT_MEDIUM")
    if missed.get("too_conservative_count", 0) > 0:
        human_review_suggested = True
        qa_reason_codes.append("QA_MISSED_OPPORTUNITY_REVIEW")
        learning_reasons.append("QA_MISSED_OPPORTUNITY_REVIEW")
    if human_review_suggested:
        requires_human_review = True

    cash_floor = 0.15 if mode in ("selective_deploy", "pilot_review") else 0.25
    if mode in ("no_capital", "monitor_only", "repair_only"):
        cash_floor = 1.0

    deploy_allowed = deploy_authority and mode in (
        "selective_deploy",
        "normal_deploy",
        "pilot_review",
        "paper_only",
    )
    sizing_allowed = deploy_allowed and mode not in ("monitor_only", "repair_only", "no_capital")

    repair = str(t.get("primary_blocker") or "Restore broker + board + deploy path")
    if mode == "de_risk":
        repair = "Reduce open risk — drawdown budget breached"
    elif mode == "no_capital":
        repair = "Connect broker or sync live book before sizing"

    learning_adjustment_reason = (
        "; ".join(learning_reasons[:4]) if learning_reasons else None
    )

    return {
        "capital_mode": mode,
        "max_new_risk_pct": round(max_new_risk, 2),
        "max_position_risk_pct": round(max_position_risk, 2),
        "gross_exposure_limit": round(gross_limit, 2),
        "sector_limit": round(0.35 if sector_concentration > 0.35 else 0.5, 2),
        "correlation_limit": round(0.5 if correlation_cluster > 0.5 else 0.65, 2),
        "cash_floor": round(cash_floor, 2),
        "deploy_allowed": deploy_allowed,
        "sizing_allowed": sizing_allowed,
        "reason_codes": reasons[:6],
        "next_repair_action": repair,
        "cannot_override_authority": True,
        "may_authorize_deploy": False,
        "authority_note": "Capital governor is advisory — page authority gates deploy",
        "cash_valid": mode in ("monitor_only", "repair_only", "no_capital") or deploy_n < 1,
        "learning_adjustment_reason": learning_adjustment_reason,
        "risk_mode_adjustment": risk_mode_adjustment,
        "requires_human_review": requires_human_review,
        "learning_feedback": {
            "false_deploy_rate": round(false_deploy_rate, 3) if false_deploy_rate else None,
            "no_edge_quality": no_edge_quality,
            "signal_confidence": signal_confidence,
            "sample_size": sample_size,
            "never_auto_loosen": True,
        },
        "qa_adjustment": qa_adjustment,
        "qa_reason_codes": qa_reason_codes[:6],
        "human_review_suggested": human_review_suggested,
        "can_loosen_automatically": False,
        "alpha_quality_status": alpha_quality_status,
        "overfit_risk": overfit_risk,
        "false_positive_rate": round(fp_rate, 3) if fp_rate else None,
    }
