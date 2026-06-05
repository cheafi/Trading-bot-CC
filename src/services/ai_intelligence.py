"""
Deterministic AI intelligence — explanatory / monitor / downgrade only.

No external LLM required for CI. Never grants deploy authority alone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_AI_INTELLIGENCE,
    build_provenance_envelope,
)

REASON_MONITOR_UPGRADE_BLOCKED = "monitor_upgrade_blocked"
REASON_DEPLOY_BLOCKED = "deploy_blocked"
REASON_SLEEVE_REDUCED = "sleeve_reduced"
REASON_COST_DEMOTION = "cost_demotion"
REASON_REGIME_CONFLICT = "regime_conflict"

REASON_COPY: Dict[str, str] = {
    REASON_MONITOR_UPGRADE_BLOCKED: (
        "Monitor upgrade blocked — board gate or tradeability still WAIT; "
        "near-miss rows are attention queue only"
    ),
    REASON_DEPLOY_BLOCKED: (
        "Deploy blocked — page gate, execution path, or degraded data; "
        "quant/algo hints cannot override"
    ),
    REASON_SLEEVE_REDUCED: (
        "Sleeve reduced — allocator headroom constrained; "
        "research template downgrade, not a trade route"
    ),
    REASON_COST_DEMOTION: (
        "Cost demotion — net edge after drag below ranking threshold; "
        "sort demote only, not standalone veto"
    ),
    REASON_REGIME_CONFLICT: (
        "Regime conflict — breadth, index posture, or factor leadership disagree; "
        "filter hint downgrade-only"
    ),
}

CATALYST_NOISE = "noise"
CATALYST_MONITOR = "monitor"
CATALYST_EVENT_RISK = "event_risk"
CATALYST_DOWNGRADE = "downgrade"

CATALYST_LABELS: Dict[str, str] = {
    CATALYST_NOISE: "Headline noise — ignore for sizing",
    CATALYST_MONITOR: "Monitor catalyst — confirm in dossier",
    CATALYST_EVENT_RISK: "Event risk — downgrade urgency",
    CATALYST_DOWNGRADE: "Thesis downgrade — defensive filter",
}


def explain_reason_code(
    code: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Structured reason-code explainer — monitor-only copy."""
    ctx = context or {}
    base = REASON_COPY.get(code, f"Unknown reason ({code}) — monitor context only")
    detail = str(ctx.get("detail") or "").strip()
    message = f"{base} ({detail})" if detail else base
    return {
        "code": code,
        "message": message,
        "ai_explanatory_only": True,
        "deploy_from_ai_alone": False,
        "may_authorize_deploy": False,
    }


