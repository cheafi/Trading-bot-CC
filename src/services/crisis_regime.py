"""
《乱世华尔街》crisis / hostile-regime mode — survival over hero trades.

Capital preservation, liquidity, funding, and correlation spikes; deploy authority
withdrawn when plumbing or regime fails first.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Granular crisis states (book: calm → fragile → stress → cascade → rescue → stabilization)
CRISIS_STATES: List[str] = [
    "calm",
    "fragile",
    "liquidity_stress",
    "funding_stress",
    "cascade",
    "rescue",
    "stabilization",
]

CRISIS_LABELS: Dict[str, str] = {
    "hostile_regime": "hostile regime — preservation overrides setups",
    "liquidity_stress": "liquidity stress — size down or flat",
    "funding_stress": "funding stress — margin and carry dominate",
    "correlation_spike": "correlation spike — book is one bet",
    "vol_crisis": "volatility crisis — no new risk",
    "cascade": "cascade risk — de-gross before heroes",
    "rescue": "rescue / policy bid — confirmation only",
    "stabilization": "stabilization — rebuild slowly",
    "calm_enough": "stress easing — confirmation only",
    "cash_is_position": "cash is the position",
}

LEVEL_MAP: Dict[str, str] = {
    "calm": "normal",
    "fragile": "elevated",
    "liquidity_stress": "elevated",
    "funding_stress": "elevated",
    "cascade": "crisis",
    "rescue": "elevated",
    "stabilization": "elevated",
}


def classify_crisis_state(
    *,
    tradeability: str = "",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    macro_regime: Optional[str] = None,
    should_trade: bool = True,
    prior_state: Optional[str] = None,
) -> str:
    """Map market inputs to a single crisis state."""
    tb = (tradeability or "").upper()
    vix_f = float(vix) if vix is not None else 0.0
    breadth_f = float(breadth) if breadth is not None else 50.0
    hostile = (macro_regime or "").lower() in ("hostile", "crisis", "risk_off")

    if vix_f >= 35 or tb == "NO_TRADE" or (hostile and not should_trade):
        return "cascade"
    if vix_f >= 30:
        return "funding_stress"
    if vix_f >= 26 or breadth_f < 32:
        return "liquidity_stress"
    if vix_f >= 22 or breadth_f < 38 or hostile:
        return "fragile"
    if prior_state in ("cascade", "funding_stress", "liquidity_stress") and vix_f < 20:
        return "stabilization"
    if prior_state in ("cascade", "funding_stress") and 20 <= vix_f < 24:
        return "rescue"
    return "calm"


def evaluate_crisis_regime(
    *,
    tradeability: str = "",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    macro_regime: Optional[str] = None,
    should_trade: bool = True,
    entropy: Optional[float] = None,
    prior_state: Optional[str] = None,
) -> Dict[str, Any]:
    """Crisis evaluation — regime/plumbing before card appeal."""
    (tradeability or "").upper()
    vix_f = float(vix) if vix is not None else 0.0
    breadth_f = float(breadth) if breadth is not None else 50.0
    hostile = (macro_regime or "").lower() in ("hostile", "crisis", "risk_off")

    state = classify_crisis_state(
        tradeability=tradeability,
        vix=vix_f,
        breadth=breadth_f,
        macro_regime=macro_regime,
        should_trade=should_trade,
        prior_state=prior_state,
    )
    level = LEVEL_MAP.get(state, "normal")

    labels: List[str] = []
    if state == "cascade":
        labels.extend(
            [
                CRISIS_LABELS["vol_crisis"],
                CRISIS_LABELS["cascade"],
                CRISIS_LABELS["cash_is_position"],
            ]
        )
    elif state == "funding_stress":
        labels.append(CRISIS_LABELS["funding_stress"])
    elif state == "liquidity_stress":
        labels.append(CRISIS_LABELS["liquidity_stress"])
    elif state == "fragile":
        labels.append(CRISIS_LABELS["liquidity_stress"])
    elif state == "rescue":
        labels.append(CRISIS_LABELS["rescue"])
    elif state == "stabilization":
        labels.append(CRISIS_LABELS["stabilization"])
    else:
        labels.append(CRISIS_LABELS["calm_enough"])

    if hostile or not should_trade:
        level = "crisis"
        labels.append(CRISIS_LABELS["hostile_regime"])
        if CRISIS_LABELS["cash_is_position"] not in labels:
            labels.append(CRISIS_LABELS["cash_is_position"])
    elif vix_f >= 24 or breadth_f < 35:
        labels.append(CRISIS_LABELS["correlation_spike"])

    deploy_blocked = (
        level == "crisis" or state in ("cascade", "funding_stress") or hostile
    )
    preservation = deploy_blocked or state in (
        "liquidity_stress",
        "funding_stress",
        "fragile",
        "cascade",
    )
    posture = (
        "preservation"
        if preservation
        else ("selective_attack" if level == "normal" else "balanced")
    )

    return {
        "mode": "luanshi_wallstreet",
        "state": state,
        "level": level,
        "labels": labels,
        "deploy_blocked": deploy_blocked,
        "headline": labels[0] if labels else CRISIS_LABELS["calm_enough"],
        "banner": (
            "乱世模式 · Capital preservation — no new hero trades"
            if preservation
            else "Stress monitor — confirmation only"
        ),
        "authority": "blocked"
        if deploy_blocked
        else ("confirmation_only" if preservation else "normal"),
        "posture": posture,
        "capital_preservation_priority": preservation,
        "attack_permission": not deploy_blocked and posture == "selective_attack",
        "model_note": "VIX/breadth/tradeability heuristics — not macro forecast",
    }


def build_crisis_bundle(
    *,
    market_regime: Optional[Dict[str, Any]] = None,
    decision_model: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate regime + liquidity + trust + survival for dashboard/portfolio."""
    mr = market_regime or {}
    dm = decision_model or {}
    er = execution_readiness or {}

    regime = evaluate_crisis_regime(
        tradeability=dm.get("honest_tradeability") or mr.get("tradeability") or "",
        vix=mr.get("vix"),
        breadth=mr.get("breadth"),
        macro_regime=dm.get("macro_regime"),
        should_trade=bool(mr.get("should_trade", True)),
        entropy=mr.get("entropy"),
    )

    from src.services.counterparty_trust import evaluate_counterparty_trust
    from src.services.crisis_portfolio_survival import (
        evaluate_crisis_portfolio_survival,
    )
    from src.services.liquidity_funding_stress import evaluate_liquidity_funding_stress

    liquidity = evaluate_liquidity_funding_stress(
        vix=mr.get("vix"),
        breadth=mr.get("breadth"),
        tradeability=mr.get("tradeability") or "",
        entropy=mr.get("entropy"),
    )
    trust = evaluate_counterparty_trust(
        ibkr_health=er.get("health") or {},
        ibkr_connected=bool(er.get("ibkr_connected")),
        bracket_ready=bool(er.get("bracket_ready")),
        circuit_breaker=bool(er.get("circuit_breaker")),
    )
    survival = evaluate_crisis_portfolio_survival(
        positions=positions,
        vix=mr.get("vix"),
        breadth=mr.get("breadth"),
        deploy_blocked=regime.get("deploy_blocked"),
        heat_pct=(mr.get("heat_pct")),
    )

    plumbing_ok = trust.get("deploy_trusted") and not regime.get("deploy_blocked")
    return {
        **regime,
        "liquidity": liquidity,
        "liquidity_state": liquidity.get("liquidity_state"),
        "counterparty_trust": trust,
        "crisis_survival": survival,
        "plumbing_first": not plumbing_ok
        or regime.get("capital_preservation_priority"),
        "regime_fit": _crisis_regime_fit_score(regime, liquidity),
    }


