"""
CC Tracker Wave — registry + Tier-1 live console bundle.

All trackers declare authority ceilings explicitly. None may authorize deploy
or override Dashboard / Playbook board gate logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_CC_TRACKER_WAVE,
    build_provenance_envelope,
    may_authorize_deploy,
)

AUTHORITY_RESEARCH = "research_only"
AUTHORITY_CONFIRMATION = "confirmation_only"
AUTHORITY_ALLOCATOR = "allocator_support"
AUTHORITY_OPS = "ops_support"
AUTHORITY_DEPLOY_SUPPORT = "deploy_surface_support"

GROUP_REGIME = "regime_index"
GROUP_OPPORTUNITY = "opportunity_quality"
GROUP_CURVE = "strategy_curve"
GROUP_EXECUTION = "execution"
GROUP_FACTOR = "factor_quant"
GROUP_AUTOMATION = "automation"
GROUP_AI = "ai_support"

TIER_1_IDS = frozenset(
    {
        "cost_adjusted_ranker",
        "strategy_curve_health",
        "drawdown_sizer",
        "monitor_to_upgrade",
        "execution_analytics",
    }
)

TIER_2_IDS = frozenset(
    {
        "sleeve_allocator",
        "factor_overlap",
        "event_risk_downgrade",
        "daily_operator_briefing",
        "post_trade_review",
    }
)


def _feature(
    feature_id: str,
    name: str,
    purpose: str,
    surface: str,
    authority: str,
    can_influence: str,
    cannot_influence: str,
    roi: str,
    trust: str,
    group: str,
    tier: int = 3,
) -> Dict[str, Any]:
    return {
        "id": feature_id,
        "name": name,
        "purpose": purpose,
        "surface": surface,
        "authority_level": authority,
        "can_influence": can_influence,
        "cannot_influence": cannot_influence,
        "operator_roi": roi,
        "trust_model": trust,
        "group": group,
        "tier": tier,
        "may_authorize_deploy": False,
        "may_override_board_gate": False,
    }


TRACKER_FEATURE_REGISTRY: List[Dict[str, Any]] = [
    # A — Regime / index
    _feature(
        "vix_term_structure",
        "VIX term structure tracker",
        "Spot VIX proxy for contango / backwardation posture",
        "Dashboard (collapsed), Discovery",
        AUTHORITY_RESEARCH,
        "Regime filter, risk posture copy",
        "Deploy permission, WAIT override",
        "Faster risk-on/off context without false deploy cues",
        "Labeled regime_filter; degraded when futures feed absent",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "breadth_thrust_decay",
        "Breadth thrust / decay tracker",
        "Participation expansion or decay vs index trend",
        "Dashboard, Command",
        AUTHORITY_RESEARCH,
        "Board narrative, monitor triggers",
        "Tradeability upgrade alone",
        "Surfaces narrow vs broad market before sizing",
        "MOCK/DEGRADED when breadth synthetic",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "sector_leadership_rotation",
        "Sector leadership rotation tracker",
        "Rotating sector leaders vs laggards",
        "Dashboard, Funds, Discovery",
        AUTHORITY_RESEARCH,
        "Sleeve tilt hints, watchlist context",
        "Deploy chips on research tabs",
        "Aligns monitors with where flow concentrates",
        "Confirm-only labels on non-deploy surfaces",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "index_trend_state",
        "SPY / QQQ / IWM trend-state tracker",
        "Multi-index trend alignment",
        "Dashboard, RS",
        AUTHORITY_RESEARCH,
        "Regime stack, RS confirmation",
        "Authorize TRADE alone",
        "Reduces single-index blind spots",
        "Index regime envelope — monitor_only",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "risk_on_off_composite",
        "Risk-on / risk-off composite tracker",
        "Composite posture from vol, breadth, trend",
        "Dashboard, Command",
        AUTHORITY_RESEARCH,
        "Allocator stance copy, restraint hints",
        "Board gate bypass",
        "One-line posture for PM triage",
        "Never sets should_trade without board",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "vol_compression_expansion",
        "Volatility compression / expansion tracker",
        "VIX band transitions",
        "Dashboard, Dossier",
        AUTHORITY_CONFIRMATION,
        "Event-risk downgrade, sizing humility",
        "Deploy from vol alone",
        "Flags breakout vs fake-breakout regimes",
        "Downgrade-only on stressed vol",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "defensives_vs_growth",
        "Defensives-vs-growth relative tracker",
        "Style rotation within factor regime block",
        "Funds, Dashboard",
        AUTHORITY_RESEARCH,
        "Sleeve research, theme saturation context",
        "Trade route selection",
        "Explains leadership skew without trade signals",
        "Research-only factor block",
        GROUP_REGIME,
        3,
    ),
    _feature(
        "macro_pressure_rates_dollar_oil",
        "Rates / dollar / oil macro pressure tracker",
        "Cross-asset pressure strip",
        "Command, Dashboard (collapsed)",
        AUTHORITY_RESEARCH,
        "Macro narrative, event-risk context",
        "Deploy authority",
        "Macro headwinds visible before entry",
        "Collapsed by default — not trade-authoritative",
        GROUP_REGIME,
        3,
    ),
    # B — Opportunity quality
    _feature(
        "cost_adjusted_ranker",
        "Edge-after-cost tracker",
        "Net edge after spread/turnover burden for sort hints",
        "Playbook, Dashboard, Discovery, Dossier",
        AUTHORITY_RESEARCH,
        "Row ranking, demotion labels",
        "WAIT override, deploy permission",
        "Stops chasing raw score that dies after TCA",
        "may_override_wait=False; downgrade-only demotion",
        GROUP_OPPORTUNITY,
        1,
    ),
    _feature(
        "monitor_to_upgrade",
        "Monitor-to-upgrade conversion tracker",
        "Near-miss gap tracking vs prior board snapshot",
        "Dashboard mission panel, Playbook",
        AUTHORITY_DEPLOY_SUPPORT,
        "Upgrade watch queue, monitor triggers",
        "Auto-deploy, gate bypass",
        "Converts watch time into structured upgrade path",
        "Explicit not-deploy copy on gap alerts",
        GROUP_OPPORTUNITY,
        1,
    ),
    _feature(
        "false_breakout",
        "False-breakout tracker",
        "Follow-through failure heuristics on extended setups",
        "Discovery, Dossier",
        AUTHORITY_CONFIRMATION,
        "Downgrade urgency, avoid-entry hints",
        "Veto board TRADE alone",
        "Reduces chase entries after weak follow-through",
        "Confirm-only downgrade",
        GROUP_OPPORTUNITY,
        2,
    ),
    _feature(
        "setup_freshness",
        "Setup freshness tracker",
        "Age of signal vs decay curve",
        "Playbook, Dossier",
        AUTHORITY_RESEARCH,
        "Strategy decay line, sort tie-break",
        "Deploy from freshness alone",
        "Surfaces stale setups before dossier drill",
        "Tied to strategy validity — research only",
        GROUP_OPPORTUNITY,
        2,
    ),
    _feature(
        "opportunity_decay_timer",
        "Opportunity decay timer",
        "Time-to-decay for ranked setups",
        "Playbook",
        AUTHORITY_RESEARCH,
        "Monitor horizon labels",
        "Execution timing authority",
        "Forces recheck before stale entries",
        "No auto-cancel or auto-order",
        GROUP_OPPORTUNITY,
        2,
    ),
    _feature(
        "leadership_persistence",
        "Leadership persistence tracker",
        "Sector/theme leader tenure",
        "Funds, Discovery",
        AUTHORITY_RESEARCH,
        "Theme saturation, crowding context",
        "New deploy signals",
        "Distinguishes durable vs one-day leaders",
        "Research labels only",
        GROUP_OPPORTUNITY,
        3,
    ),
    _feature(
        "follow_through_quality",
        "Follow-through quality tracker",
        "Volume/price follow-through score",
        "Dossier, Discovery",
        AUTHORITY_CONFIRMATION,
        "Confirmation evidence tier",
        "Board gate replacement",
        "Upgrade watch quality filter",
        "Confirm-only — not deploy chip",
        GROUP_OPPORTUNITY,
        2,
    ),
    _feature(
        "event_risk_blocker",
        "Event-risk blocker tracker",
        "Earnings/macro event proximity downgrade",
        "Dashboard, Dossier, Playbook",
        AUTHORITY_CONFIRMATION,
        "Downgrade-only event flags",
        "Upgrade WAIT to TRADE",
        "Blocks accidental pre-event sizing",
        "downgrade_only=True in provenance",
        GROUP_OPPORTUNITY,
        2,
    ),
    _feature(
        "crowding_theme_saturation",
        "Crowding / theme saturation tracker",
        "Concentration in hot themes",
        "Funds, Command",
        AUTHORITY_RESEARCH,
        "Allocator research, avoid crowding copy",
        "Trade authorization",
        "Prevents pile-on into crowded themes",
        "Allocator-support not deploy",
        GROUP_OPPORTUNITY,
        3,
    ),
    # C — Strategy curve / sleeve
    _feature(
        "strategy_curve_health",
        "Strategy curve health console",
        "Walk-forward Sharpe, DD, expectancy regime filters",
        "Backtest Lab, Funds",
        AUTHORITY_RESEARCH,
        "Pause/reduce/restore research stance",
        "Deploy from curve alone",
        "Governance view before live capital",
        "deploy_from_curve_alone=False; backtest_not_live_edge",
        GROUP_CURVE,
        1,
    ),
    _feature(
        "rolling_sharpe",
        "Rolling Sharpe tracker",
        "WF window Sharpe trend",
        "Backtest Lab",
        AUTHORITY_RESEARCH,
        "Curve health tier",
        "Live sizing authority",
        "Detects edge erosion early",
        "Historical simulation disclaimer",
        GROUP_CURVE,
        2,
    ),
    _feature(
        "rolling_drawdown",
        "Rolling drawdown tracker",
        "Max DD across WF windows",
        "Backtest Lab, Portfolio",
        AUTHORITY_RESEARCH,
        "DD regime labels, sizer hints",
        "Deploy permission",
        "Links simulated pain to live budget",
        "Research + allocator support only",
        GROUP_CURVE,
        1,
    ),
    _feature(
        "drawdown_sizer",
        "Drawdown-aware sizing support",
        "Book DD → template multiplier",
        "Portfolio, Dashboard (support)",
        AUTHORITY_RESEARCH,
        "Template reduction, restore hints",
        "Deploy, sizing authority on stale/fallback",
        "Automatic humility when book heat high",
        "Blocked on research_only/fallback_or_stale",
        GROUP_CURVE,
        1,
    ),
    _feature(
        "live_vs_backtest_divergence",
        "Live-vs-backtest divergence tracker",
        "Paper/live vs WF expectancy gap",
        "Funds, Ops",
        AUTHORITY_RESEARCH,
        "Validity downgrade hints",
        "Trust backtest for deploy",
        "Surfaces overfit before capital add",
        "Explicit divergence label",
        GROUP_CURVE,
        2,
    ),
    _feature(
        "sleeve_capital_efficiency",
        "Sleeve capital efficiency tracker",
        "Return per unit risk by sleeve",
        "Funds",
        AUTHORITY_ALLOCATOR,
        "Hypothetical allocation research",
        "Live rebalance authority",
        "Prioritizes sleeves with better efficiency",
        "Hypothetical % framing preserved",
        GROUP_CURVE,
        2,
    ),
    # D — Execution
    _feature(
        "execution_analytics",
        "Execution analytics console",
        "Latency, slippage, fill quality from session fills",
        "Dashboard (ops strip), IBKR/Ops",
        AUTHORITY_OPS,
        "Post-trade review, urgency reduction",
        "Deploy, broker readiness claims",
        "Honest TCA even before full automation",
        "Stub vs live sample_state; authorizes_execution=False",
        GROUP_EXECUTION,
        1,
    ),
    _feature(
        "signal_to_order_latency",
        "Signal-to-order latency tracker",
        "Board-to-order timing",
        "Ops, IBKR",
        AUTHORITY_OPS,
        "Ops diagnostics",
        "Trade signals",
        "Finds workflow friction",
        "Ops support only",
        GROUP_EXECUTION,
        2,
    ),
    _feature(
        "slippage_vs_arrival",
        "Slippage vs arrival tracker",
        "Implementation shortfall vs decision price",
        "Ops, post-trade review",
        AUTHORITY_OPS,
        "Size/template feedback",
        "Edge claims",
        "Quantifies real execution tax",
        "Insufficient sample → unknown status",
        GROUP_EXECUTION,
        2,
    ),
    _feature(
        "partial_fill_tracker",
        "Partial-fill tracker",
        "Partial fill rate session stats",
        "IBKR/Ops",
        AUTHORITY_OPS,
        "Algo choice hints",
        "Auto-replace orders",
        "Informs algo selection research",
        "No hidden order automation",
        GROUP_EXECUTION,
        2,
    ),
    # E — Factor / quant
    _feature(
        "factor_overlap",
        "Factor overlap tracker",
        "Cross-sleeve correlation / overlap",
        "Portfolio, Funds, Backtest",
        AUTHORITY_RESEARCH,
        "Concentration warnings",
        "Standalone trade signals",
        "Prevents accidental factor stacking",
        "Research interpretation only",
        GROUP_FACTOR,
        2,
    ),
    _feature(
        "beta_exposure",
        "Beta exposure tracker",
        "Book beta vs benchmark",
        "Portfolio, Dashboard",
        AUTHORITY_RESEARCH,
        "Risk interpretation",
        "Deploy gate",
        "Macro shock preparedness",
        "Not a trade trigger",
        GROUP_FACTOR,
        3,
    ),
    _feature(
        "liquidity_capacity",
        "Liquidity / capacity pressure tracker",
        "ADV vs intended size",
        "Dossier, Portfolio",
        AUTHORITY_CONFIRMATION,
        "Capacity downgrade hints",
        "Authorize size",
        "Avoids moving the market on illiquid names",
        "Confirm-only capacity band",
        GROUP_FACTOR,
        2,
    ),
    # F — Automation
    _feature(
        "near_miss_auto_recheck",
        "Near-miss auto-recheck",
        "Scheduled recheck hints for stale near-miss rows",
        "Dashboard support",
        AUTHORITY_DEPLOY_SUPPORT,
        "Monitor queue refresh suggestions",
        "Auto-deploy, hidden orders",
        "Operator leverage without bypass",
        "monitor_only=True; may_authorize_deploy=False",
        GROUP_AUTOMATION,
        3,
    ),
    _feature(
        "monitor_upgrade_alert_engine",
        "Monitor upgrade alert engine",
        "Gap-improved near-miss alerts",
        "Dashboard mission panel",
        AUTHORITY_DEPLOY_SUPPORT,
        "Upgrade watch notifications",
        "Gate override",
        "Surfaces when watch names tighten gaps",
        "Explicit not-deploy on alerts",
        GROUP_AUTOMATION,
        1,
    ),
    _feature(
        "daily_operator_briefing",
        "Daily operator briefing generator",
        "Structured AM briefing from board state",
        "Dashboard, Command",
        AUTHORITY_DEPLOY_SUPPORT,
        "Triage order, safe-action list",
        "Deploy decisions",
        "Cuts morning scatter",
        "Briefing ≠ board decision",
        GROUP_AUTOMATION,
        2,
    ),
    _feature(
        "strategy_pause_restore_automation",
        "Strategy pause / reduce / restore automation support",
        "Research stance suggestions from curve + DD",
        "Backtest Lab, Funds",
        AUTHORITY_RESEARCH,
        "Pause/reduce copy in research",
        "Live auto-pause without operator",
        "Governance workflow acceleration",
        "Operator must confirm any live change",
        GROUP_AUTOMATION,
        2,
    ),
    # G — AI support
    _feature(
        "ai_contradiction_detector",
        "Contradiction detector",
        "Flags conflicting signals across layers",
        "Dossier, Command",
        AUTHORITY_RESEARCH,
        "Triage, explainability",
        "Deploy authority",
        "Prevents silent signal conflicts",
        "AI explanatory — not primary authority",
        GROUP_AI,
        3,
    ),
    _feature(
        "ai_anomalous_move_explainer",
        "Anomalous move explainer",
        "Context for unusual price moves",
        "Dossier, Discovery",
        AUTHORITY_RESEARCH,
        "Narrative triage",
        "Trade triggers",
        "Faster sense-making on spikes",
        "Degraded AI labeled MOCK",
        GROUP_AI,
        3,
    ),
    _feature(
        "ai_post_trade_review",
        "Post-trade review AI",
        "Session fill / decision retrospective",
        "Ops, IBKR",
        AUTHORITY_OPS,
        "Learning loop copy",
        "Auto-correct positions",
        "Closes feedback loop safely",
        "Ops support — no order authority",
        GROUP_AI,
        2,
    ),
    _feature(
        "signal_provenance_explainer",
        "Signal provenance explainer",
        "Why a row ranked / flagged",
        "Playbook, Dossier",
        AUTHORITY_RESEARCH,
        "Trust / audit trail",
        "Alter board gate",
        "Preserves CC trust model",
        "Tied to signal_provenance envelopes",
        GROUP_AI,
        2,
    ),
]

_REGISTRY_BY_ID = {f["id"]: f for f in TRACKER_FEATURE_REGISTRY}


def get_feature(feature_id: str) -> Optional[Dict[str, Any]]:
    return _REGISTRY_BY_ID.get(feature_id)


def features_for_group(group: str) -> List[Dict[str, Any]]:
    return [f for f in TRACKER_FEATURE_REGISTRY if f["group"] == group]


def features_for_tier(tier: int) -> List[Dict[str, Any]]:
    return [f for f in TRACKER_FEATURE_REGISTRY if f["tier"] == tier]


def build_tier1_live_bundle(
    *,
    tradeability: str = "WAIT",
    execution_analytics: Optional[Dict[str, Any]] = None,
    drawdown_sizing: Optional[Dict[str, Any]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    near_miss_count: int = 0,
    cost_rank_active: bool = True,
    degraded: bool = False,
    ibkr_connected: bool = False,
    curve_governance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate Tier-1 tracker state for Today / quant API — no deploy authority."""
    exec_a = execution_analytics or {}
    sizing = drawdown_sizing or {}
    triggers = list(monitor_triggers or [])
    hints = list(quant_cluster_hints or [])

    upgrade_alerts = [
        t for t in triggers if t.get("type") == "monitor_upgrade_alert"
    ]
    exec_sample = exec_a.get("sample_state") or "insufficient_sample"
    exec_live = exec_sample == "live_sample" and ibkr_connected and not degraded

    curve = curve_governance or {}
    curve_metrics = curve.get("curve_metrics") or {}
    curve_health_state = curve_metrics.get("health_state") or curve.get("sleeve_governance", {}).get("health_state")
    curve_label = (
        curve_metrics.get("health_label")
        or curve.get("strip_line")
        or "Backtest Lab / quant API — research only"
    )
    curve_live = bool(curve.get("live_strategy_health") or curve.get("data_source") == "closed_trades_ledger")

    tier1_status = {
        "cost_adjusted_ranker": {
            "active": cost_rank_active and not degraded,
            "label": "Ranking hint active" if cost_rank_active else "Degraded — sort humility",
            "authority": AUTHORITY_RESEARCH,
        },
        "strategy_curve_health": {
            "active": bool(curve_metrics) or curve_live,
            "health_state": curve_health_state,
            "label": curve_label[:120] if curve_label else "Curve research only",
            "live_ledger": curve_live,
            "authority": AUTHORITY_RESEARCH,
        },
        "drawdown_sizer": {
            "active": bool(sizing.get("sizing_mode") and sizing.get("sizing_mode") != "blocked"),
            "mode": sizing.get("sizing_mode", "blocked"),
            "label": sizing.get("sizing_label", "DD sizing unavailable"),
            "authority": AUTHORITY_RESEARCH,
        },
        "monitor_to_upgrade": {
            "active": near_miss_count > 0 or len(upgrade_alerts) > 0,
            "near_miss_count": near_miss_count,
            "upgrade_alert_count": len(upgrade_alerts),
            "authority": AUTHORITY_DEPLOY_SUPPORT,
        },
        "execution_analytics": {
            "active": exec_live or exec_a.get("orders_sampled", 0) > 0,
            "sample_state": exec_sample,
            "orders_sampled": exec_a.get("orders_sampled", 0),
            "fill_status": (exec_a.get("fill_quality") or {}).get("status"),
            "authority": AUTHORITY_OPS,
        },
    }

    strip_lines: List[str] = []
    if degraded:
        strip_lines.append("Tracker wave MOCK/DEGRADED — monitor only")
    if tier1_status["monitor_to_upgrade"]["active"]:
        strip_lines.append(
            f"Upgrade watch: {near_miss_count} near-miss · {len(upgrade_alerts)} gap alerts"
        )
    ch = tier1_status.get("strategy_curve_health") or {}
    if ch.get("live_ledger"):
        strip_lines.append(f"Curve: live ledger — {ch.get('label', '')[:60]}")
    elif ch.get("active"):
        strip_lines.append(f"Curve: {ch.get('label', 'research only')[:60]}")
    if sizing.get("sizing_mode") and sizing.get("sizing_mode") != "blocked":
        strip_lines.append(
            f"DD sizing: {sizing.get('sizing_label', '')} — template only"
        )
    elif sizing.get("sizing_mode") == "blocked":
        strip_lines.append("DD sizing blocked — stale/fallback/research")
    if exec_live:
        strip_lines.append(
            f"Execution: live sample n={exec_a.get('orders_sampled', 0)} — ops context"
        )
    elif exec_a.get("orders_sampled", 0) > 0:
        strip_lines.append("Execution: insufficient sample — monitor only")
    else:
        strip_lines.append("Execution: no fills / disconnected — not broker-ready")

    cost_hint = next((h for h in hints if h.get("type") == "cluster_blocked_cost"), None)
    if cost_hint:
        strip_lines.append(str(cost_hint.get("detail") or "Cost drag cluster"))

    return {
        "tier": 1,
        "tradeability": str(tradeability or "").upper(),
        "degraded": degraded,
        "ibkr_connected": ibkr_connected,
        "tier1_status": tier1_status,
        "strip_lines": strip_lines[:6],
        "strip_line": " · ".join(strip_lines[:3]) if strip_lines else "Tracker wave idle",
        "monitoring_only": True,
        "may_authorize_deploy": False,
        "may_override_board_gate": False,
        "authority_ceiling": AUTHORITY_DEPLOY_SUPPORT,
        "deploy_surfaces_only": ["today", "playbook"],
        "research_surfaces": [
            "discovery",
            "dossier",
            "funds",
            "btlab",
            "command",
            "ops",
            "ibkr",
        ],
    }


