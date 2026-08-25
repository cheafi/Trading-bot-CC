"""
Cost-adjusted ranking — net edge labels for playbook display only.

May downgrade ranking order; never overrides WAIT or grants deploy authority.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.cost_adjusted_edge import compute_net_edge, infer_burdens_from_row
from src.services.signal_provenance import (
    SIGNAL_COST_RANK,
    build_provenance_envelope,
)
from src.services.strategy_validity import resolve_strategy_decay_line

try:
    from src.services.index_relative_leadership import leadership_from_row
except ImportError:
    leadership_from_row = None  # type: ignore[misc, assignment]

LABEL_NET_SURVIVES = "net_survives"
LABEL_COST_TOO_HIGH = "cost_too_high"
LABEL_MONITOR_ONLY = "monitor_only"

RANK_LABELS: Dict[str, str] = {
    LABEL_NET_SURVIVES: "Net edge survives cost drag — ranking hint only",
    LABEL_COST_TOO_HIGH: "Cost drag erodes edge — demote in sort, not a veto alone",
    LABEL_MONITOR_ONLY: "Insufficient edge after cost — monitor / near-miss only",
}


def resolve_cost_rank_label(
    *,
    raw_score: float,
    net_score: float,
    tradeability: str = "",
    weak_edge_after_cost: bool = False,
) -> str:
    """Classify cost-adjusted rank tier (display / sort — not deploy gate)."""
    tb = str(tradeability or "").upper()
    if tb == "WAIT":
        return LABEL_MONITOR_ONLY
    if weak_edge_after_cost or net_score < 6.0:
        return LABEL_COST_TOO_HIGH if raw_score >= 5.5 else LABEL_MONITOR_ONLY
    if net_score >= 6.5 and raw_score - net_score < 1.5:
        return LABEL_NET_SURVIVES
    if net_score >= 6.0:
        return LABEL_NET_SURVIVES
    return LABEL_MONITOR_ONLY


def rank_single_row(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Attach cost-rank fields to one opportunity row."""
    raw = row.get("raw_score")
    if raw is None:
        raw = row.get("score")
    if raw is None:
        return {
            **row,
            "cost_rank_label": LABEL_MONITOR_ONLY,
            "cost_rank_display": RANK_LABELS[LABEL_MONITOR_ONLY],
            "may_override_wait": False,
        }
    burdens = infer_burdens_from_row(row)
    edge = compute_net_edge(
        float(raw),
        turnover_burden=burdens["turnover_burden"],
        spread_burden=burdens["spread_burden"],
        action=row.get("action"),
        extended=bool(row.get("extended") or row.get("timing_extended")),
        partial_data=bool(row.get("partial")),
    )
    tb = str(tradeability or row.get("tradeability") or "").upper()
    label = resolve_cost_rank_label(
        raw_score=edge["raw_score"],
        net_score=edge["net_edge_score"],
        tradeability=tb,
        weak_edge_after_cost=edge["weak_edge_after_cost"],
    )
    out = {
        **row,
        **edge,
        "cost_rank_label": label,
        "cost_rank_display": RANK_LABELS[label],
        "may_override_wait": False,
        "cost_rank_blocked_on_wait": tb == "WAIT",
    }
    if tb == "WAIT":
        out["action"] = (
            row.get("action")
            if row.get("action") not in ("TRADE", "BUY", "PILOT")
            else "WATCH"
        )
    decay_line = resolve_strategy_decay_line(out)
    if decay_line:
        out["strategy_decay_line"] = decay_line
    return out


def resolve_regime_fit_label(
    row: Dict[str, Any],
    *,
    index_regime: Optional[Dict[str, Any]] = None,
    tradeability: str = "",
) -> str:
    """Regime fit pill for playbook — filter hint, not deploy gate."""
    posture = str((index_regime or {}).get("posture") or "").lower()
    tb = str(tradeability or row.get("tradeability") or "").upper()
    leadership = str(row.get("index_leadership") or "")
    if tb in ("NO_TRADE", "WAIT"):
        return "wait_filter"
    if posture in ("stressed", "no_trade_pressure"):
        return "stressed_filter"
    if leadership == "lag":
        return "lag_vs_index"
    if leadership == "outperform" and posture in ("risk_on", "normal"):
        return "aligned"
    return "selective_filter"