def detect_contradictions(
    *,
    market_regime: Optional[Dict[str, Any]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    row: Optional[Dict[str, Any]] = None,
    event_risks: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Breadth vs index, factor vs setup, event vs thesis — heuristic flags."""
    hints: List[Dict[str, Any]] = []
    regime = market_regime or {}
    idx = index_regime or {}
    r = row or {}

    breadth = regime.get("breadth")
    try:
        b = float(breadth) if breadth is not None else None
        if b is not None and b <= 1.0:
            b *= 100.0
    except (TypeError, ValueError):
        b = None

    trend = str(regime.get("trend") or "").upper()
    posture = str(idx.get("posture") or "").lower()
    participation = str((idx.get("breadth_regime") or {}).get("participation") or "")

    if b is not None and trend == "UPTREND" and b < 45:
        hints.append(
            {
                "type": "breadth_vs_index",
                "hint": "Breadth narrow while trend UP — participation filter conflict",
                "severity": "watch",
            }
        )
    if participation == "narrow" and posture in ("risk_on", "normal"):
        hints.append(
            {
                "type": "breadth_vs_index",
                "hint": "Index posture optimistic but breadth narrow — downgrade filter",
                "severity": "watch",
            }
        )

    factor_tags = (idx.get("factor_regime") or {}).get("leadership_tags") or []
    setup = str(r.get("strategy") or r.get("setup_family") or "").lower()
    if "momentum" in factor_tags and setup in ("mean_reversion", "value"):
        hints.append(
            {
                "type": "factor_vs_setup",
                "hint": "Factor leadership favors momentum; setup family diverges",
                "severity": "watch",
            }
        )
    if "min_vol" in factor_tags and setup in ("breakout", "momentum"):
        hints.append(
            {
                "type": "factor_vs_setup",
                "hint": "Stressed factor regime vs aggressive setup — filter caution",
                "severity": "watch",
            }
        )

    thesis_bull = str(r.get("action") or "").upper() in ("TRADE", "PILOT", "BUY")
    events = event_risks or []
    if thesis_bull and events:
        hints.append(
            {
                "type": "event_vs_thesis",
                "hint": f"Event risk present ({events[0][:48]}) while action bullish — confirm-only",
                "severity": "downgrade",
            }
        )

    for h in hints:
        h["ai_explanatory_only"] = True
        h["deploy_from_ai_alone"] = False
    return hints[:4]


def triage_catalyst(
    event: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Rule-based catalyst triage from existing event fields."""
    impact = str(event.get("impact") or event.get("impact_framing") or "").lower()
    credibility = str(event.get("credibility") or event.get("tier") or "medium").lower()
    headline = str(event.get("headline") or event.get("title") or "")[:120]
    tb = str(tradeability or "").upper()

    if impact in ("risk_downgrade", "downgrade", "negative"):
        tier = CATALYST_DOWNGRADE
    elif impact in ("event_risk", "binary", "earnings"):
        tier = CATALYST_EVENT_RISK
    elif credibility in ("low", "rumor", "unverified") or "noise" in impact:
        tier = CATALYST_NOISE
    elif tb == "WAIT":
        tier = CATALYST_MONITOR
    else:
        tier = CATALYST_MONITOR

    return {
        "headline": headline,
        "tier": tier,
        "tier_label": CATALYST_LABELS.get(tier, tier),
        "ai_explanatory_only": True,
        "deploy_from_ai_alone": False,
        "downgrade_only": tier in (CATALYST_DOWNGRADE, CATALYST_EVENT_RISK),
    }


def triage_catalysts_from_events(
    events: Optional[List[Any]],
    *,
    tradeability: str = "",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ev in events or []:
        if isinstance(ev, str):
            ev = {"headline": ev, "impact": "monitor"}
        if isinstance(ev, dict):
            out.append(triage_catalyst(ev, tradeability=tradeability))
    return out[:8]


def detect_watchlist_recurrence(
    *,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    top_ranked: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Near-miss repeat detection from existing monitor data."""
    counts: Dict[str, int] = {}
    sources: Dict[str, List[str]] = {}

    def _bump(ticker: str, source: str) -> None:
        t = str(ticker or "").upper().strip()
        if not t:
            return
        counts[t] = counts.get(t, 0) + 1
        sources.setdefault(t, [])
        if source not in sources[t]:
            sources[t].append(source)

    for nm in near_miss or []:
        if isinstance(nm, dict):
            _bump(nm.get("ticker"), "near_miss")
    for tr in monitor_triggers or []:
        if isinstance(tr, dict) and tr.get("type") == "near_miss":
            label = str(tr.get("label") or "")
            for part in label.replace("—", " ").split():
                if part.isalpha() and len(part) <= 5:
                    _bump(part, "monitor_trigger")
    for row in top_ranked or []:
        if isinstance(row, dict) and str(row.get("action") or "").upper() == "WATCH":
            _bump(row.get("ticker"), "watch_rank")

    recurring: List[Dict[str, Any]] = []
    for tick, n in sorted(counts.items(), key=lambda x: -x[1]):
        if n < 2:
            continue
        recurring.append(
            {
                "ticker": tick,
                "appearances": n,
                "sources": sources.get(tick, []),
                "hint": f"{tick} near-miss recurrence ({n}×) — monitor upgrade layer only",
                "ai_explanatory_only": True,
                "deploy_from_ai_alone": False,
            }
        )
    return recurring[:5]


def build_regime_stack_summary(
    index_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact regime stack for Today strip — monitor-only."""
    idx = index_regime or {}
    blocks = []
    for key in ("vol_regime", "breadth_regime", "factor_regime"):
        blk = idx.get(key)
        if isinstance(blk, dict):
            blocks.append(
                {
                    "block": blk.get("block") or key,
                    "summary": blk.get("summary") or "",
                    "degraded": bool(blk.get("degraded")),
                }
            )
    cross = idx.get("cross_asset") if isinstance(idx.get("cross_asset"), dict) else {}
    return {
        "posture": idx.get("posture"),
        "posture_label": idx.get("posture_label"),
        "blocks": blocks,
        "cross_asset_alignment": cross.get("alignment"),
        "strip_line": idx.get("strip_line") or idx.get("summary") or "",
        "degraded": bool(idx.get("degraded")),
        "monitor_only": True,
        "may_authorize_deploy": False,
    }


def build_allocator_stance(
    *,
    sleeves: Optional[List[Dict[str, Any]]] = None,
    sleeve_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sleeve routing stance for Today — hint only."""
    from src.services.strategy_allocator import build_sleeve_budgets, routing_suggestion

    cards = sleeves
    if not cards and sleeve_summary:
        raw = sleeve_summary.get("cards") or []
        mapped: List[Dict[str, Any]] = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            try:
                fit = float(c.get("regime_fit") or 50)
            except (TypeError, ValueError):
                fit = 50.0
            mapped.append(
                {
                    "id": c.get("id"),
                    "name": c.get("display_name") or c.get("name") or c.get("id"),
                    "budget_pct": float(c.get("budget_pct") or 25),
                    "utilization_pct": round(min(95.0, max(5.0, 100.0 - fit)), 1),
                    "gate_status": c.get("gate_status") or "ACTIVE",
                }
            )
        cards = mapped or None
    budgeted = build_sleeve_budgets(cards)
    route = routing_suggestion(budgeted)
    reduced = [s for s in budgeted if s.get("allocator_state") == "reduced"]
    return {
        "routing": route,
        "strongest": route.get("strongest"),
        "weakest": route.get("weakest"),
        "suggestion": route.get("suggestion"),
        "reduced_sleeve_count": len(reduced),
        "controls_capital": False,
        "deploy_from_allocator_alone": False,
        "monitor_only": True,
    }


def collect_ai_reason_codes(
    *,
    tradeability: str = "WAIT",
    decision_authority: Optional[Dict[str, Any]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    allocator_stance: Optional[Dict[str, Any]] = None,
    scanner_degraded: bool = False,
) -> List[Dict[str, Any]]:
    """Assemble monitor-only reason codes for Today payload."""
    codes: List[Dict[str, Any]] = []
    auth = decision_authority or {}
    tb = str(tradeability or "").upper()

    if tb in ("WAIT", "NO_TRADE") or not auth.get("allows_trade_labels"):
        codes.append(
            explain_reason_code(
                REASON_MONITOR_UPGRADE_BLOCKED,
                context={"detail": f"tradeability={tb}"},
            )
        )
    if scanner_degraded or auth.get("gates_active") or not auth.get("deploy_authority"):
        codes.append(
            explain_reason_code(
                REASON_DEPLOY_BLOCKED,
                context={
                    "detail": "degraded scanner"
                    if scanner_degraded
                    else "board gate inactive"
                },
            )
        )

    alloc = allocator_stance or {}
    if int(alloc.get("reduced_sleeve_count") or 0) > 0:
        codes.append(
            explain_reason_code(
                REASON_SLEEVE_REDUCED,
                context={"detail": alloc.get("suggestion", "")[:80]},
            )
        )

    for hint in quant_cluster_hints or []:
        if not isinstance(hint, dict):
            continue
        if hint.get("type") == "cluster_blocked_cost" or hint.get("cluster") == "blocked-by-cost":
            codes.append(
                explain_reason_code(
                    REASON_COST_DEMOTION,
                    context={"detail": str(hint.get("detail") or "")[:80]},
                )
            )
            break

    idx = index_regime or {}
    posture = str(idx.get("posture") or "")
    breadth_blk = idx.get("breadth_regime") or {}
    if posture in ("stressed", "no_trade_pressure") and breadth_blk.get("participation") == "broad":
        codes.append(
            explain_reason_code(
                REASON_REGIME_CONFLICT,
                context={"detail": "posture stressed vs broad breadth proxy"},
            )
        )

    return codes[:6]


def attach_row_ai_hints(
    rows: List[Dict[str, Any]],
    *,
    market_regime: Optional[Dict[str, Any]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    event_risks: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Playbook row ai_contradiction_hint + net_edge_display."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        raw = r.get("raw_score") or r.get("score")
        net = r.get("net_edge_score") or r.get("net_deploy_score")
        if raw is not None and net is not None:
            try:
                r["net_edge_display"] = (
                    f"Raw {float(raw):.1f} · Net {float(net):.1f} after cost"
                )
            except (TypeError, ValueError):
                pass
        contradictions = detect_contradictions(
            market_regime=market_regime,
            index_regime=index_regime,
            row=r,
            event_risks=event_risks,
        )
        if contradictions:
            r["ai_contradiction_hint"] = contradictions[0].get("hint")
            r["ai_contradiction_hints"] = contradictions
        r["ai_explanatory_only"] = True
        r["deploy_from_ai_alone"] = False
        out.append(r)
    return out


def build_ai_intelligence_for_today(
    *,
    market_regime: Optional[Dict[str, Any]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    decision_authority: Optional[Dict[str, Any]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    top_ranked: Optional[List[Dict[str, Any]]] = None,
    event_risks: Optional[List[Any]] = None,
    sleeve_summary: Optional[Dict[str, Any]] = None,
    scanner_degraded: bool = False,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Full AI intelligence envelope for Today — deterministic/heuristic."""
    regime = market_regime or {}
    tradeability = str(regime.get("tradeability") or "WAIT")
    allocator_stance = build_allocator_stance(sleeve_summary=sleeve_summary)
    regime_stack = build_regime_stack_summary(index_regime)
    reason_codes = collect_ai_reason_codes(
        tradeability=tradeability,
        decision_authority=decision_authority,
        index_regime=index_regime,
        quant_cluster_hints=quant_cluster_hints,
        allocator_stance=allocator_stance,
        scanner_degraded=scanner_degraded,
    )
    catalysts = triage_catalysts_from_events(event_risks, tradeability=tradeability)
    recurrence = detect_watchlist_recurrence(
        near_miss=near_miss,
        monitor_triggers=monitor_triggers,
        top_ranked=top_ranked,
    )
    body = {
        "regime_stack_summary": regime_stack,
        "allocator_stance": allocator_stance,
        "ai_reason_codes": reason_codes,
        "catalyst_triage": catalysts,
        "watchlist_recurrence": recurrence,
        "ai_explanatory_only": True,
        "deploy_from_ai_alone": False,
        "may_authorize_deploy": False,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_AI_INTELLIGENCE,
        source="deterministic-ai-intelligence",
        degraded=degraded or scanner_degraded or bool(index_regime and index_regime.get("degraded")),
        data_mode="research_only",
        extra=body,
    )