def _crisis_regime_fit_score(regime: Dict[str, Any], liquidity: Dict[str, Any]) -> int:
    base = int(liquidity.get("score") or 50)
    if regime.get("deploy_blocked"):
        return min(base, 25)
    if regime.get("state") == "fragile":
        return min(base, 45)
    return min(100, base)


def tags_for_playbook_row(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    market_vix: Optional[float] = None,
) -> Dict[str, Any]:
    """Playbook enrich fields — survival-first."""
    tb = tradeability or str(
        row.get("tradeability") or row.get("honest_tradeability") or ""
    )
    ev = evaluate_crisis_regime(
        tradeability=tb,
        vix=row.get("vix") or market_vix,
        macro_regime=row.get("macro_regime"),
        should_trade=bool(row.get("should_trade", True)),
    )
    from src.services.dislocation_opportunity import dislocation_for_row

    disloc = dislocation_for_row(row, market_vix=market_vix)
    fit = _crisis_regime_fit_score(ev, {"score": 50})
    preservation = ev.get("capital_preservation_priority") or not disloc.get(
        "attack_allowed"
    )
    attack = (
        ev.get("attack_permission")
        and disloc.get("attack_allowed")
        and not ev.get("deploy_blocked")
    )

    return {
        "regime_fit": fit,
        "attack_permission": attack,
        "capital_preservation_priority": preservation,
        "crisis_hint": ev.get("headline"),
        "crisis_state": ev.get("state"),
        "dislocation_kind": disloc.get("kind"),
    }


