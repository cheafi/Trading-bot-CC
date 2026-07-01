"""Fund Research Lab — sleeve research layer on model backtests (not live allocation authority)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

FUNDS_RESEARCH_LAB_TITLE = "Fund Research Lab"
FUNDS_GUARDRAIL = "Funds tab is not an allocation instruction."

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


def _is_unknown_regime(regime: str) -> bool:
    norm = (regime or "").strip().upper().replace(" ", "_")
    return not norm or norm in ("UNKNOWN", "UNRESOLVED", "N/A", "NA", "—")


def _format_today_regime_label(trend: str, tradeability: str = "") -> str:
    parts = [p for p in [(trend or "").strip(), (tradeability or "").strip()] if p]
    return " · ".join(parts) if parts else ""


def resolve_fund_regime(
    *,
    sleeve_regime: str = "",
    today_trend: str = "",
    today_tradeability: str = "",
    fund_lab_sync_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """Align fund-lab sleeve regime with Today strip — never bare UNKNOWN when Today knows."""
    today_label = _format_today_regime_label(today_trend, today_tradeability)
    sleeve_unknown = _is_unknown_regime(sleeve_regime)
    resolved = (sleeve_regime or "").strip()
    source = "fund_lab"
    note = ""

    if sleeve_unknown and today_label:
        resolved = today_label
        source = "today_fallback"
        note = f"Using Today regime: {today_label}"
    elif sleeve_unknown:
        resolved = "Regime unresolved"
        source = "unresolved"
        note = "Local sleeve regime unresolved — refresh Today + fund lab"
    elif today_label and today_label.upper() != resolved.upper():
        source = "fund_lab_with_today"
        note = f"Fund lab: {resolved} · Today: {today_label}"

    stale_note = ""
    regime_stale = False
    if fund_lab_sync_ts:
        age_min = max(0, int((datetime.now(timezone.utc).timestamp() - fund_lab_sync_ts) / 60))
        if age_min >= 30:
            hh = age_min // 60
            mm = age_min % 60
            stale_note = f"Fund lab regime snapshot stale (last sync {hh:02d}:{mm:02d} ago)"
            regime_stale = True
    if sleeve_unknown and today_label:
        regime_stale = True

    return {
        "regime": resolved,
        "regime_display": resolved if not sleeve_unknown else (today_label or resolved),
        "regime_source": source,
        "regime_note": note or stale_note or resolved,
        "regime_stale_note": stale_note,
        "regime_stale": regime_stale,
        "regime_sync_age_min": (
            max(0, int((datetime.now(timezone.utc).timestamp() - fund_lab_sync_ts) / 60))
            if fund_lab_sync_ts
            else None
        ),
        "today_regime_label": today_label,
        "using_today_fallback": sleeve_unknown and bool(today_label),
    }


def _total_live_trades(cards: List[Dict[str, Any]]) -> int:
    total = 0
    for c in cards:
        eq = c.get("evidence_quality") or {}
        try:
            total += int(eq.get("live_trades_count") or 0)
        except (TypeError, ValueError):
            continue
    return total


def resolve_funds_mode(
    *,
    execution_readiness: Optional[Dict[str, Any]] = None,
    tradeability: str = "",
    cards: Optional[List[Dict[str, Any]]] = None,
    system_truth: Optional[Dict[str, Any]] = None,
    allocation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Research-only vs allocation authority — driven by broker, sync, live trades, gates."""
    ex = execution_readiness or {}
    truth = system_truth or {}
    card_list = cards or []
    alloc = allocation or {}

    broker_connected = bool(ex.get("broker_connected"))
    portfolio_synced = bool(ex.get("portfolio_synced"))
    portfolio_manual = str(ex.get("portfolio_source") or "manual").lower() == "manual"
    live_trades = _total_live_trades(card_list)
    tb = str(tradeability or truth.get("regime_state") or "").upper()
    regime_no_trade = tb == "NO_TRADE" or str(truth.get("regime_state") or "").upper() == "NO_TRADE"
    board_closed = str(truth.get("board_gate") or "") == "closed" or regime_no_trade
    gates_blocked = bool(truth.get("reason_codes")) and not bool(truth.get("deploy_authority"))
    if truth and "deploy_authority" in truth:
        gates_blocked = gates_blocked or not bool(truth.get("deploy_authority"))
    elif regime_no_trade or tb in ("WAIT", "NO_TRADE"):
        gates_blocked = True

    blockers: List[str] = []
    if not broker_connected:
        blockers.append("broker offline")
    if portfolio_manual or not portfolio_synced:
        blockers.append("portfolio not synced")
    if live_trades == 0:
        blockers.append("no live validation")
    if regime_no_trade:
        blockers.append("NO_TRADE")
    elif tb in ("WAIT", "SELECTIVE"):
        blockers.append(f"tradeability {tb}")
    if gates_blocked and "NO_TRADE" not in blockers:
        blockers.append("gates blocked")

    research_only_mode = bool(blockers)
    theoretical_band = alloc.get("deployable_capital_range") or alloc.get("theoretical_model_band")
    live_eligible_pct = 0 if research_only_mode else int(alloc.get("deployable_capital_pct") or 0)

    if research_only_mode:
        allocation_authority = "none"
    elif live_trades == 0:
        allocation_authority = "none"
    elif broker_connected and portfolio_synced and live_eligible_pct > 0:
        allocation_authority = "limited"
    else:
        allocation_authority = "none"

    return {
        "research_only_mode": research_only_mode,
        "live_allocation_eligible": live_eligible_pct,
        "allocation_authority": allocation_authority,
        "live_trades_count": live_trades,
        "theoretical_model_band": theoretical_band,
        "blockers": blockers,
        "allocation_execution_locked": research_only_mode,
        "guardrail": FUNDS_GUARDRAIL,
    }


