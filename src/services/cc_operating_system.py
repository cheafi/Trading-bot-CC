"""
CC Operating System — institutional operator intelligence orchestrator.

Aggregates regime, opportunity, curve, capital, execution, portfolio, event,
automation, and AI modules. Preserves strict authority model throughout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.cc_book_bridge import (
    load_live_strategy_health,
    normalize_portfolio_positions,
    resolve_curve_inputs_for_os,
)
from src.services.cc_capital_control import build_capital_control_context
from src.services.cc_curve_governance import build_curve_governance_context
from src.services.cc_event_intel import build_event_intel_bundle
from src.services.cc_execution_console import build_execution_console
from src.services.cc_opportunity_engine import (
    build_opportunity_pipeline_summary,
    enrich_opportunity_quality_rows,
)
from src.services.cc_portfolio_intel import build_portfolio_intel_context
from src.services.cc_regime_engine import build_advanced_regime_stack
from src.services.cc_tracker_wave import (
    TRACKER_FEATURE_REGISTRY,
    build_tier1_live_bundle,
    get_feature,
)
from src.services.signal_provenance import (
    SIGNAL_CC_OPERATING_SYSTEM,
    build_provenance_envelope,
    may_authorize_deploy,
)

# Extended groups H–I + pipeline / research overlays
GROUP_EVENT_INTEL = "event_intelligence"
GROUP_PIPELINE = "idea_pipeline"
GROUP_INDEX_OVERLAY = "index_investing_overlay"

TOP_10_BUILD_PRIORITY = [
    "cost_adjusted_ranker",
    "monitor_to_upgrade",
    "drawdown_sizer",
    "execution_analytics",
    "strategy_curve_health",
    "factor_overlap",
    "event_risk_blocker",
    "daily_operator_briefing",
    "risk_on_off_composite",
    "opportunity_quality_score",
]


def build_cc_operating_system_context(
    *,
    trend: str = "SIDEWAYS",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    narrative: str = "",
    cross_asset: Optional[Dict[str, Any]] = None,
    index_regime_summary: Optional[Dict[str, Any]] = None,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    top5: Optional[List[Dict[str, Any]]] = None,
    monitor_triggers: Optional[List[Dict[str, Any]]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    event_risks: Optional[List[str]] = None,
    drawdown_sizing: Optional[Dict[str, Any]] = None,
    execution_analytics: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    sleeve_summary: Optional[Dict[str, Any]] = None,
    passive_baseline: Optional[Dict[str, Any]] = None,
    safe_automation: Optional[Dict[str, Any]] = None,
    ai_intelligence: Optional[Dict[str, Any]] = None,
    ibkr_connected: bool = False,
    ibkr_fills: Optional[List[Dict[str, Any]]] = None,
    equity_dd_pct: Optional[float] = None,
    deployable_count: int = 0,
    discovery_count: int = 0,
    degraded: bool = False,
    positions: Optional[List[Dict[str, Any]]] = None,
    live_strategy_health: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full CC OS bundle for Today / quant API."""
    nm = list(near_miss or [])
    t5 = list(top5 or [])
    dd_pct = float(equity_dd_pct or 0.0)
    dd_sizing = drawdown_sizing or {}
    book_positions = normalize_portfolio_positions(positions or [])

    live_health = live_strategy_health
    if live_health is None and not degraded:
        live_health = load_live_strategy_health()
    curve_inputs = resolve_curve_inputs_for_os(
        live_health=live_health,
        degraded=degraded,
    )

    regime_stack = build_advanced_regime_stack(
        trend=trend,
        vix=vix,
        breadth=breadth,
        tradeability=tradeability,
        should_trade=should_trade,
        cross_asset=cross_asset,
        sector_leaders=sector_leaders,
        degraded=degraded,
    )

    opp_top = enrich_opportunity_quality_rows(
        t5, tradeability=tradeability, event_risks=event_risks
    )
    opp_nm = enrich_opportunity_quality_rows(
        nm, tradeability=tradeability, event_risks=event_risks
    )

    capital = build_capital_control_context(
        current_dd_pct=dd_pct,
        vix=vix,
        tradeability=tradeability,
        execution_fill_status=(execution_analytics or {}).get("fill_quality", {}).get("status"),
        event_risk_blocked=any(
            h.get("type") == "cluster_blocked_dd" for h in (quant_cluster_hints or [])
        ),
        fallback_or_stale=degraded,
        on_deploy_surface=False,
    )

    curve = build_curve_governance_context(
        sleeve_cards=(sleeve_summary or {}).get("cards"),
        degraded=curve_inputs.get("degraded", degraded),
        sharpe_wf=curve_inputs.get("sharpe_wf", 0.85),
        max_dd_pct=curve_inputs.get("max_dd_pct", 14.5),
        win_rate=curve_inputs.get("win_rate", 0.48),
        n_trades=curve_inputs.get("n_trades", 42),
        expectancy_r=curve_inputs.get("expectancy_r", 0.35),
        live_sharpe=curve_inputs.get("live_sharpe"),
    )
    if live_health:
        curve["live_strategy_health"] = live_health
        curve["data_source"] = "closed_trades_ledger"

    exec_console = build_execution_console(
        ibkr_fills,
        ibkr_connected=ibkr_connected,
        execution_readiness=execution_readiness,
        degraded=degraded,
    )

    portfolio = build_portfolio_intel_context(
        positions=book_positions,
        passive_baseline=passive_baseline,
        sleeve_summary=sleeve_summary,
        degraded=degraded or not book_positions,
    )

    event_intel = build_event_intel_bundle(
        ticker=(t5[0].get("ticker") if t5 else "SPY") or "SPY",
        event_risks=event_risks,
        degraded=degraded,
    )

    pipeline = build_opportunity_pipeline_summary(
        discovery_count=discovery_count,
        near_miss_count=len(nm),
        playbook_count=len(t5),
        deployable_count=deployable_count,
    )

    cost_blocked = any(
        h.get("type") == "cluster_blocked_cost" for h in (quant_cluster_hints or [])
    )
    tier1 = build_tier1_live_bundle(
        tradeability=tradeability,
        execution_analytics=execution_analytics,
        drawdown_sizing=dd_sizing,
        monitor_triggers=monitor_triggers,
        quant_cluster_hints=quant_cluster_hints,
        near_miss_count=len(nm),
        cost_rank_active=not cost_blocked and not degraded,
        degraded=degraded,
        ibkr_connected=ibkr_connected,
        curve_governance=curve,
    )

    module_strips = [
        regime_stack.get("strip_line", ""),
        pipeline.get("label", ""),
        capital.get("strip_line", ""),
        exec_console.get("strip_line", ""),
        portfolio.get("strip_line", ""),
    ]
    os_strip = " · ".join(s for s in module_strips if s)[:280]

    body: Dict[str, Any] = {
        "may_authorize_deploy": False,
        "may_override_board_gate": False,
        "authority_ceiling": "deploy_surface_support",
        "wave": 2,
        "top_10_priority": TOP_10_BUILD_PRIORITY,
        "registry_count": len(TRACKER_FEATURE_REGISTRY),
        "modules": {
            "regime_index": regime_stack,
            "opportunity_quality": {
                "top5_enriched": opp_top,
                "near_miss_enriched": opp_nm,
                "pipeline": pipeline,
                "authority": "research_only",
            },
            "curve_governance": curve,
            "capital_control": capital,
            "execution": exec_console,
            "portfolio_factor": portfolio,
            "event_intelligence": event_intel,
            "automation": safe_automation or {},
            "ai_support": ai_intelligence or {},
        },
        "tier1": tier1,
        "index_regime_summary": index_regime_summary,
        "operator_strip": os_strip + " — CC OS monitor/ops only",
        "index_overlay": {
            "label": "Index investing overlay — passive comparator on Dashboard",
            "passive_baseline": passive_baseline,
        },
        "research_overlays": {
            "multi_timeframe": "RS + dossier confirm layers — research only",
            "intraday_regime": "Ops strip when engine ON — not deploy",
            "overnight_gap": "Discovery context — confirm-only",
            "rejected_signal_learning": "Rejections tab — diagnostic only",
        },
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_CC_OPERATING_SYSTEM,
        source="cc-operating-system",
        as_of=datetime.now(timezone.utc).isoformat(),
        degraded=degraded,
        data_mode="ops_probe" if ibkr_connected and not degraded else "research_only",
        extra=body,
    )


def authority_matrix_entry(feature_id: str) -> Optional[Dict[str, Any]]:
    """Lookup authority metadata for a registry feature."""
    feat = get_feature(feature_id)
    if not feat:
        return None
    return {
        "id": feat["id"],
        "authority_level": feat["authority_level"],
        "can_influence": feat["can_influence"],
        "cannot_influence": feat["cannot_influence"],
        "may_authorize_deploy": False,
    }


def assert_cc_os_no_deploy(payload: Dict[str, Any]) -> None:
    assert payload.get("may_authorize_deploy") is False
    assert may_authorize_deploy(SIGNAL_CC_OPERATING_SYSTEM) is False
    tier1 = payload.get("tier1") or {}
    if tier1:
        assert tier1.get("may_authorize_deploy") is False
