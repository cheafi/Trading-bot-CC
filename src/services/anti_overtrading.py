"""
Anti-overtrading restraint governor — board WAIT, deployable count, turnover proxy.

Cash is valid; churn without edge is penalized at L5 portfolio restraint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_MAX_DAILY_DEPLOYS = 2
_TURNOVER_WARN = 0.45


def evaluate_restraint(
    *,
    tradeability: str,
    deployable_count: int = 0,
    pilot_count: int = 0,
    recent_trade_count_5d: int = 0,
    board_wait: bool = False,
    weak_net_edge: bool = False,
) -> Dict[str, Any]:
    """
    Return restraint state for decision hierarchy L5 and dashboard copy.
    """
    tb = (tradeability or "").upper()
    reasons: List[str] = []
    restraint_active = False
    posture = "normal"

    if board_wait or tb in ("WAIT", "NO_TRADE"):
        restraint_active = True
        posture = "patience"
        reasons.append("Board WAIT/NO_TRADE — default action is no new risk")

    if deployable_count < 1 and pilot_count < 1:
        restraint_active = True
        posture = "patience"
        reasons.append(
            "Zero deploy-grade names — overtrading would be discretionary churn"
        )

    if recent_trade_count_5d >= _MAX_DAILY_DEPLOYS * 3:
        restraint_active = True
        posture = "cooldown"
        reasons.append(
            f"{recent_trade_count_5d} trades in 5d — cooldown before adding size"
        )

    if weak_net_edge and deployable_count >= 1:
        posture = "size_down"
        reasons.append("Net edge after cost is weak — full size not justified")

    turnover_burden = min(1.0, 0.15 + recent_trade_count_5d * 0.08)
    if turnover_burden >= _TURNOVER_WARN:
        reasons.append(f"Turnover burden elevated ({turnover_burden:.0%})")

    # 0–100 restraint score — higher = more reason to stand down
    score = 0
    if board_wait or tb in ("WAIT", "NO_TRADE"):
        score += 35
    if deployable_count < 1 and pilot_count < 1:
        score += 30
    if recent_trade_count_5d >= _MAX_DAILY_DEPLOYS * 3:
        score += 20
    if weak_net_edge:
        score += 10
    score += int(min(15, turnover_burden * 20))
    restraint_score = min(100, score)

    summary = (
        " · ".join(reasons) if reasons else "Restraint clear — size within book rules"
    )

    return {
        "restraint_active": restraint_active,
        "restraint_score": restraint_score,
        "restraint_high": restraint_score >= 55,
        "posture": posture,
        "reasons": reasons,
        "summary": summary,
        "turnover_burden": round(turnover_burden, 2),
        "cash_valid": restraint_active or deployable_count < 1,
        "headline": (
            "Restraint is correct today"
            if restraint_active
            else "Restraint governor clear"
        ),
        "banner": (
            "Restraint is correct today — patience is the active decision."
            if restraint_active
            else None
        ),
        "guidance": (
            "Cash is a valid allocation — do not force trades when board lacks edge."
            if restraint_active
            else "Deploy only names that pass full hierarchy; avoid reactive churn."
        ),
    }


def restraint_from_today_context(
    *,
    tradeability: str,
    deployable_count: int,
    pilot_ready_count: int = 0,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    recent_trade_count_5d: int = 0,
) -> Dict[str, Any]:
    """Wrapper for /api/v7/today."""
    opps = opportunities or []
    weak_net = any(bool(r.get("weak_edge_after_cost")) for r in opps[:5])
    tb = (tradeability or "").upper()
    return evaluate_restraint(
        tradeability=tradeability,
        deployable_count=deployable_count,
        pilot_count=pilot_ready_count,
        recent_trade_count_5d=recent_trade_count_5d,
        board_wait=tb in ("WAIT", "NO_TRADE"),
        weak_net_edge=weak_net,
    )