def build_tracker_wave_context(
    *,
    tradeability: str = "WAIT",
    execution_analytics: Optional[Dict[str, Any]] = None,
    drawdown_sizing: Optional[Dict[str, Any]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    safe_automation: Optional[Dict[str, Any]] = None,
    degraded: bool = False,
    ibkr_connected: bool = False,
    curve_governance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full tracker wave envelope for API / Today payload."""
    nm = list(near_miss or [])
    tier1 = build_tier1_live_bundle(
        tradeability=tradeability,
        execution_analytics=execution_analytics,
        drawdown_sizing=drawdown_sizing,
        monitor_triggers=monitor_triggers,
        quant_cluster_hints=quant_cluster_hints,
        near_miss_count=len(nm),
        degraded=degraded,
        ibkr_connected=ibkr_connected,
        curve_governance=curve_governance,
    )
    body = {
        "may_authorize_deploy": False,
        "may_override_board_gate": False,
        "registry_count": len(TRACKER_FEATURE_REGISTRY),
        "tier1": tier1,
        "tier2_ids": sorted(TIER_2_IDS),
        "tier3_note": "Regime macro + AI layers staged — registry documented",
        "groups": {
            g: len(features_for_group(g))
            for g in (
                GROUP_REGIME,
                GROUP_OPPORTUNITY,
                GROUP_CURVE,
                GROUP_EXECUTION,
                GROUP_FACTOR,
                GROUP_AUTOMATION,
                GROUP_AI,
            )
        },
        "safe_automation": safe_automation or {},
        "feature_ids_tier1": sorted(TIER_1_IDS),
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_CC_TRACKER_WAVE,
        source="cc-tracker-wave-console",
        as_of=datetime.now(timezone.utc).isoformat(),
        degraded=degraded,
        data_mode="ops_probe" if ibkr_connected and not degraded else "research_only",
        extra=body,
    )


def assert_tracker_wave_no_deploy(payload: Dict[str, Any]) -> None:
    """Regression helper — tracker wave must never grant deploy."""
    assert payload.get("may_authorize_deploy") is False
    assert may_authorize_deploy(SIGNAL_CC_TRACKER_WAVE) is False
    tier1 = (payload.get("tier1") or payload.get("extra", {}).get("tier1") or {})
    if isinstance(tier1, dict):
        assert tier1.get("may_authorize_deploy") is False
        assert tier1.get("may_override_board_gate") is False
