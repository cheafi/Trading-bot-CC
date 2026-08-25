"""EV Ranking v1 — research-only expected value after cost and fit (Sprint 117/122)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.cost_adjusted_edge import compute_net_edge, infer_burdens_from_row


def compute_ev_score(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    portfolio_fit_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    EV = alpha × prob × persistence × capacity × liquidity × fit × execution × macro
         − cost − crowding − decay

    Never overrides deploy gates — research ranking only.
    """
    raw = float(row.get("raw_score") or row.get("score") or 0.0)
    burdens = infer_burdens_from_row(row)
    edge = compute_net_edge(
        raw,
        turnover_burden=burdens["turnover_burden"],
        spread_burden=burdens["spread_burden"],
        action=row.get("action"),
        extended=bool(row.get("extended") or row.get("timing_extended")),
        partial_data=bool(row.get("partial")),
    )
    net = float(edge.get("net_edge_score") or raw)
    alpha = max(net / 10.0, 0.0)
    prob = float(row.get("thesis_conf") or row.get("confidence") or 0.5)
    if prob > 1.0:
        prob = prob / 100.0
    persistence = 0.85 if row.get("cost_rank_label") == "net_survives" else 0.65
    capacity = 1.0 if str(row.get("capacity_class") or "") != "blocked" else 0.4
    liquidity = 1.0 if str(row.get("liquidity_fit") or "ok") == "ok" else 0.7
    fit = (portfolio_fit_score or row.get("portfolio_fit_score") or 50) / 100.0
    execution = 1.0 if row.get("execution_ready") else 0.55
    macro = 0.9 if str(tradeability or row.get("tradeability") or "WAIT").upper() in (
        "TRADE",
        "SELECTIVE",
    ) else 0.5
    cost_penalty = float(edge.get("cost_drag") or 0.0) / 10.0
    crowding_penalty = 0.15 if str(row.get("crowding") or "").lower() in (
        "high",
        "elevated",
    ) else 0.0
    decay_penalty = 0.1 if row.get("strategy_decay_line") else 0.0

    components = {
        "alpha": round(alpha, 4),
        "prob": round(prob, 4),
        "persistence": round(persistence, 4),
        "capacity": round(capacity, 4),
        "liquidity": round(liquidity, 4),
        "fit": round(fit, 4),
        "execution": round(execution, 4),
        "macro": round(macro, 4),
        "cost_penalty": round(cost_penalty, 4),
        "crowding_penalty": round(crowding_penalty, 4),
        "decay_penalty": round(decay_penalty, 4),
    }
    positive = (
        components["alpha"]
        * components["prob"]
        * components["persistence"]
        * components["capacity"]
        * components["liquidity"]
        * components["fit"]
        * components["execution"]
        * components["macro"]
    )
    ev_score = round(
        positive
        - components["cost_penalty"]
        - components["crowding_penalty"]
        - components["decay_penalty"],
        4,
    )
    return {
        "ev_score": ev_score,
        "ev_components": components,
        "authority": "research_only",
        "may_authorize_deploy": False,
    }


def enrich_rows_with_ev(
    rows: List[Dict[str, Any]],
    *,
    tradeability: str = "",
) -> List[Dict[str, Any]]:
    """Attach ev_score + ev_components to each row."""
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        ev = compute_ev_score(r, tradeability=tradeability)
        r.update(ev)
        enriched.append(r)
    return sorted(enriched, key=lambda x: -(x.get("ev_score") or 0))
