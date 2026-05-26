"""Unified Decision Summary Bar — Layer 1 across Today / Portfolio / Funds / Stock."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def evidence_quality_block(
    *,
    basis: str,
    sample_size: Optional[int] = None,
    freshness: str = "recent",
    source_quality: str = "medium",
    label: Optional[str] = None,
) -> Dict[str, Any]:
    score = 50
    if basis in ("live", "live_ibkr"):
        score += 25
    elif basis == "mixed":
        score += 10
    elif basis in ("backtest", "model_backtest", "training"):
        score -= 15
    if freshness == "stale":
        score -= 20
    if source_quality == "high":
        score += 10
    score = max(0, min(100, score))
    tier = (
        "strong"
        if score >= 70
        else "mixed"
        if score >= 45
        else "weak"
    )
    return {
        "basis": basis,
        "sample_size": sample_size,
        "freshness": freshness,
        "source_quality": source_quality,
        "score": score,
        "tier": tier,
        "label": label or f"{basis} · {tier}",
    }


def build_decision_bar(
    *,
    surface: str,
    verdict: str,
    conviction: int,
    evidence: Dict[str, Any],
    risk_state: str = "Normal",
    next_catalyst: Optional[str] = None,
    time_horizon: str = "swing",
    next_action: Optional[str] = None,
    invalidation: Optional[str] = None,
    why_now: Optional[str] = None,
    why_not: Optional[str] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical decision bar payload."""
    return {
        "surface": surface,
        "verdict": verdict,
        "conviction": max(0, min(100, int(conviction))),
        "evidence_quality": evidence,
        "risk_state": risk_state,
        "next_catalyst": next_catalyst or "—",
        "time_horizon": time_horizon,
        "next_action": next_action or verdict,
        "invalidation": invalidation,
        "why_now": (why_now or "")[:240],
        "why_not": (why_not or "")[:240],
        "as_of": as_of or _now(),
    }