def build_funds_first_screen(
    *,
    funds_mode: Dict[str, Any],
    index_posture: Optional[Dict[str, Any]] = None,
    strength_strips: Optional[Dict[str, Any]] = None,
    cards: Optional[List[Dict[str, Any]]] = None,
    system_truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Default first-screen copy — research posture before sleeve detail."""
    truth = system_truth or {}
    posture = index_posture or {}
    strips = strength_strips or {}
    card_list = cards or []
    blockers = funds_mode.get("blockers") or []
    why = " + ".join(blockers) if blockers else "live validation pending"

    best_research = strips.get("strongest_research") or {}
    missing_validation: List[str] = ["walk-forward OOS", "transaction costs", "live track record"]
    if funds_mode.get("live_trades_count", 0) == 0:
        missing_validation.insert(0, "live trades")

    core_action = (
        posture.get("action_label")
        or (posture.get("benchmark_judgment") or {}).get("action_label")
        or "hold core · no urgent action"
    )

    return {
        "now": "Research only · no live allocation",
        "why": why,
        "core_index_posture": core_action,
        "live_allocation_pct": funds_mode.get("live_allocation_eligible", 0),
        "live_allocation_label": f"{funds_mode.get('live_allocation_eligible', 0)}%",
        "best_research_sleeve": {
            "headline": "research hypothesis only",
            "label": best_research.get("label") or "No sleeve ranked yet",
            "missing_validation": missing_validation,
        },
        "next_steps": ["sync broker", "validate OOS", "apply costs"],
        "guardrail": FUNDS_GUARDRAIL,
        "hypothesis_only": bool(funds_mode.get("research_only_mode")),
        "theoretical_model_band_note": (
            f"Theoretical model band: {funds_mode.get('theoretical_model_band')} "
            "if validation later passes"
            if funds_mode.get("theoretical_model_band") and funds_mode.get("live_allocation_eligible", 0) == 0
            else None
        ),
    }


def build_backtest_quarantine(card: Dict[str, Any]) -> Dict[str, Any]:
    """Collapsed backtest summary — hide α/Sharpe until expanded."""
    eq = card.get("evidence_quality") or {}
    live = int(eq.get("live_trades_count") or 0)
    return {
        "collapsed_default": True,
        "validation_model_only": True,
        "live_trades_count": live,
        "walk_forward": "missing",
        "costs": "unknown",
        "allocation_authority": "none",
        "summary_lines": [
            "Validation model-only",
            f"Live trades {live}",
            "Walk-forward missing",
            "Costs unknown",
            "Allocation authority none",
        ],
        "show_alpha_sharpe": False,
        "fund_return_pct": card.get("fund_return_pct"),
        "excess_return_pct": card.get("excess_return_pct"),
        "sharpe": card.get("sharpe"),
        "max_drawdown_pct": card.get("max_drawdown_pct"),
    }


def _model_stance_label(deployability: str) -> str:
    """Replace deploy language with model stance labels."""
    d = (deployability or "").upper()
    if d == "REDUCE":
        return "Model stance: Reduced"
    if d == "DEPLOY":
        return "Model stance: Active (hypothetical)"
    if d == "OFF":
        return "Model stance: Off"
    if d == "WATCH":
        return "Model stance: Watch"
    return f"Model stance: {deployability or 'Neutral'}"


def _validation_confidence(card: Dict[str, Any], manager_box: Dict[str, Any]) -> Optional[str]:
    """No MEDIUM/HIGH conviction when model-only and live trades = 0."""
    live = int((card.get("evidence_quality") or {}).get("live_trades_count") or 0)
    tier = str((card.get("evidence_quality") or {}).get("trust_tier") or "research_only")
    raw = str(manager_box.get("conviction") or "").upper()
    if live == 0 or tier == "research_only":
        if raw in ("MEDIUM", "HIGH"):
            return None
        return "pending" if not raw or raw == "LOW" else None
    return manager_box.get("conviction")


def _display_text(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value).strip()
    if text.lower() in ("true", "false"):
        return "Yes" if text.lower() == "true" else "No"
    return text or default


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


def _honest_deploy_label(
    *,
    deploy_pool: List[Dict[str, Any]],
    paused: List[Dict[str, Any]],
    regime_stale: bool,
    execution_state: str,
    broker_connected: bool,
    handoff_ready: bool,
    paper_mode: bool,
    portfolio_manual: bool,
    only_reduced: bool,
    best_now: Optional[Dict[str, Any]],
) -> tuple[bool, str]:
    """Brutally honest deploy label — never imply live authority when blockers exist."""
    if not deploy_pool:
        return False, "No fully live-validated sleeve"
    if regime_stale:
        if only_reduced and best_now:
            short = (best_now.get("display_name") or "Sleeve").split()[0]
            return False, f"Research-weight only · {short} reduced"
        return False, "Research-weight only"
    if execution_state == "analysis_only" or not broker_connected:
        return False, "Paper allocation only — not execution-ready"
    if not handoff_ready:
        return False, "Analysis only — handoff not ready"
    if paper_mode:
        return False, "Paper allocation only — not live-validated"
    if portfolio_manual:
        return False, "Manual book sync — allocator view only"
    if len(paused) >= 2 and only_reduced and best_now:
        short = (best_now.get("display_name") or "Tactical").split()[0]
        return False, f"{short} sleeve only, reduced"
    active = [c for c in deploy_pool if c.get("gate_status") == "ACTIVE"]
    if not active:
        short = (best_now or {}).get("display_name", "Sleeve").split()[0]
        return False, f"{short} sleeve only, reduced"
    return True, "Selective deploy · execution-ready"


def build_allocator_decision_strip(
    cards: List[Dict[str, Any]],
    *,
    regime_display: str = "",
    tradeability: str = "",
    best_action_liner: str = "",
    benchmark_return_pct: float = 0.0,
    regime_stale: bool = False,
    execution_readiness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Layer 1 — 30-second allocator answers (honest, not backtest-authoritative)."""
    deploy_pool = sorted(
        [c for c in cards if c.get("gate_status") in ("ACTIVE", "REDUCED")],
        key=lambda c: -(c.get("regime_fit") or 0),
    )
    paused = [c for c in cards if c.get("gate_status") == "PAUSED"]
    sorted_fit = sorted(cards, key=lambda c: -(c.get("regime_fit") or 0))
    only_reduced = not any(c.get("gate_status") == "ACTIVE" for c in deploy_pool)

    best_now = deploy_pool[0] if deploy_pool else None
    highest_upside = next(
        (c for c in cards if c.get("id") == "LEADER_MOMENTUM"),
        sorted_fit[0] if sorted_fit else None,
    )
    weakest = sorted_fit[-1] if sorted_fit else None

    ex = execution_readiness or {}
    execution_state = str(ex.get("execution_state") or "analysis_only")
    broker_connected = bool(ex.get("broker_connected"))
    handoff_ready = bool(ex.get("trade_handoff_ready"))
    paper_mode = str(ex.get("paper_or_live") or "paper") != "live"
    portfolio_manual = str(ex.get("portfolio_source") or "manual").lower() == "manual"
    execution_ready = execution_state in ("basket_ready", "paper_handoff_ready") and handoff_ready

    alloc = build_allocation_recommendation(
        cards,
        regime_display,
        regime_stale=regime_stale,
        execution_ready=execution_ready,
    )
    cash_pct = int(alloc.get("cash_reserve_pct") or 15)
    deployable_pct = int(alloc.get("deployable_capital_pct") or 0)
    net_exposure = float(alloc.get("net_portfolio_exposure_pct") or 0)

    should_deploy, deploy_label = _honest_deploy_label(
        deploy_pool=deploy_pool,
        paused=paused,
        regime_stale=regime_stale,
        execution_state=execution_state,
        broker_connected=broker_connected,
        handoff_ready=handoff_ready,
        paper_mode=paper_mode,
        portfolio_manual=portfolio_manual,
        only_reduced=only_reduced,
        best_now=best_now,
    )
    if tradeability == "NO_TRADE":
        should_deploy = False
        deploy_label = "No live deploy — tradeability NO_TRADE"

    blockers: List[str] = []
    if regime_stale:
        blockers.append("Regime snapshot stale — freeze sizing at research weight")
    if not broker_connected:
        blockers.append("Execution: gateway not logged in")
    if not handoff_ready:
        blockers.append("Trade handoff not ready")
    if paper_mode:
        blockers.append("Paper mode — not live-validated")
    if portfolio_manual:
        blockers.append("Portfolio manual sync")
    for c in paused:
        blockers.append(
            f"{(c.get('display_name') or c.get('id') or 'Sleeve').split()[0]} "
            f"fit {c.get('regime_fit')}% — PAUSED"
        )
    for c in deploy_pool:
        if c.get("gate_status") == "REDUCED":
            blockers.append(
                f"{(c.get('display_name') or '').split()[0]} fit {c.get('regime_fit')}% — REDUCED"
            )
    if tradeability in ("WAIT", "SELECTIVE"):
        blockers.append(f"Tradeability {tradeability} — selective sizing only")
    if not blockers:
        blockers.append("No live-validated sleeve track record — backtest only")

    how_much = alloc.get("tactical_mix_label") or alloc.get("marginal_instruction") or (
        f"Hypothetical research band {alloc.get('deployable_capital_range', deployable_pct)} · "
        f"net ~{net_exposure}% if gates reopen · cash {alloc.get('cash_reserve_range', str(cash_pct)+'%')}"
    )

    return {
        "deploy_capital": should_deploy,
        "deploy_capital_label": deploy_label,
        "deploy_posture": (
            "research_weight_only"
            if regime_stale
            else "analysis_only"
            if execution_state == "analysis_only" or not broker_connected
            else "cautious_selective"
            if only_reduced or tradeability in ("WAIT", "SELECTIVE")
            else "selective"
            if should_deploy
            else "preserve_cash"
        ),
        "where": (best_now or {}).get("display_name", "Cash"),
        "how_much": how_much,
        "deployable_capital_pct": deployable_pct,
        "deployable_capital_range": alloc.get("deployable_capital_range"),
        "net_portfolio_exposure_pct": net_exposure,
        "cash_reserve_pct": cash_pct,
        "cash_reserve_range": alloc.get("cash_reserve_range"),
        "allocation_summary": how_much,
        "marginal_instruction": alloc.get("marginal_instruction"),
        "capital_split": alloc.get("weights") or [],
        "best_sleeve_now": (best_now or {}).get("display_name"),
        "highest_upside_if_confirmed": (highest_upside or {}).get("display_name"),
        "weakest_sleeve": (weakest or {}).get("display_name"),
        "do_not_allocate": [p.get("display_name") for p in paused],
        "do_not_allocate_now": [p.get("display_name") for p in paused],
        "blocked_sleeves": [
            {
                "id": c.get("id"),
                "display_name": c.get("display_name"),
                "gate_status": c.get("gate_status"),
                "regime_fit": c.get("regime_fit"),
            }
            for c in cards
            if c.get("gate_status") in ("PAUSED", "NO_DATA")
        ],
        "closest_to_reactivation": (
            sorted_fit[0].get("display_name")
            if sorted_fit and sorted_fit[0].get("gate_status") != "ACTIVE"
            else None
        ),
        "why_now": best_action_liner or alloc.get("note", ""),
        "why_not": " · ".join(blockers[:5]),
        "if_follow": "Research-weight sizing only · confirm regime + execution before live",
        "if_wrong": "Cut REDUCED sleeves first · raise cash to reserve band",
        "regime_display": regime_display,
        "tradeability": tradeability,
        "performance_basis": "Training / backtest only · not live track record",
        "confidence": 35 if regime_stale or not execution_ready else 50 if only_reduced else 55,
        "reduce_exposure": regime_stale or only_reduced,
    }


def build_allocator_truth_strip(
    cards: List[Dict[str, Any]],
    *,
    allocator_decision: Dict[str, Any],
    execution_readiness: Optional[Dict[str, Any]] = None,
    regime_stale: bool = False,
) -> Dict[str, Any]:
    """Single honest strip — live vs research vs execution blockers."""
    ex = execution_readiness or {}
    live_eligible = [
        c
        for c in cards
        if c.get("gate_status") == "ACTIVE"
        and (c.get("evidence_quality") or {}).get("trust_tier") == "live_validated"
    ]
    research = [c for c in cards if c.get("gate_status") in ("ACTIVE", "REDUCED", "PAUSED", "NO_DATA")]
    deploy_pool = [c for c in cards if c.get("gate_status") in ("ACTIVE", "REDUCED")]
    best_partial = deploy_pool[0] if deploy_pool else None
    execution_ready = (
        str(ex.get("execution_state") or "") in ("basket_ready", "paper_handoff_ready")
        and bool(ex.get("trade_handoff_ready"))
        and bool(ex.get("broker_connected"))
    )

    why_not: List[str] = []
    for c in cards:
        gs = (c.get("gate_status") or "").upper()
        fit = int(c.get("regime_fit") or 0)
        short = (c.get("display_name") or c.get("id") or "?").split()[0]
        if gs == "PAUSED":
            why_not.append(f"{short} fit {fit} — PAUSED")
        elif gs == "REDUCED":
            why_not.append(f"{short} fit {fit} — REDUCED")
    if not ex.get("broker_connected"):
        why_not.append("Execution not logged in")
    if not ex.get("trade_handoff_ready"):
        why_not.append("Handoff not ready")
    if regime_stale:
        why_not.append("Regime stale")
    if str(ex.get("portfolio_source") or "manual").lower() == "manual":
        why_not.append("Manual portfolio sync")

    allocatable = "None"
    if best_partial:
        short = (best_partial.get("display_name") or "Sleeve").split()[0]
        allocatable = f"{short} only (research fit)"

    theoretical_band = (
        allocator_decision.get("deployable_capital_range")
        or f"{allocator_decision.get('deployable_capital_pct', 0)}%"
    )
    live_eligible_pct = 0
    if execution_ready and len(live_eligible) > 0:
        live_eligible_pct = int(allocator_decision.get("deployable_capital_pct") or 0)

    return {
        "live_eligible_count": len(live_eligible),
        "research_sleeve_count": len(research),
        "execution_ready": execution_ready,
        "execution_ready_label": "Yes" if execution_ready else "No",
        "current_allocatable": allocatable,
        "current_research_fit": allocatable,
        "max_capital_allowed": (
            f"{live_eligible_pct}%"
            if live_eligible_pct > 0
            else "0%"
        ),
        "live_eligible_capital_pct": live_eligible_pct,
        "theoretical_model_band": theoretical_band,
        "max_capital_label": "Theoretical model band (hypothetical)",
        "why_not_more": why_not[:6],
        "headline": (
            "Funds research is promising, but only "
            f"{(best_partial.get('display_name') or 'one sleeve').split()[0] if best_partial else 'no sleeve'} "
            "shows partial research fit now — not live-validated for capital."
            if best_partial
            else "No sleeve is live-validated for capital deployment now."
        ),
        "deploy_label": allocator_decision.get("deploy_capital_label"),
        "research_hypothesis_only": live_eligible_pct == 0,
    }


def build_investable_now_zone(
    *,
    regime_ctx: Dict[str, Any],
    allocator_decision: Dict[str, Any],
    allocator_truth: Dict[str, Any],
    allocation: Dict[str, Any],
    execution_readiness: Optional[Dict[str, Any]] = None,
    strength_strips: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Zone A — core index posture (advisory; not live deploy authority)."""
    ex = execution_readiness or {}
    strips = strength_strips or {}
    return {
        "title": "Core index posture",
        "regime": regime_ctx.get("regime_display"),
        "regime_source": regime_ctx.get("regime_source"),
        "regime_stale": bool(regime_ctx.get("regime_stale")),
        "regime_stale_note": regime_ctx.get("regime_stale_note") or "",
        "regime_note": regime_ctx.get("regime_note") or "",
        "deploy_label": allocator_decision.get("deploy_capital_label"),
        "deploy_posture": allocator_decision.get("deploy_posture"),
        "model_stance_label": _model_stance_label(
            (allocator_decision.get("deploy_posture") or "").replace("research_weight_only", "REDUCE")
        ),
        "strongest_eligible": strips.get("strongest_live"),
        "strongest_research_fit": strips.get("strongest_live"),
        "strongest_research": strips.get("strongest_research"),
        "blocked_sleeves": allocator_decision.get("blocked_sleeves") or [],
        "allocation_headline": allocation.get("headline"),
        "allocation_lines": allocation.get("allocation_lines") or [],
        "max_capital_allowed": allocator_truth.get("max_capital_allowed"),
        "live_eligible_capital_pct": allocator_truth.get("live_eligible_capital_pct", 0),
        "theoretical_model_band": allocator_truth.get("theoretical_model_band"),
        "execution_state_label": ex.get("execution_state_label") or ex.get("readiness_label"),
        "execution_ready": allocator_truth.get("execution_ready_label"),
        "truth_headline": allocator_truth.get("headline"),
        "why_not_more": allocator_truth.get("why_not_more") or [],
        "research_hypothesis_only": allocator_truth.get("research_hypothesis_only", True),
    }


def enrich_fund_card(
    card: Dict[str, Any],
    regime: str = "unknown",
    *,
    period: str = "1y",
    benchmark_return_pct: float = 0.0,
    research_only_mode: bool = True,
) -> Dict[str, Any]:
    """Attach research-lab fields to a model fund card."""
    out = dict(card)
    gs = (card.get("gate_status") or "NO_DATA").upper()
    raw_deploy = (
        "DEPLOY"
        if gs == "ACTIVE"
        else "REDUCE"
        if gs == "REDUCED"
        else "OFF"
        if gs in ("PAUSED", "NO_DATA")
        else "WATCH"
    )
    out["manager_status"] = gs
    out["deployability"] = raw_deploy
    out["deployability_raw"] = raw_deploy
    out["model_stance_label"] = _model_stance_label(raw_deploy)
    out["status_reason"] = _status_reason(card, regime)
    out["regime_fit_explanation"] = _regime_fit_explanation(
        card.get("id") or "", int(card.get("regime_fit") or 0), regime
    )
    out["next_trigger"] = _next_trigger(card, regime)
    out["next_review"] = "Daily open · intraday on regime shift"
    out["target_allocation"] = _target_allocation(card)
    out["last_rebalance"] = _last_change_summary(card)
    out["last_change"] = out["last_rebalance"]
    holdings = card.get("holdings") or []
    out["top_monitored"] = [
        h.get("ticker") for h in holdings[:4] if h.get("ticker")
    ]
    gs_upper = (card.get("gate_status") or "").upper()
    if gs_upper in ("REDUCED", "PAUSED"):
        out["upgrade_trigger"] = out.get("next_trigger") or _next_trigger(card, regime)
    out["regime_fit_decomposed"] = decompose_regime_fit(card, regime)
    out["manager_box"] = build_manager_box(out, regime)
    validation_conf = _validation_confidence(out, out["manager_box"])
    out["validation_confidence"] = validation_conf
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
        "live_trades_count": 0,
        "sample_window": f"{period} model backtest",
        "validation_tier": "research_only",
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
    out["allocator_action"] = build_sleeve_allocator_action(out)
    out["backtest_quarantine"] = build_backtest_quarantine(out)
    out["research_only_mode"] = research_only_mode
    out["show_target_holdings"] = not research_only_mode
    out["card_zones"] = {
        "current_state": {
            "status": gs_upper,
            "fit_pct": int(card.get("regime_fit") or 0),
            "deploy": out.get("model_stance_label") if research_only_mode else out.get("deployability"),
            "model_stance": out.get("model_stance_label"),
            "conviction": validation_conf,
            "validation_confidence": validation_conf,
            "stance": card.get("stance"),
        },
        "allocator_action": out["allocator_action"],
        "evidence": {
            "type": out["performance_evidence"].get("label"),
            "backtest_return_pct": card.get("fund_return_pct"),
            "max_dd_pct": card.get("max_drawdown_pct"),
            "sharpe": card.get("sharpe"),
            "sample_window": out["performance_evidence"].get("period"),
            "collapsed_default": True,
            "show_alpha_sharpe": not research_only_mode,
        },
        "current_book": {
            "title": "Model holdings (hypothetical)",
            "top_holdings": [
                h.get("ticker") for h in (card.get("holdings") or [])[:5] if h.get("ticker")
            ],
            "target_weights": (out.get("target_allocation") or []) if not research_only_mode else [],
            "recent_changes": (out.get("last_rebalance") or {}).get("summary"),
            "hidden_default": research_only_mode,
        },
    }
    return out


def _max_capital_range(
    *,
    best_fit: int,
    regime_stale: bool,
    execution_ready: bool,
    only_reduced: bool,
) -> Dict[str, Any]:
    """Honest deployable capital band — never imply full deploy on research-only sleeves."""
    if regime_stale:
        lo, hi = 25, 40
    elif only_reduced:
        cap = min(60, max(40, best_fit))
        lo, hi = max(35, cap - 5), min(65, cap + 5)
    elif execution_ready:
        lo, hi = min(55, best_fit), min(85, best_fit + 10)
    else:
        lo, hi = 35, 55
    return {
        "low_pct": lo,
        "high_pct": hi,
        "label": f"{lo}-{hi}%",
    }


def build_allocation_recommendation(
    cards: List[Dict[str, Any]],
    regime: str = "",
    *,
    regime_stale: bool = False,
    execution_ready: bool = False,
) -> Dict[str, Any]:
    """Suggested sleeve weights from regime fit (not live orders)."""
    active = [c for c in cards if c.get("gate_status") == "ACTIVE"]
    reduced = [c for c in cards if c.get("gate_status") == "REDUCED"]
    if not active and not reduced:
        return {
            "headline": "No active sleeve allocation now",
            "weights": [],
            "note": "All sleeves PAUSED — preserve cash / monitor triggers",
            "deployable_capital_pct": 0,
            "net_portfolio_exposure_pct": 0,
            "cash_reserve_pct": 100,
            "allocation_lines": [],
            "tactical_mix_label": "Cash 100%",
            "cash_reserve_range": "100%",
        }
    pool = active if active else reduced
    only_reduced = not active and bool(reduced)
    best_fit = max((c.get("regime_fit") or 0) for c in pool)
    cap_band = _max_capital_range(
        best_fit=best_fit,
        regime_stale=regime_stale,
        execution_ready=execution_ready,
        only_reduced=only_reduced,
    )
    deployable_pct = round((cap_band["low_pct"] + cap_band["high_pct"]) / 2, 0)
    cash_pct = round(100 - deployable_pct, 0)

    total_fit = sum(max(c.get("regime_fit") or 0, 1) for c in pool)
    gross_weights = [
        {
            "id": c.get("id"),
            "display_name": c.get("display_name"),
            "weight_pct": round((c.get("regime_fit") or 0) / total_fit * 100, 0),
            "gate_status": c.get("gate_status"),
        }
        for c in sorted(pool, key=lambda x: -(x.get("regime_fit") or 0))
    ]

    # REDUCED-only: cap sleeve share inside deployable pool (never implied 100% tactical)
    sleeve_share_lo, sleeve_share_hi = (60, 75) if only_reduced else (70, 100)
    cash_reserve_lo, cash_reserve_hi = (25, 40) if only_reduced else (15, 30)

    weights = []
    for i, w in enumerate(gross_weights):
        if only_reduced and len(pool) == 1:
            deploy_share = round(deployable_pct * sleeve_share_hi / 100, 1)
            gross_in_pool = sleeve_share_hi
        else:
            gross_in_pool = w["weight_pct"]
            deploy_share = round(w["weight_pct"] * deployable_pct / 100, 1)
        weights.append(
            {
                **w,
                "gross_sleeve_weight_pct": gross_in_pool,
                "deployable_share_pct": deploy_share,
                "sleeve_share_range": (
                    f"{sleeve_share_lo}-{sleeve_share_hi}% of research pool (hypothetical)"
                    if i == 0 and only_reduced
                    else None
                ),
            }
        )
    net_exposure = round(sum(w["deployable_share_pct"] for w in weights), 1)
    strongest = weights[0] if weights else None
    weakest_card = min(cards, key=lambda c: c.get("regime_fit") or 0) if cards else None

    tactical_mix = ""
    if only_reduced and strongest:
        short = (strongest.get("display_name") or "Sleeve").split()[0]
        tactical_mix = (
            f"Hypothetical mix: {short} {sleeve_share_lo}-{sleeve_share_hi}% of research pool · "
            f"cash {cash_reserve_lo}-{cash_reserve_hi}%"
        )

    allocation_lines = [
        f"Research allocation band: {cap_band['label']} — hypothetical if live gates reopen",
    ]
    if tactical_mix:
        allocation_lines.append(tactical_mix)
    elif strongest:
        allocation_lines.append(
            f"Hypothetical sleeve share: {(strongest.get('display_name') or '').split()[0]} "
            f"{strongest['gross_sleeve_weight_pct']:.0f}% of research pool"
        )
    allocation_lines.extend(
        [
            f"Hypothetical net exposure (if gates reopen): ~{net_exposure}%",
            f"Headroom estimate — cash band: {cash_reserve_lo}-{cash_reserve_hi}%",
        ]
    )

    headline = tactical_mix or (
        f"Research posture band {cap_band['label']} (not a live capital command) · "
        + " · ".join(
            f"{w['display_name'].split()[0]} ~{w['deployable_share_pct']:.0f}% hypothetical"
            for w in weights[:2]
        )
        if weights
        else "No research allocation posture"
    )
    marginal = tactical_mix or (
        f"Hypothetical: {(strongest.get('display_name') or '').split()[0]} "
        f"{sleeve_share_lo}-{sleeve_share_hi}% of research pool · cash {cash_reserve_lo}-{cash_reserve_hi}%"
        if strongest and only_reduced
        else (
            f"Research model: ~{strongest['gross_sleeve_weight_pct']:.0f}% of hypothetical pool to "
            f"{(strongest.get('display_name') or '').split()[0]}"
            if strongest
            else "No marginal research add — preserve cash posture"
        )
    )
    return {
        "headline": headline,
        "weights": weights,
        "cash_reserve_pct": cash_pct,
        "cash_reserve_range": f"{cash_reserve_lo}-{cash_reserve_hi}%",
        "deployable_capital_pct": deployable_pct,
        "deployable_capital_range": cap_band["label"],
        "net_portfolio_exposure_pct": net_exposure,
        "allocation_lines": allocation_lines,
        "strongest_deployable": strongest,
        "tactical_mix_label": tactical_mix,
        "weakest": (
            {
                "id": weakest_card.get("id"),
                "display_name": weakest_card.get("display_name"),
            }
            if weakest_card
            else None
        ),
        "marginal_instruction": marginal,
        "do_not_allocate_now": [
            c.get("display_name") for c in cards if c.get("gate_status") == "PAUSED"
        ],
        "note": (
            "Research-only weights · backtest sleeves · not live track record · "
            "cap applies when regime stale or execution offline"
        ),
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
                "model_stance_label": c.get("model_stance_label") or _model_stance_label(c.get("deployability") or ""),
                "evidence_badge": (c.get("evidence_quality") or {}).get("badge")
                or c.get("evidence_badge"),
                "live_trades_count": (c.get("evidence_quality") or {}).get("live_trades_count", 0),
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
    """What to monitor across sleeves — structured trigger rows."""
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
                "trigger": f"{closest.get('display_name')} gate → ACTIVE",
                "current_value": f"Fit {closest.get('regime_fit')}% · {closest.get('gate_status')}",
                "required_threshold": "Regime fit ≥55% + gate ACTIVE",
                "if_hit": f"Upgrade {closest.get('display_name')} to REDUCED/ACTIVE",
                "if_fail": "Keep OFF · preserve cash reserve",
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
                "trigger": "Capital sleeve drift / rebalance",
                "current_value": controller.get("gate_status") or "—",
                "required_threshold": "Within DD budget + mandate",
                "if_hit": "Maintain target weights · 1R on adds",
                "if_fail": "Cut to REDUCED · raise cash",
            }
        )
    if _is_unknown_regime(regime):
        triggers.append(
            {
                "type": "regime",
                "label": "Regime label stale",
                "detail": "Fund lab regime unknown — align with Today REGIME strip",
                "horizon": "immediate",
                "trigger": "Fund vs Today regime mismatch",
                "current_value": "Fund lab UNKNOWN",
                "required_threshold": "Today regime synced",
                "if_hit": "Re-score sleeve fit vs Today regime",
                "if_fail": "Do not size up until regime resolved",
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
                    "trigger": "New rebalance adds",
                    "current_value": ", ".join(c["adds"][:4]),
                    "required_threshold": "Entry timing + liquidity OK",
                    "if_hit": "Stage basket · confirm execution readiness",
                    "if_fail": "Defer adds · monitor only",
                }
            )
    return triggers[:8]


def enrich_execution_readiness_for_funds(
    execution: Dict[str, Any],
    *,
    cards: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Fund-tab execution layer — explicit closed-loop states."""
    ex = dict(execution or {})
    broker = bool(ex.get("broker_connected"))
    bracket = bool(ex.get("bracket_order_ready"))
    handoff = bool(ex.get("trade_handoff_ready"))
    breaker = bool(ex.get("circuit_breaker"))
    gateway = bool(ex.get("gateway_reachable"))

    rebalance_names = sum(len(c.get("adds") or []) + len(c.get("exits") or []) for c in cards)
    estimated_turnover_pct = min(35.0, round(rebalance_names * 2.5, 1))
    estimated_cash_impact_pct = min(25.0, round(estimated_turnover_pct * 0.55, 1))

    if breaker:
        state = "broker_blocked"
        state_label = "Broker blocked — circuit breaker"
    elif handoff and broker:
        state = "basket_ready"
        state_label = "Basket ready — IBKR handoff"
    elif broker and gateway:
        state = "paper_handoff_ready"
        state_label = "Paper handoff ready — confirm basket"
    else:
        state = "analysis_only"
        state_label = "Analysis only — no broker handoff"

    ex.update(
        {
            "execution_state": state,
            "execution_state_label": state_label,
            "can_push_ibkr": broker and not breaker,
            "can_push_ibkr_label": "Yes" if broker and not breaker else "No",
            "order_basket_ready": rebalance_names > 0 and broker,
            "order_basket_ready_label": (
                f"Yes · ~{rebalance_names} name(s)" if rebalance_names and broker else "No"
            ),
            "bracket_compatible": bracket,
            "bracket_compatible_label": "Yes" if bracket else "No — manual stops",
            "estimated_turnover_pct": estimated_turnover_pct,
            "estimated_cash_impact_pct": estimated_cash_impact_pct,
            "readiness_label": state_label,
        }
    )
    return ex


def build_sleeve_allocator_action(card: Dict[str, Any]) -> Dict[str, Any]:
    gs = (card.get("gate_status") or "NO_DATA").upper()
    if gs == "ACTIVE":
        action = "HOLD"
    elif gs == "REDUCED":
        action = "ADD"
    elif gs == "PAUSED":
        action = "OFF"
    else:
        action = "OFF"
    return {
        "action": action,
        "upgrade_condition": card.get("upgrade_trigger") or card.get("next_trigger") or "—",
        "cut_condition": (
            "VIX >28 or regime RISK_OFF → cut to REDUCED/OFF"
            if gs in ("ACTIVE", "REDUCED")
            else "Remain OFF until fit ≥55%"
        ),
    }


def build_consensus_matrix(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-sleeve ticker preference — consensus vs conflict."""
    by_sleeve: List[Dict[str, Any]] = []
    ticker_sleeves: Dict[str, List[str]] = {}
    for c in cards:
        holdings = (c.get("holdings") or [])[:3]
        tickers = [h.get("ticker") for h in holdings if h.get("ticker")]
        short = (c.get("display_name") or c.get("id") or "?").split()[0]
        by_sleeve.append({"sleeve": short, "top_tickers": tickers, "stance": c.get("stance")})
        for t in tickers:
            ticker_sleeves.setdefault(t.upper(), []).append(short)

    consensus = [t for t, sleeves in ticker_sleeves.items() if len(sleeves) >= 2]
    conflicts: List[str] = []
    growth = next((c for c in cards if c.get("id") == "LEADER_MOMENTUM"), None)
    defense = next((c for c in cards if c.get("id") == "TACTICAL_DEF"), None)
    if growth and defense:
        g_top = [h.get("ticker") for h in (growth.get("holdings") or [])[:2]]
        d_top = [h.get("ticker") for h in (defense.get("holdings") or [])[:2]
                 if h.get("ticker") not in g_top]
        if g_top and d_top:
            conflicts.append(
                f"{growth.get('display_name', 'Leader').split()[0]} prefers "
                f"{', '.join(g_top[:2])} vs "
                f"{defense.get('display_name', 'Tactical').split()[0]} prefers "
                f"{', '.join(d_top[:2])}"
            )

    return {
        "by_sleeve": by_sleeve,
        "consensus_tickers": consensus[:5],
        "consensus_label": ", ".join(consensus[:3]) if consensus else "none",
        "conflicts": conflicts,
        "conflict_theme": "growth vs defense" if conflicts else "aligned",
    }


def build_strength_strips(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Split strongest live deployable vs strongest research-only sleeve."""
    deployable = [c for c in cards if c.get("gate_status") in ("ACTIVE", "REDUCED")]
    research = [c for c in cards if c.get("gate_status") in ("PAUSED", "NO_DATA")]
    live_best = max(deployable, key=lambda c: c.get("regime_fit") or 0) if deployable else None
    research_best = max(
        research,
        key=lambda c: (c.get("excess_return_pct") or 0, c.get("regime_fit") or 0),
    ) if research else None
    return {
        "strongest_live": (
            {
                "id": live_best.get("id"),
                "display_name": live_best.get("display_name"),
                "gate_status": live_best.get("gate_status"),
                "regime_fit": live_best.get("regime_fit"),
                "label": f"{live_best.get('display_name')} · fit {live_best.get('regime_fit')}%",
            }
            if live_best
            else None
        ),
        "strongest_research": (
            {
                "id": research_best.get("id"),
                "display_name": research_best.get("display_name"),
                "excess_return_pct": research_best.get("excess_return_pct"),
                "label": (
                    f"{research_best.get('display_name')} · "
                    f"α {(research_best.get('excess_return_pct') or 0):+.1f}% backtest"
                ),
            }
            if research_best
            else None
        ),
    }


def build_fund_console_payload(
    *,
    cards: List[Dict[str, Any]],
    regime: str,
    benchmark: str,
    execution_readiness: Optional[Dict[str, Any]] = None,
    market_regime_label: str = "",
    today_trend: str = "",
    today_tradeability: str = "",
    fund_lab_sync_ts: Optional[float] = None,
    period: str = "1y",
    benchmark_return_pct: float = 0.0,
    tradeability: str = "",
    best_action_liner: str = "",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    system_truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full fund tab payload — research lab with optional allocation lock."""
    regime_ctx = resolve_fund_regime(
        sleeve_regime=regime,
        today_trend=today_trend or market_regime_label.split("·")[0].strip(),
        today_tradeability=today_tradeability or (
            market_regime_label.split("·")[1].strip() if "·" in market_regime_label else ""
        ),
        fund_lab_sync_ts=fund_lab_sync_ts,
    )
    regime_resolved = regime_ctx["regime"]
    regime_display = regime_ctx["regime_display"]
    regime_stale = bool(regime_ctx.get("regime_stale"))
    execution = enrich_execution_readiness_for_funds(
        execution_readiness or {},
        cards=cards,
    )
    allocation = build_allocation_recommendation(
        cards,
        regime_resolved,
        regime_stale=regime_stale,
        execution_ready=str(execution.get("execution_state") or "") in (
            "basket_ready",
            "paper_handoff_ready",
        )
        and bool(execution.get("trade_handoff_ready")),
    )
    funds_mode = resolve_funds_mode(
        execution_readiness=execution,
        tradeability=tradeability,
        cards=cards,
        system_truth=system_truth,
        allocation=allocation,
    )
    research_only_mode = bool(funds_mode.get("research_only_mode"))
    enriched = [
        enrich_fund_card(
            c,
            regime_resolved,
            period=period,
            benchmark_return_pct=benchmark_return_pct,
            research_only_mode=research_only_mode,
        )
        for c in cards
    ]
    alloc_weights = allocation.get("weights") or []
    for c in enriched:
        c["_alloc_weights"] = alloc_weights
    comparison = build_comparison_table(enriched)
    controller = next((c for c in enriched if c.get("controls_capital")), None)
    allocator_decision = build_allocator_decision_strip(
        enriched,
        regime_display=regime_display,
        tradeability=tradeability,
        best_action_liner=best_action_liner,
        benchmark_return_pct=benchmark_return_pct,
        regime_stale=regime_stale,
        execution_readiness=execution,
    )
    from src.services.decision_bar import bar_from_funds

    decision_bar = bar_from_funds(
        allocator_decision,
        active_sleeve=(controller or {}).get("display_name"),
        execution_readiness=execution,
        regime_stale=regime_stale,
    )
    strength_strips = build_strength_strips(enriched)
    allocator_truth = build_allocator_truth_strip(
        enriched,
        allocator_decision=allocator_decision,
        execution_readiness=execution,
        regime_stale=regime_stale,
    )
    if research_only_mode:
        allocator_truth["live_eligible_capital_pct"] = 0
        allocator_truth["max_capital_allowed"] = "0%"
        band = funds_mode.get("theoretical_model_band")
        if band:
            allocator_truth["theoretical_model_band_note"] = (
                f"Theoretical model band: {band} if validation later passes"
            )
    investable_now = build_investable_now_zone(
        regime_ctx=regime_ctx,
        allocator_decision=allocator_decision,
        allocator_truth=allocator_truth,
        allocation=allocation,
        execution_readiness=execution,
        strength_strips=strength_strips,
    )
    funds_first_screen = build_funds_first_screen(
        funds_mode=funds_mode,
        index_posture=None,
        strength_strips=strength_strips,
        cards=enriched,
        system_truth=system_truth,
    )
    console_payload = {
        "title": FUNDS_RESEARCH_LAB_TITLE,
        "research_lab_title": FUNDS_RESEARCH_LAB_TITLE,
        "funds_mode": funds_mode,
        "funds_first_screen": funds_first_screen,
        "live_allocation_eligible": funds_mode.get("live_allocation_eligible", 0),
        "allocation_authority": funds_mode.get("allocation_authority", "none"),
        "research_only_mode": research_only_mode,
        "guardrail": FUNDS_GUARDRAIL,
        "regime": regime_resolved,
        "regime_display": regime_display,
        "regime_source": regime_ctx["regime_source"],
        "regime_note": regime_ctx["regime_note"],
        "regime_stale_note": regime_ctx.get("regime_stale_note"),
        "regime_stale": regime_stale,
        "regime_sync_age_min": regime_ctx.get("regime_sync_age_min"),
        "using_today_fallback": regime_ctx.get("using_today_fallback"),
        "today_regime_label": regime_ctx.get("today_regime_label"),
        "benchmark": benchmark,
        "benchmark_return_pct": benchmark_return_pct,
        "period": period,
        "allocator_decision": allocator_decision,
        "allocator_truth_strip": allocator_truth,
        "investable_now": investable_now,
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
        "consensus_matrix": build_consensus_matrix(enriched),
        "strength_strips": strength_strips,
        "research_lab": {
            "sleeve_id": (controller or {}).get("id"),
            "display_name": (controller or {}).get("display_name"),
            "stance": (controller or {}).get("stance"),
            "mode": (controller or {}).get("mode"),
            "controls_capital": bool((controller or {}).get("controls_capital")),
            "manager_box": (controller or {}).get("manager_box"),
        },
        "active_manager": {
            "sleeve_id": (controller or {}).get("id"),
            "display_name": (controller or {}).get("display_name"),
            "stance": (controller or {}).get("stance"),
            "mode": (controller or {}).get("mode"),
            "controls_capital": bool((controller or {}).get("controls_capital")),
            "manager_box": (controller or {}).get("manager_box"),
        },
        "execution_readiness": execution,
        "evidence_note": "All sleeves: model_backtest · 1y gross · not live track record",
        "count": len(enriched),
    }
    from src.services.index_fund_judgment import enrich_funds_console_index_layer

    return enrich_funds_console_index_layer(
        console_payload,
        benchmark=benchmark,
    )