def build_crisis_context(
    *,
    ticker: str,
    regime: Any,
    dossier: Optional[Dict[str, Any]] = None,
    unified: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dossier block — regime-aware summary and liquidity exposure."""
    dossier = dossier or {}
    unified = unified or {}
    should_trade = getattr(regime, "should_trade", True)
    if isinstance(regime, dict):
        should_trade = bool(regime.get("should_trade", True))
    vix = (
        getattr(regime, "vix", None)
        if not isinstance(regime, dict)
        else regime.get("vix")
    )
    chg = dossier.get("change_pct")

    ev = evaluate_crisis_regime(should_trade=should_trade, vix=vix)
    from src.services.dislocation_opportunity import classify_dislocation
    from src.services.liquidity_funding_stress import evaluate_liquidity_funding_stress

    disloc = classify_dislocation(vix=vix, change_pct=chg, should_trade=should_trade)
    liq = evaluate_liquidity_funding_stress(vix=vix)

    summary = (
        f"{ticker}: {ev.get('headline')} · {liq.get('headline')}"
        if ticker
        else f"{ev.get('headline')} · {liq.get('headline')}"
    )
    return {
        "mode": "luanshi_wallstreet",
        "summary": summary,
        "state": ev.get("state"),
        "posture": ev.get("posture"),
        "liquidity_exposure": liq.get("liquidity_state"),
        "dislocation": disloc.get("kind"),
        "capital_preservation_priority": ev.get("capital_preservation_priority"),
        "attack_permission": ev.get("attack_permission")
        and disloc.get("attack_allowed"),
        "deploy_blocked": ev.get("deploy_blocked"),
        "labels": ev.get("labels") or [],
    }


def crisis_strip_for_today(
    market_regime: Dict[str, Any],
    decision_model: Dict[str, Any],
    *,
    execution_readiness: Optional[Dict[str, Any]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Dashboard crisis strip on /api/v7/today."""
    bundle = build_crisis_bundle(
        market_regime=market_regime,
        decision_model=decision_model,
        execution_readiness=execution_readiness,
        positions=positions,
    )
    preservation = bundle.get("posture") == "preservation"
    return {
        **bundle,
        "regime_state": bundle.get("state"),
        "liquidity_state": bundle.get("liquidity_state"),
        "preservation_vs_attack": "preservation"
        if preservation
        else bundle.get("posture", "balanced"),
        "strip_headline": bundle.get("banner") or bundle.get("headline"),
    }
