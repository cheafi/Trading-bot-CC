"""
Five-level decision hierarchy — page gate beats card appeal.

Level 1: Page / regime gate
Level 2: Board opportunity quality
Level 3: Setup evidence & thesis
Level 4: Execution & broker readiness
Level 5: Portfolio fit & restraint
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

LEVEL_PAGE_GATE = 1
LEVEL_BOARD_QUALITY = 2
LEVEL_SETUP_EVIDENCE = 3
LEVEL_EXECUTION = 4
LEVEL_PORTFOLIO_RESTRAINT = 5

LEVEL_LABELS: Dict[int, str] = {
    LEVEL_PAGE_GATE: "Page gate",
    LEVEL_BOARD_QUALITY: "Board quality",
    LEVEL_SETUP_EVIDENCE: "Setup evidence",
    LEVEL_EXECUTION: "Execution readiness",
    LEVEL_PORTFOLIO_RESTRAINT: "Portfolio & restraint",
}

LEVEL_AUTHORITY: Dict[int, str] = {
    LEVEL_PAGE_GATE: "Blocks or permits all deploy surfaces",
    LEVEL_BOARD_QUALITY: "Caps how many names earn sizing",
    LEVEL_SETUP_EVIDENCE: "Thesis / timing / R:R — not decorative",
    LEVEL_EXECUTION: "Broker + bracket + fill realism",
    LEVEL_PORTFOLIO_RESTRAINT: "Book fit, turnover, crowding governor",
}


def _level_status(level: int, *, blocked: bool, detail: str) -> Dict[str, Any]:
    return {
        "level": level,
        "label": LEVEL_LABELS[level],
        "authority": LEVEL_AUTHORITY[level],
        "status": "blocked" if blocked else "clear",
        "detail": detail,
    }


def evaluate_decision_hierarchy(
    *,
    should_trade: bool,
    tradeability: str,
    execution_ready_count: int = 0,
    deployable_count: int = 0,
    pilot_ready_count: int = 0,
    ibkr_connected: bool = False,
    bracket_ready: bool = False,
    restraint_blocked: bool = False,
    restraint_detail: str = "",
    macro_regime: Optional[str] = None,
    crisis_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate L1–L5 and return the binding (lowest failing) level.
    Regime and plumbing (《乱世华尔街》) are evaluated before board quality.
    """
    tradeability_u = (tradeability or "").upper()
    levels: List[Dict[str, Any]] = []
    crisis = crisis_bundle or {}

    l1_blocked = not should_trade or tradeability_u in ("NO_TRADE", "WAIT")
    l1_detail = (
        "Regime gate closed — no new risk regardless of card rank"
        if not should_trade
        else f"Board tradeability {tradeability_u} — page gate limits deploy"
    )
    if macro_regime == "Hostile":
        l1_blocked = True
        l1_detail = "Macro hostile — capital preservation overrides isolated setups"
    if crisis.get("deploy_blocked"):
        l1_blocked = True
        l1_detail = crisis.get("headline") or "Crisis regime — preservation overrides setups"
    if crisis.get("plumbing_first") and not crisis.get("counterparty_trust", {}).get(
        "deploy_trusted"
    ):
        l1_blocked = True
        trust_h = (crisis.get("counterparty_trust") or {}).get("headline")
        l1_detail = trust_h or "Broker plumbing not trusted — no new risk"
    levels.append(_level_status(LEVEL_PAGE_GATE, blocked=l1_blocked, detail=l1_detail))

    deploy_n = deployable_count or execution_ready_count
    l2_blocked = deploy_n < 1 and pilot_ready_count < 1
    l2_detail = (
        f"{deploy_n} execution-ready · {pilot_ready_count} pilot-eligible"
        if not l2_blocked
        else "No deploy-grade or pilot-eligible names on today's board"
    )
    levels.append(_level_status(LEVEL_BOARD_QUALITY, blocked=l2_blocked, detail=l2_detail))

    l3_blocked = deploy_n < 1
    l3_detail = (
        "At least one name passes score + thesis + timing + R:R bar"
        if not l3_blocked
        else "Setups lack validated evidence bar — research only"
    )
    levels.append(_level_status(LEVEL_SETUP_EVIDENCE, blocked=l3_blocked, detail=l3_detail))

    l4_blocked = deploy_n >= 1 and (not ibkr_connected or not bracket_ready)
    l4_detail = (
        "IBKR connected · bracket levels present"
        if not l4_blocked and deploy_n >= 1
        else (
            "Confirm IBKR + entry/stop before send"
            if deploy_n >= 1
            else "Execution checks idle — no deploy candidate"
        )
    )
    levels.append(_level_status(LEVEL_EXECUTION, blocked=l4_blocked, detail=l4_detail))

    l5_blocked = restraint_blocked
    l5_detail = restraint_detail or "Restraint governor clear — size to book rules"
    levels.append(
        _level_status(LEVEL_PORTFOLIO_RESTRAINT, blocked=l5_blocked, detail=l5_detail)
    )

    binding = next((lv for lv in levels if lv["status"] == "blocked"), levels[-1])
    can_full_deploy = (
        not l1_blocked
        and deploy_n >= 1
        and not l4_blocked
        and not l5_blocked
        and tradeability_u in ("TRADE", "STRONG_TRADE")
    )
    can_pilot = (
        not l1_blocked
        and (pilot_ready_count >= 1 or deploy_n >= 1)
        and not l5_blocked
    )

    return {
        "levels": levels,
        "binding_level": binding["level"],
        "binding_label": binding["label"],
        "binding_detail": binding["detail"],
        "can_full_deploy": can_full_deploy,
        "can_pilot_only": can_pilot and not can_full_deploy,
        "headline": (
            f"L{binding['level']} {binding['label']}: {binding['detail']}"
        ),
    }


def can_deploy_at_level(hierarchy: Dict[str, Any], min_level: int = LEVEL_EXECUTION) -> bool:
    """True when no blocked level from L1 through min_level."""
    for lv in hierarchy.get("levels") or []:
        level = int(lv.get("level") or 0)
        if level <= min_level and lv.get("status") == "blocked":
            return False
    return True


def hierarchy_for_dashboard(
    *,
    decision_model: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    restraint: Optional[Dict[str, Any]] = None,
    should_trade: bool = True,
    tradeability: str = "WAIT",
    execution_ready_count: int = 0,
    pilot_ready_count: int = 0,
    crisis_bundle: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper for /api/v7/today payload."""
    dm = decision_model or {}
    er = execution_readiness or {}
    rs = restraint or {}
    bundle = crisis_bundle
    if bundle is None and market_regime is not None:
        from src.services.crisis_regime import build_crisis_bundle

        bundle = build_crisis_bundle(
            market_regime=market_regime,
            decision_model=dm,
            execution_readiness=er,
        )
    return evaluate_decision_hierarchy(
        should_trade=should_trade,
        tradeability=dm.get("honest_tradeability") or tradeability,
        execution_ready_count=execution_ready_count,
        deployable_count=execution_ready_count,
        pilot_ready_count=pilot_ready_count,
        ibkr_connected=bool(er.get("ibkr_connected")),
        bracket_ready=bool(er.get("bracket_ready")),
        restraint_blocked=bool(rs.get("restraint_active")),
        restraint_detail=str(rs.get("summary") or ""),
        macro_regime=dm.get("macro_regime"),
        crisis_bundle=bundle,
    )
