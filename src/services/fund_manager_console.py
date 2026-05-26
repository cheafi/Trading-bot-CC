"""Fund Manager Console — allocator / PM / CRO operating layer on model sleeves."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

# Sleeve risk governance (CRO-visible)
_SLEEVE_RISK: Dict[str, Dict[str, Any]] = {
    "LEADER_MOMENTUM": {
        "max_dd_budget_pct": 15,
        "stop_framework": "Trailing 20d low · 1R sizing",
        "rebalance_cadence": "Weekly",
        "concentration_cap": "Top-5 names · semis cluster watch",
    },
    "BALANCED_MULTI": {
        "max_dd_budget_pct": 12,
        "stop_framework": "ATR-based per factor leg",
        "rebalance_cadence": "Bi-weekly",
        "concentration_cap": "Sector bucket ≤35%",
    },
    "TACTICAL_DEF": {
        "max_dd_budget_pct": 8,
        "stop_framework": "Hard -5% sleeve drawdown guard",
        "rebalance_cadence": "Monthly",
        "concentration_cap": "Defensive sectors only",
    },
}

_REASON_CODES: Dict[str, str] = {
    "PAUSED": "REGIME_FIT_LOW",
    "REDUCED": "REGIME_MIXED",
    "ACTIVE": "REGIME_ALIGNED",
    "NO_DATA": "DATA_UNAVAILABLE",
}


def _regime_fit_explanation(model_id: str, regime_fit: int, regime: str) -> str:
    regime_n = (regime or "unknown").strip().upper()
    if regime_fit >= 80:
        return (
            f"Regime fit {regime_fit}% — {regime_n} supports this sleeve; "
            "eligible for active allocation."
        )
    if regime_fit >= 50:
        return (
            f"Regime fit {regime_fit}% — {regime_n} is mixed; "
            "run at REDUCED size until breadth/VIX improve."
        )
    return (
        f"Regime fit {regime_fit}% — {regime_n} does not support mandate; "
        "PAUSED until trend/participation align."
    )


def _status_reason(card: Dict[str, Any], regime: str) -> str:
    gs = (card.get("gate_status") or "").upper()
    fit = int(card.get("regime_fit") or 0)
    if gs == "NO_DATA":
        return "No fund-lab data — check market data pipeline."
    if gs == "PAUSED":
        return (
            f"Paused: regime fit {fit}% too low for "
            f"{card.get('display_name', 'sleeve')} in {(regime or 'current').upper()}."
        )
    if gs == "REDUCED":
        return (
            f"Reduced: fit {fit}% — defensive/tactical overlay preferred; "
            "size down vs full mandate."
        )
    if gs == "ACTIVE":
        if card.get("controls_capital"):
            return "Active: controls capital today — highest regime fit among sleeves."
        return f"Active: fit {fit}% — deployable at mandate risk budget."
    return "Status unknown — refresh fund lab."


def _next_trigger(card: Dict[str, Any], regime: str) -> str:
    gs = (card.get("gate_status") or "").upper()
    fit = int(card.get("regime_fit") or 0)
    if gs == "ACTIVE":
        return "Monitor rebalance adds/exits; maintain 1R discipline on entries."
    if gs == "REDUCED":
        return f"Upgrade to full ACTIVE if regime fit rises above 80% (now {fit}%)."
    if gs == "PAUSED":
        aff = card.get("regime_affinity") or []
        return (
            f"Reactivate when regime matches {', '.join(aff[:2])} "
            f"and fit > 50% (now {fit}%)."
        )
    return "Load fund lab data to set triggers."


def _target_allocation(card: Dict[str, Any]) -> List[Dict[str, Any]]:
    holdings = card.get("holdings") or []
    if not holdings:
        return []
    total_w = sum(float(h.get("weight") or 0) for h in holdings) or 1.0
    return [
        {
            "ticker": h.get("ticker"),
            "weight_pct": round(float(h.get("weight") or 0) / total_w * 100, 1),
        }
        for h in holdings[:8]
    ]


def _last_change_summary(card: Dict[str, Any]) -> Dict[str, Any]:
    adds = card.get("adds") or []
    exits = card.get("exits") or []
    reduces = card.get("reduces") or []
    parts: List[str] = []
    if adds:
        parts.append(f"Added {', '.join(adds[:3])}")
    if exits:
        parts.append(f"Exited {', '.join(exits[:3])}")
    if reduces:
        parts.append(f"Reduced {', '.join(reduces[:3])}")
    return {
        "date": date.today().isoformat(),
        "summary": " · ".join(parts) if parts else "No position changes vs prior snapshot",
        "adds": adds,
        "exits": exits,
        "reduces": reduces,
    }


def decompose_regime_fit(
    card: Dict[str, Any], regime: str = "unknown"
) -> Dict[str, Any]:
    """Explain regime fit — institutional decomposition (heuristic)."""
    fit = int(card.get("regime_fit") or 0)
    model_id = card.get("id") or ""
    regime_u = (regime or "unknown").upper()
    bull = any(k in regime_u for k in ("BULL", "UP", "TREND"))
    bear = any(k in regime_u for k in ("BEAR", "DOWN", "RISK_OFF"))
    choppy = any(k in regime_u for k in ("CHOP", "SIDE", "WAIT"))

    if model_id == "LEADER_MOMENTUM":
        trend = 95 if bull else 20 if bear else 45
        vol = 70 if not bear else 25
        breadth = 75 if bull else 30
    elif model_id == "TACTICAL_DEF":
        trend = 55 if bull else 90 if bear else 70
        vol = 85
        breadth = 80
    else:
        trend = 70 if bull else 50 if choppy else 40
        vol = 65
        breadth = 60 if bull else 45

    liquidity = 80
    correlation = 70 if model_id != "LEADER_MOMENTUM" else 55
    components = {
        "trend_fit": trend,
        "volatility_fit": vol,
        "breadth_fit": breadth,
        "liquidity_fit": liquidity,
        "correlation_fit": correlation,
    }
    composite = round(sum(components.values()) / len(components))
    return {
        "composite": fit or composite,
        "components": components,
        "formula_note": "Heuristic blend — calibrate vs live regime router",
    }


def build_manager_box(card: Dict[str, Any], regime: str = "") -> Dict[str, Any]:
    """Per-sleeve fund manager operating mini-console."""
    gs = (card.get("gate_status") or "NO_DATA").upper()
    deploy_pct = (
        100.0
        if gs == "ACTIVE"
        else 40.0
        if gs == "REDUCED"
        else 0.0
        if gs == "PAUSED"
        else 0.0
    )
    cash_pct = round(100.0 - deploy_pct, 0)
    conviction = (
        "HIGH"
        if int(card.get("regime_fit") or 0) >= 80
        else "MEDIUM"
        if int(card.get("regime_fit") or 0) >= 50
        else "LOW"
    )
    return {
        "manager_state": card.get("stance") or "NEUTRAL",
        "capital_deployed_pct": deploy_pct,
        "idle_cash_pct": cash_pct,
        "hedge_pct": 10.0 if card.get("id") == "TACTICAL_DEF" and gs != "PAUSED" else 0.0,
        "conviction": conviction,
        "reason_code": _REASON_CODES.get(gs, "UNKNOWN"),
        "last_decision": {
            "date": (card.get("last_rebalance") or {}).get("date") or date.today().isoformat(),
            "action": gs,
            "summary": (card.get("last_rebalance") or {}).get("summary", "No change logged"),
        },
        "decision_reason": card.get("status_reason", ""),
        "next_trigger": card.get("next_trigger", ""),
        "next_action": (
            "ADD"
            if gs == "REDUCED"
            else "HOLD"
            if gs == "ACTIVE"
            else "WATCH"
        ),
        "override_condition": (
            "Breadth >50% + VIX <22 → reconsider PAUSED sleeves"
            if gs == "PAUSED"
            else "VIX >28 or regime RISK_OFF → cut to REDUCED/OFF"
        ),
        "expected_if_regime_up": f"Fit rises → {card.get('display_name')} moves toward ACTIVE",
        "expected_if_regime_down": "Cut deploy % · favor Tactical defensive sleeve",
    }


def build_performance_evidence(
    card: Dict[str, Any],
    *,
    period: str = "1y",
    benchmark_return_pct: float = 0.0,
) -> Dict[str, Any]:
    """Trust stack for KPIs — live/paper/backtest labels."""
    fr = float(card.get("fund_return_pct") or 0)
    ex = float(card.get("excess_return_pct") or 0)
    bm = float(card.get("benchmark_return_pct") or benchmark_return_pct or 0)
    return {
        "evidence": "backtest",
        "mode": card.get("mode") or "training",
        "sample": "model_universe_backtest",
        "period": period,
        "cost_basis": "gross_ex_fees",
        "since": "rolling_backtest_window",
        "benchmark_same_period": True,
        "benchmark_return_pct": bm,
        "fund_return_pct": fr,
        "excess_return_pct": ex,
        "formula": "excess = fund_total_return − SPY_total_return (same window)",
        "transaction_costs": "not_included",
        "slippage": "not_included",
        "label": "Backtest · 1y · gross · not live track record",
        "trust_tier": "research_only",
    }


def build_holdings_overlap(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-sleeve concentration / overlap warnings."""
    ticker_map: Dict[str, List[str]] = {}
    for c in cards:
        name = c.get("display_name") or c.get("id") or "?"
        for h in c.get("holdings") or []:
            t = (h.get("ticker") or "").upper()
            if t:
                ticker_map.setdefault(t, []).append(name)
    overlaps = [
        {"ticker": t, "sleeves": names, "severity": "high" if len(names) >= 2 else "low"}
        for t, names in ticker_map.items()
        if len(names) >= 2
    ]
    overlaps.sort(key=lambda x: -len(x["sleeves"]))
    return {
        "overlapping_tickers": overlaps[:8],
        "warning": (
            f"{len(overlaps)} ticker(s) appear in multiple sleeves — check factor stacking"
            if overlaps
            else "No direct ticker overlap across sleeves"
        ),
        "factor_note": "Sector/factor overlap not fully modeled — review semis/tech cluster",
    }


