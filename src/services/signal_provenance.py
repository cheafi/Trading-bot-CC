"""
Signal provenance — authority limits per opportunity intelligence type.

Insider / 13F / events / strategy curves inform research surfaces only;
they must never upgrade deploy authority without board + playbook gates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.surface_authority import (
    AUTHORITY_BLOCKED,
    AUTHORITY_CONFIRMATION,
    AUTHORITY_OPS,
    AUTHORITY_RESEARCH,
)

SIGNAL_INSIDER_FORM4 = "insider_form4"
SIGNAL_INSTITUTIONAL_13F = "institutional_13f"
SIGNAL_EVENT_NARRATIVE = "event_narrative"
SIGNAL_STRATEGY_CURVE = "strategy_curve"
SIGNAL_COST_RANK = "cost_adjusted_rank"
SIGNAL_DRAWDOWN_SIZER = "drawdown_sizer"
SIGNAL_EXECUTION_ANALYTICS = "execution_analytics"
SIGNAL_STRATEGY_ALLOCATION = "strategy_allocation"
SIGNAL_FACTOR_EXPOSURE = "factor_exposure"
SIGNAL_STRATEGY_VALIDITY = "strategy_validity"
SIGNAL_INDEX_REGIME = "index_regime"
SIGNAL_EXECUTION_ALGO = "execution_algo_recommendation"
SIGNAL_AI_INTELLIGENCE = "ai_intelligence"
SIGNAL_SIGNAL_COHORT = "signal_cohort"
SIGNAL_REGIME_TIMELINE = "regime_timeline"
SIGNAL_CAPACITY = "capacity_intelligence"

ALL_SIGNAL_TYPES = (
    SIGNAL_INSIDER_FORM4,
    SIGNAL_INSTITUTIONAL_13F,
    SIGNAL_EVENT_NARRATIVE,
    SIGNAL_STRATEGY_CURVE,
    SIGNAL_COST_RANK,
    SIGNAL_DRAWDOWN_SIZER,
    SIGNAL_EXECUTION_ANALYTICS,
    SIGNAL_STRATEGY_ALLOCATION,
    SIGNAL_FACTOR_EXPOSURE,
    SIGNAL_STRATEGY_VALIDITY,
    SIGNAL_INDEX_REGIME,
    SIGNAL_EXECUTION_ALGO,
    SIGNAL_AI_INTELLIGENCE,
    SIGNAL_SIGNAL_COHORT,
    SIGNAL_REGIME_TIMELINE,
    SIGNAL_CAPACITY,
)

# Max authority any single signal may confer (never deploy alone).
_SIGNAL_AUTHORITY_CEILING: Dict[str, str] = {
    SIGNAL_INSIDER_FORM4: AUTHORITY_RESEARCH,
    SIGNAL_INSTITUTIONAL_13F: AUTHORITY_RESEARCH,
    SIGNAL_EVENT_NARRATIVE: AUTHORITY_CONFIRMATION,  # narrative/risk — downgrade only
    SIGNAL_STRATEGY_CURVE: AUTHORITY_RESEARCH,
    SIGNAL_COST_RANK: AUTHORITY_RESEARCH,
    SIGNAL_DRAWDOWN_SIZER: AUTHORITY_RESEARCH,
    SIGNAL_EXECUTION_ANALYTICS: AUTHORITY_OPS,
    SIGNAL_STRATEGY_ALLOCATION: AUTHORITY_RESEARCH,
    SIGNAL_FACTOR_EXPOSURE: AUTHORITY_RESEARCH,
    SIGNAL_STRATEGY_VALIDITY: AUTHORITY_RESEARCH,
    SIGNAL_INDEX_REGIME: AUTHORITY_RESEARCH,
    SIGNAL_EXECUTION_ALGO: AUTHORITY_OPS,
    SIGNAL_AI_INTELLIGENCE: AUTHORITY_RESEARCH,
    SIGNAL_SIGNAL_COHORT: AUTHORITY_RESEARCH,
    SIGNAL_REGIME_TIMELINE: AUTHORITY_RESEARCH,
    SIGNAL_CAPACITY: AUTHORITY_RESEARCH,
}

_SIGNAL_RULES: Dict[str, Dict[str, Any]] = {
    SIGNAL_INSIDER_FORM4: {
        "label": "Form 4 insider",
        "lag_disclosure": "SEC filings lag days–weeks — context only",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_INSTITUTIONAL_13F: {
        "label": "13F institutional",
        "lag_disclosure": "Quarterly 13F — 45+ day lag typical",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_EVENT_NARRATIVE: {
        "label": "Event / news narrative",
        "lag_disclosure": "Headlines cluster — credibility tiered, not triggers",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "downgrade_only": True,
        "monitor_only": True,
    },
    SIGNAL_STRATEGY_CURVE: {
        "label": "Strategy curve health",
        "lag_disclosure": "Walk-forward / paper — not live track record",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_COST_RANK: {
        "label": "Cost-adjusted rank",
        "lag_disclosure": "Heuristic TCA — ranking humility only",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "may_override_wait": False,
        "downgrade_only": True,
        "monitor_only": True,
    },
    SIGNAL_DRAWDOWN_SIZER: {
        "label": "Drawdown budget sizer",
        "lag_disclosure": "Book DD template — blocked on research/confirm-only",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_EXECUTION_ANALYTICS: {
        "label": "Execution analytics",
        "lag_disclosure": "Fill sample — ops context, not edge claim",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_STRATEGY_ALLOCATION: {
        "label": "Strategy allocator",
        "lag_disclosure": "Sleeve budget hints — no live routing",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_FACTOR_EXPOSURE: {
        "label": "Factor exposure",
        "lag_disclosure": "Beta/sector overlap — concentration research",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_STRATEGY_VALIDITY: {
        "label": "Strategy validity",
        "lag_disclosure": "OOS / decay flags — backtest ≠ live edge",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_INDEX_REGIME: {
        "label": "Index regime filter",
        "lag_disclosure": "VIX/breadth/factor proxies — regime filter only",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "downgrade_only": True,
        "monitor_only": True,
    },
    SIGNAL_EXECUTION_ALGO: {
        "label": "Execution algo recommendation",
        "lag_disclosure": "IBKR-style hint — recommendation only, no routing",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_AI_INTELLIGENCE: {
        "label": "AI intelligence (deterministic)",
        "lag_disclosure": "Heuristic explainer — no LLM required for CI",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "downgrade_only": True,
        "monitor_only": True,
    },
    SIGNAL_SIGNAL_COHORT: {
        "label": "Signal cohort tracker",
        "lag_disclosure": "Forward outcomes accrue over days — sample may be thin",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "monitor_only": True,
    },
    SIGNAL_REGIME_TIMELINE: {
        "label": "Market regime timeline",
        "lag_disclosure": "Distribution/follow-through proxies — regime context only",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "downgrade_only": True,
        "monitor_only": True,
    },
    SIGNAL_CAPACITY: {
        "label": "Capacity intelligence",
        "lag_disclosure": "%ADV / impact heuristics — scale humility, not live TCA",
        "may_authorize_deploy": False,
        "may_upgrade_tradeability": False,
        "may_override_wait": False,
        "downgrade_only": True,  # capacity can only demote / shrink, never upgrade
        "monitor_only": True,
    },
}


def quant_authority_can(signal_type: str, action: str) -> bool:
    """Explicit CAN rules — quant signals never grant deploy."""
    _ = action
    return may_authorize_deploy(signal_type)


def quant_authority_cannot(signal_type: str) -> List[str]:
    """Explicit CANNOT rules for quant / algo surfaces."""
    rules = signal_rules(signal_type)
    cannot: List[str] = [
        "authorize_deploy",
        "override_wait",
        "upgrade_tradeability_from_backtest",
    ]
    if rules.get("downgrade_only"):
        cannot.append("upgrade_action")
    if rules.get("monitor_only"):
        cannot.append("size_without_board_gate")
    return cannot


def authority_ceiling(signal_type: str) -> str:
    """Highest authority this signal type may imply."""
    return _SIGNAL_AUTHORITY_CEILING.get(signal_type, AUTHORITY_BLOCKED)


def signal_rules(signal_type: str) -> Dict[str, Any]:
    base = dict(_SIGNAL_RULES.get(signal_type) or {})
    base["signal_type"] = signal_type
    base["authority_ceiling"] = authority_ceiling(signal_type)
    return base


def may_authorize_deploy(signal_type: str) -> bool:
    return bool(_SIGNAL_RULES.get(signal_type, {}).get("may_authorize_deploy"))


def build_provenance_envelope(
    *,
    signal_type: str,
    source: str,
    as_of: Optional[str] = None,
    degraded: bool = False,
    data_mode: str = "research_only",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Standard wrapper for opportunity intelligence API payloads."""
    rules = signal_rules(signal_type)
    return {
        "signal_type": signal_type,
        "authority_ceiling": rules["authority_ceiling"],
        "data_mode": data_mode,
        "degraded": degraded,
        "source": source,
        "as_of": as_of,
        "provenance": {
            **rules,
            "deploy_from_signal_alone": False,
            "page_gate_required": True,
        },
        "trust": {
            "mode": "RESEARCH" if data_mode == "research_only" else "CONFIRM",
            "stale": degraded,
            "source": source,
        },
        **(extra or {}),
    }


def assert_no_deploy_from_signals(signals: List[Dict[str, Any]]) -> None:
    """Raise if any signal claims deploy authority (test / guard hook)."""
    for sig in signals:
        st = sig.get("signal_type") or sig.get("type")
        if may_authorize_deploy(str(st)):
            raise ValueError(f"signal {st} must not authorize deploy")