def bar_from_today(
    today: Dict[str, Any],
    decision_strip: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Decision bar for Today / global strip."""
    ba = today.get("best_action") or {}
    regime = today.get("market_regime") or {}
    strip = decision_strip or {}
    deploy = strip.get("deploy_reduce_wait") or "WAIT"
    tradeability = regime.get("tradeability") or "WAIT"
    vix = regime.get("vix")
    breadth = regime.get("breadth")

    verdict = deploy
    if deploy == "DEPLOY":
        verdict = "DEPLOY"
    elif deploy == "REDUCE":
        verdict = "REDUCE"
    else:
        verdict = "WAIT"

    risk = "Normal"
    if vix is not None and float(vix) > 28:
        risk = "Extreme"
    elif vix is not None and float(vix) > 22:
        risk = "Elevated"
    elif tradeability == "NO_TRADE":
        risk = "Elevated"

    idea = strip.get("best_idea_now") or ba.get("best_trade_now")
    catalyst = None
    if idea:
        catalyst = f"Watch {idea.get('ticker')} setup"

    conv = 55
    if idea and idea.get("score"):
        conv = min(95, int(float(idea.get("score", 0)) * 10))
    elif ba.get("capital_stance") == "DEPLOY_SELECTIVE":
        conv = 50

    return build_decision_bar(
        surface="today",
        verdict=verdict,
        conviction=conv,
        evidence=evidence_quality_block(
            basis="live" if today.get("trust", {}).get("freshness") == "REAL_TIME" else "mixed",
            freshness="recent" if today else "warming",
            source_quality="high" if today.get("top_5") else "low",
            label="Today engine · regime + scan",
        ),
        risk_state=risk,
        next_catalyst=catalyst or "Regime / breadth review",
        time_horizon="intraday" if tradeability == "STRONG_TRADE" else "swing",
        next_action=ba.get("capital_stance", "").replace("_", " ") or verdict,
        why_now=ba.get("stance_one_liner") or strip.get("stance_one_liner"),
        why_not=(
            f"Breadth {breadth}% · VIX {vix}"
            if breadth is not None
            else "No deploy-grade ideas in funnel"
        ),
    )


def bar_from_portfolio(
    allocator_summary: Dict[str, Any],
    regime_fit: Dict[str, Any],
    *,
    rebalance_urgency: bool = False,
) -> Dict[str, Any]:
    stance = allocator_summary.get("stance") or "HOLD"
    verdict = stance
    conv = 60 if allocator_summary.get("confidence") == "medium" else 40
    if rebalance_urgency:
        conv += 15
    risk = "Elevated" if stance in ("REDUCE", "PAUSE") else "Normal"
    if not regime_fit.get("aligned_with_regime"):
        risk = "Elevated"
    return build_decision_bar(
        surface="portfolio",
        verdict=verdict,
        conviction=min(95, conv),
        evidence=evidence_quality_block(
            basis=allocator_summary.get("evidence_quality") or "manual",
            sample_size=regime_fit.get("position_count"),
            label="Book + allocation monitor",
        ),
        risk_state=risk,
        next_catalyst="Rebalance review" if rebalance_urgency else "Hold — monitor drift",
        time_horizon="medium",
        next_action=allocator_summary.get("recommended_action"),
        why_now=allocator_summary.get("recommended_action"),
        why_not=regime_fit.get("note"),
    )


def bar_from_funds(
    allocator_decision: Dict[str, Any],
    *,
    active_sleeve: Optional[str] = None,
) -> Dict[str, Any]:
    deploy = allocator_decision.get("deploy_capital") or allocator_decision.get("deploy_posture")
    verdict = "ALLOCATE" if deploy and "cash" not in str(deploy).lower() else "HOLD CASH"
    if allocator_decision.get("reduce_exposure"):
        verdict = "REDUCE"
    return build_decision_bar(
        surface="funds",
        verdict=verdict,
        conviction=int(allocator_decision.get("confidence") or 55),
        evidence=evidence_quality_block(
            basis="model_backtest",
            sample_size=None,
            freshness="recent",
            source_quality="medium",
            label="Fund lab · backtest sleeves",
        ),
        risk_state="Normal",
        next_catalyst=allocator_decision.get("next_rebalance") or "Sleeve gate review",
        time_horizon="medium",
        next_action=allocator_decision.get("marginal_instruction") or deploy,
        why_now=allocator_decision.get("headline"),
        why_not="; ".join(allocator_decision.get("do_not_allocate_now") or [])[:200],
    )


def bar_from_stock(
    *,
    ticker: str,
    unified: Dict[str, Any],
    pm_answer: Dict[str, Any],
    catalysts: Dict[str, Any],
    smart_money: Dict[str, Any],
) -> Dict[str, Any]:
    label = (unified.get("label") or "WATCH").upper()
    verdict_map = {
        "TRADE": "BUY",
        "BUY": "BUY",
        "WATCH": "WATCH",
        "AVOID": "AVOID",
        "NO TRADE": "AVOID",
        "PASS": "AVOID",
    }
    verdict = verdict_map.get(label, "WATCH")
    conf = int(float(unified.get("confidence") or 0) * 100)
    sm_basis = "mixed"
    if smart_money.get("sources"):
        for s in smart_money["sources"]:
            if s.get("signal_quality") == "live":
                sm_basis = "live"
                break
    return build_decision_bar(
        surface="stock",
        verdict=verdict,
        conviction=conf,
        evidence=evidence_quality_block(
            basis=sm_basis,
            freshness="recent",
            source_quality="medium" if unified.get("reason") else "low",
            label=f"{ticker} dossier stack",
        ),
        risk_state="Elevated" if verdict == "AVOID" else "Normal",
        next_catalyst=(catalysts.get("next_label") or "—"),
        time_horizon=pm_answer.get("best_setup_type") or "swing",
        next_action=pm_answer.get("action_now") or verdict,
        invalidation=unified.get("invalidation") or pm_answer.get("thesis_breaks"),
        why_now=pm_answer.get("one_line") or unified.get("reason"),
        why_not=(pm_answer.get("bear_case") or [None])[0]
        if isinstance(pm_answer.get("bear_case"), list)
        else pm_answer.get("thesis_breaks"),
    )


def enrich_curve_diagnostics(card: Dict[str, Any]) -> Dict[str, Any]:
    """Curve block with explicit live/backtest separation."""
    perf = card.get("performance_evidence") or {}
    mode = (card.get("mode") or perf.get("mode") or "training").lower()
    evidence = perf.get("evidence") or "backtest"
    curve = card.get("equity_curve_20") or []
    return {
        "equity_curve_20": curve,
        "curve_basis": evidence,
        "curve_mode": mode,
        "curve_label": perf.get("label")
        or ("Backtest · not live track record" if evidence == "backtest" else mode),
        "live_vs_backtest_gap": None,
        "forward_degradation_flag": False,
        "rolling_sharpe_note": "Wire live sleeve equity for rolling Sharpe",
        "sample": perf.get("sample") or "model_universe_backtest",
    }