def build_risk_governance(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """CRO strip — per-sleeve risk budget."""
    rows: List[Dict[str, Any]] = []
    for c in cards:
        sid = c.get("id") or ""
        meta = _SLEEVE_RISK.get(sid, {})
        rows.append(
            {
                "id": sid,
                "display_name": c.get("display_name"),
                "max_dd_budget_pct": meta.get("max_dd_budget_pct"),
                "current_max_dd_pct": c.get("max_drawdown_pct"),
                "dd_headroom_pct": round(
                    float(meta.get("max_dd_budget_pct") or 0)
                    - abs(float(c.get("max_drawdown_pct") or 0)),
                    1,
                ),
                "stop_framework": meta.get("stop_framework"),
                "rebalance_cadence": meta.get("rebalance_cadence"),
                "concentration_cap": meta.get("concentration_cap"),
                "escalation": (
                    "Breach DD budget → auto REDUCED"
                    if abs(float(c.get("max_drawdown_pct") or 0))
                    > float(meta.get("max_dd_budget_pct") or 99)
                    else "Within budget"
                ),
            }
        )
    return rows


def build_reaction_monitor(
    cards: List[Dict[str, Any]],
    *,
    regime: str = "",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """If/then PM checklist — static rules + sleeve-specific."""
    rules: List[Dict[str, Any]] = []
    if vix is not None and vix > 20:
        rules.append(
            {
                "if": f"VIX > 20 (now {vix:.0f})",
                "then": "Upweight Tactical / Defensive · cut Leader size",
                "priority": "high",
            }
        )
    if breadth is not None and breadth < 50:
        rules.append(
            {
                "if": f"Breadth < 50% (now {breadth:.0f}%)",
                "then": "Keep Leader PAUSED · Balanced REDUCED until breadth recovers",
                "priority": "high",
            }
        )
    if breadth is not None and breadth >= 50:
        rules.append(
            {
                "if": "Breadth ≥ 50%",
                "then": "Balanced may resume · review Leader for unpause",
                "priority": "medium",
            }
        )
    leader = next((c for c in cards if c.get("id") == "LEADER_MOMENTUM"), None)
    if leader and (leader.get("holdings") or []):
        tickers = ", ".join(h["ticker"] for h in leader["holdings"][:3])
        rules.append(
            {
                "if": f"Leadership confirms ({tickers})",
                "then": "Leader unpause candidate — timing gate still required",
                "priority": "medium",
            }
        )
    rules.append(
        {
            "if": "Regime WAIT + UPTREND backdrop",
            "then": "Deploy selectively — size ½ until TRADE-ready name exists",
            "priority": "high",
        }
    )
    rules.append(
        {
            "if": "Earnings cluster / macro event",
            "then": "Reduce new adds · widen stops on momentum sleeve",
            "priority": "low",
        }
    )
    return rules[:10]


def build_allocator_decision_strip(
    cards: List[Dict[str, Any]],
    *,
    regime_display: str = "",
    tradeability: str = "",
    best_action_liner: str = "",
    benchmark_return_pct: float = 0.0,
) -> Dict[str, Any]:
    """Layer 1 — 30-second allocator answers."""
    deploy_pool = [c for c in cards if c.get("gate_status") in ("ACTIVE", "REDUCED")]
    paused = [c for c in cards if c.get("gate_status") == "PAUSED"]
    sorted_fit = sorted(cards, key=lambda c: -(c.get("regime_fit") or 0))

    best_now = deploy_pool[0] if deploy_pool else (sorted_fit[0] if sorted_fit else None)
    highest_upside = next(
        (c for c in cards if c.get("id") == "LEADER_MOMENTUM"),
        sorted_fit[0] if sorted_fit else None,
    )
    weakest = sorted_fit[-1] if sorted_fit else None

    alloc = build_allocation_recommendation(cards, regime_display)
    cash_pct = 100 - sum(w.get("weight_pct", 0) for w in alloc.get("weights") or [])
    if cash_pct < 0:
        cash_pct = 20

    should_deploy = tradeability not in ("NO_TRADE", "") and bool(deploy_pool)
    blockers: List[str] = []
    if tradeability in ("WAIT", "SELECTIVE"):
        blockers.append("Tradeability WAIT — no full deploy until setup passes gates")
    if paused:
        blockers.append(
            f"{len(paused)} sleeve(s) PAUSED — "
            f"{', '.join((p.get('display_name') or '').split()[0] for p in paused[:2])}"
        )
    if not blockers:
        blockers.append("Breadth / timing confirmation still required for momentum sleeve")

    return {
        "deploy_capital": should_deploy,
        "deploy_posture": (
            "cautious_selective"
            if tradeability in ("WAIT", "SELECTIVE")
            else "full_selective"
            if should_deploy
            else "preserve_cash"
        ),
        "where": (best_now or {}).get("display_name", "Cash"),
        "how_much": alloc.get("headline", "0% deploy"),
        "cash_reserve_pct": max(cash_pct, 15),
        "capital_split": alloc.get("weights") or [],
        "best_sleeve_now": (best_now or {}).get("display_name"),
        "highest_upside_if_confirmed": (highest_upside or {}).get("display_name"),
        "weakest_sleeve": (weakest or {}).get("display_name"),
        "do_not_allocate": [p.get("display_name") for p in paused],
        "closest_to_reactivation": (
            sorted_fit[0].get("display_name")
            if sorted_fit and sorted_fit[0].get("gate_status") != "ACTIVE"
            else None
        ),
        "why_now": best_action_liner or alloc.get("note", ""),
        "why_not": " · ".join(blockers[:3]),
        "if_follow": "Selective sleeve weights per model · 1R discipline",
        "if_wrong": "Cut REDUCED sleeves first · raise cash to reserve",
        "regime_display": regime_display,
        "tradeability": tradeability,
        "performance_basis": f"Backtest 1y vs SPY ({benchmark_return_pct}% BM)",
    }


def enrich_fund_card(
    card: Dict[str, Any],
    regime: str = "unknown",
    *,
    period: str = "1y",
    benchmark_return_pct: float = 0.0,
) -> Dict[str, Any]:
    """Attach active manager operating fields to a model fund card."""
    out = dict(card)
    gs = (card.get("gate_status") or "NO_DATA").upper()
    out["manager_status"] = gs
    out["deployability"] = (
        "DEPLOY"
        if gs == "ACTIVE"
        else "REDUCE"
        if gs == "REDUCED"
        else "OFF"
        if gs in ("PAUSED", "NO_DATA")
        else "WATCH"
    )
    out["status_reason"] = _status_reason(card, regime)
    out["regime_fit_explanation"] = _regime_fit_explanation(
        card.get("id") or "", int(card.get("regime_fit") or 0), regime
    )
    out["next_trigger"] = _next_trigger(card, regime)
    out["next_review"] = "Daily open · intraday on regime shift"
    out["target_allocation"] = _target_allocation(card)
    out["last_rebalance"] = _last_change_summary(card)
    out["regime_fit_decomposed"] = decompose_regime_fit(card, regime)
    out["manager_box"] = build_manager_box(out, regime)
    out["performance_evidence"] = build_performance_evidence(
        out, period=period, benchmark_return_pct=benchmark_return_pct
    )
    from src.services.decision_bar import enrich_curve_diagnostics

    out["curve_diagnostics"] = enrich_curve_diagnostics(out)
    out["evidence_quality"] = {
        "badge": out["performance_evidence"]["evidence"],
        "mode": out["performance_evidence"]["mode"],
        "sample": out["performance_evidence"]["sample"],
        "period": period,
        "calibrated": False,
        "label": out["performance_evidence"]["label"],
        "trust_tier": out["performance_evidence"]["trust_tier"],
    }
    out["underwater_badge"] = {
        "max_drawdown_pct": card.get("max_drawdown_pct"),
        "watermark_dd": card.get("watermark_drawdown"),
        "recovery_days": card.get("recovery_days"),
    }
    bm = float(card.get("benchmark_return_pct") or benchmark_return_pct or 0)
    fr = float(card.get("fund_return_pct") or 0)
    if bm == 0 and fr != 0:
        out["alpha_warning"] = "Benchmark return unavailable — excess vs SPY not computed"
    else:
        out["alpha_warning"] = None
    risk_meta = _SLEEVE_RISK.get(card.get("id") or "", {})
    out["risk_governance"] = {
        "max_dd_budget_pct": risk_meta.get("max_dd_budget_pct"),
        "stop_framework": risk_meta.get("stop_framework"),
    }
    return out


def build_allocation_recommendation(
    cards: List[Dict[str, Any]], regime: str = ""
) -> Dict[str, Any]:
    """Suggested sleeve weights from regime fit (not live orders)."""
    active = [c for c in cards if c.get("gate_status") == "ACTIVE"]
    reduced = [c for c in cards if c.get("gate_status") == "REDUCED"]
    if not active and not reduced:
        return {
            "headline": "No active sleeve allocation now",
            "weights": [],
            "note": "All sleeves PAUSED — preserve cash / monitor triggers",
        }
    pool = active if active else reduced
    total_fit = sum(max(c.get("regime_fit") or 0, 1) for c in pool)
    weights = [
        {
            "id": c.get("id"),
            "display_name": c.get("display_name"),
            "weight_pct": round((c.get("regime_fit") or 0) / total_fit * 100, 0),
            "gate_status": c.get("gate_status"),
        }
        for c in sorted(pool, key=lambda x: -(x.get("regime_fit") or 0))
    ]
    headline = (
        " · ".join(f"{w['display_name'].split()[0]} {w['weight_pct']}%" for w in weights[:3])
        if weights
        else "No allocation"
    )
    cash_pct = max(15, 100 - sum(w["weight_pct"] for w in weights))
    strongest = weights[0] if weights else None
    weakest_card = min(cards, key=lambda c: c.get("regime_fit") or 0) if cards else None
    return {
        "headline": headline,
        "weights": weights,
        "cash_reserve_pct": cash_pct,
        "strongest_deployable": strongest,
        "weakest": (
            {
                "id": weakest_card.get("id"),
                "display_name": weakest_card.get("display_name"),
            }
            if weakest_card
            else None
        ),
        "marginal_instruction": (
            f"Add to {strongest['display_name']}"
            if strongest
            else "No marginal add — stay in cash"
        ),
        "do_not_allocate_now": [
            c.get("display_name") for c in cards if c.get("gate_status") == "PAUSED"
        ],
        "note": "Model suggestion from regime fit — confirm with risk limits",
    }


def build_comparison_table(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per sleeve for PM scan."""
    rows: List[Dict[str, Any]] = []
    for c in cards:
        curve = c.get("equity_curve_20") or []
        recent_20d = (
            round((curve[-1] - curve[0]) / curve[0] * 100, 2)
            if len(curve) >= 2 and curve[0]
            else None
        )
        rows.append(
            {
                "id": c.get("id"),
                "display_name": c.get("display_name"),
                "gate_status": c.get("gate_status"),
                "stance": c.get("stance"),
                "regime_fit": c.get("regime_fit"),
                "max_drawdown_pct": c.get("max_drawdown_pct"),
                "recent_20d_pct": recent_20d,
                "excess_return_pct": c.get("excess_return_pct"),
                "deployability": c.get("deployability"),
                "evidence_badge": (c.get("evidence_quality") or {}).get("badge")
                or c.get("evidence_badge"),
                "controls_capital": bool(c.get("controls_capital")),
                "monitor_priority": (
                    "HIGH"
                    if c.get("gate_status") == "ACTIVE"
                    else "MEDIUM"
                    if c.get("gate_status") == "REDUCED"
                    else "LOW"
                ),
                "target_weight_pct": next(
                    (
                        w["weight_pct"]
                        for w in (c.get("_alloc_weights") or [])
                        if w.get("id") == c.get("id")
                    ),
                    None,
                ),
            }
        )
    return rows


def build_fund_monitor_triggers(
    cards: List[Dict[str, Any]], regime: str = ""
) -> List[Dict[str, Any]]:
    """What to monitor across sleeves."""
    triggers: List[Dict[str, Any]] = []
    closest = None
    best_fit = -1
    for c in cards:
        fit = int(c.get("regime_fit") or 0)
        if c.get("gate_status") != "ACTIVE" and fit > best_fit:
            best_fit = fit
            closest = c
    if closest:
        triggers.append(
            {
                "type": "upgrade",
                "label": f"Closest to activation: {closest.get('display_name')}",
                "detail": closest.get("next_trigger") or closest.get("status_reason"),
                "horizon": "daily",
            }
        )
    controller = next((c for c in cards if c.get("controls_capital")), None)
    if controller:
        triggers.append(
            {
                "type": "active",
                "label": f"Capital sleeve: {controller.get('display_name')}",
                "detail": controller.get("status_reason", ""),
                "horizon": "intraday",
            }
        )
    if (regime or "").upper() in ("UNKNOWN", ""):
        triggers.append(
            {
                "type": "regime",
                "label": "Regime label stale",
                "detail": "Fund lab regime unknown — align with Today REGIME strip",
                "horizon": "immediate",
            }
        )
    for c in cards:
        if c.get("adds"):
            triggers.append(
                {
                    "type": "rebalance",
                    "label": f"{c.get('display_name')}: new adds",
                    "detail": ", ".join(c["adds"][:4]),
                    "horizon": "weekly",
                }
            )
    return triggers[:8]


def build_fund_console_payload(
    *,
    cards: List[Dict[str, Any]],
    regime: str,
    benchmark: str,
    execution_readiness: Optional[Dict[str, Any]] = None,
    market_regime_label: str = "",
    period: str = "1y",
    benchmark_return_pct: float = 0.0,
    tradeability: str = "",
    best_action_liner: str = "",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
) -> Dict[str, Any]:
    """Full fund tab payload — allocator command center."""
    regime_resolved = regime if regime and regime != "unknown" else market_regime_label or regime
    enriched = [
        enrich_fund_card(
            c,
            regime_resolved,
            period=period,
            benchmark_return_pct=benchmark_return_pct,
        )
        for c in cards
    ]
    allocation = build_allocation_recommendation(enriched, regime_resolved)
    alloc_weights = allocation.get("weights") or []
    for c in enriched:
        c["_alloc_weights"] = alloc_weights
    comparison = build_comparison_table(enriched)
    controller = next((c for c in enriched if c.get("controls_capital")), None)
    regime_display = market_regime_label or regime_resolved
    allocator_decision = build_allocator_decision_strip(
        enriched,
        regime_display=regime_display,
        tradeability=tradeability,
        best_action_liner=best_action_liner,
        benchmark_return_pct=benchmark_return_pct,
    )
    from src.services.decision_bar import bar_from_funds

    decision_bar = bar_from_funds(
        allocator_decision,
        active_sleeve=(controller or {}).get("display_name"),
    )
    return {
        "regime": regime_resolved,
        "regime_display": regime_display,
        "benchmark": benchmark,
        "benchmark_return_pct": benchmark_return_pct,
        "period": period,
        "allocator_decision": allocator_decision,
        "decision_bar": decision_bar,
        "cards": enriched,
        "allocation": allocation,
        "comparison_table": comparison,
        "monitor_triggers": build_fund_monitor_triggers(enriched, regime_resolved),
        "reaction_monitor": build_reaction_monitor(
            enriched, regime=regime_resolved, vix=vix, breadth=breadth
        ),
        "holdings_overlap": build_holdings_overlap(enriched),
        "risk_governance": build_risk_governance(enriched),
        "active_manager": {
            "sleeve_id": (controller or {}).get("id"),
            "display_name": (controller or {}).get("display_name"),
            "stance": (controller or {}).get("stance"),
            "mode": (controller or {}).get("mode"),
            "controls_capital": bool((controller or {}).get("controls_capital")),
            "manager_box": (controller or {}).get("manager_box"),
        },
        "execution_readiness": execution_readiness or {},
        "evidence_note": "All sleeves: model_backtest · 1y gross · not live track record",
        "count": len(enriched),
    }