def resolve_execution_fit_label(row: Dict[str, Any]) -> str:
    vol_q = str(row.get("vol_quality") or "").upper()
    extended = bool(row.get("extended") or row.get("timing_extended"))
    if vol_q == "LOW" or extended:
        return "caution"
    if row.get("execution_ready"):
        return "ready_hint"
    return "monitor"


def resolve_liquidity_fit_label(row: Dict[str, Any]) -> str:
    vol_r = row.get("vol_ratio")
    try:
        vr = float(vol_r) if vol_r is not None else 1.0
    except (TypeError, ValueError):
        vr = 1.0
    if vr < 0.5:
        return "thin"
    if vr > 2.5:
        return "elevated_turnover"
    return "ok"


def enrich_row_with_index_intel(
    row: Dict[str, Any],
    *,
    index_regime: Optional[Dict[str, Any]] = None,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Attach regime/execution/liquidity fit + index leadership (monitor-only)."""
    out = dict(row)
    if leadership_from_row is not None:
        lead = leadership_from_row(out, index_regime=index_regime)
        out["index_leadership"] = lead.get("composite")
        out["index_leadership_detail"] = lead
    out["regime_fit"] = resolve_regime_fit_label(
        out, index_regime=index_regime, tradeability=tradeability
    )
    out["execution_fit"] = resolve_execution_fit_label(out)
    out["liquidity_fit"] = resolve_liquidity_fit_label(out)
    out["regime_intel_monitor_only"] = True
    out["may_authorize_deploy"] = False
    return out


def enrich_opportunity_rows(
    rows: List[Dict[str, Any]],
    *,
    index_regime: Optional[Dict[str, Any]] = None,
    tradeability: str = "",
) -> List[Dict[str, Any]]:
    """Rank + index intel enrichment for playbook rows."""
    ranked = rank_opportunity_rows(rows, tradeability=tradeability)
    return [
        enrich_row_with_index_intel(
            r, index_regime=index_regime, tradeability=tradeability
        )
        for r in ranked
    ]


def rank_opportunity_rows(
    rows: List[Dict[str, Any]],
    *,
    tradeability: str = "",
) -> List[Dict[str, Any]]:
    """Sort by net edge descending; WAIT rows stay monitor-only labels."""
    ranked = [rank_single_row(r, tradeability=tradeability) for r in rows]
    order = {LABEL_NET_SURVIVES: 0, LABEL_COST_TOO_HIGH: 1, LABEL_MONITOR_ONLY: 2}

    def sort_key(r: Dict[str, Any]) -> tuple:
        return (
            order.get(r.get("cost_rank_label"), 3),
            -(r.get("net_edge_score") or 0),
            -(r.get("raw_score") or r.get("score") or 0),
        )

    return sorted(ranked, key=sort_key)


def build_cost_rank_context(
    ticker: str,
    *,
    raw_score: float = 7.2,
    tradeability: str = "SELECTIVE",
    degraded: bool = False,
) -> Dict[str, Any]:
    """API payload for /cost-ranked — research ranking, not deploy."""
    sym = ticker.upper().strip()
    row = rank_single_row(
        {"ticker": sym, "raw_score": raw_score, "score": raw_score},
        tradeability=tradeability,
    )
    body = {
        "ticker": sym,
        "ranking": row,
        "tradeability": tradeability,
        "may_override_wait": False,
        "deploy_from_cost_rank_alone": False,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_COST_RANK,
        source="mock-cost-rank-stub",
        as_of=None,
        degraded=degraded or True,
        extra=body,
    )
