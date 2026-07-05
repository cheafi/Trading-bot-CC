"""
Heuristic net edge after trading costs (Random Walk — honest estimate, not precision).

Subtracts turnover and spread/slippage burdens from a raw deploy score (0–10 scale).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Burdens are 0.0–1.0 intensity; penalties scale to score points on 0–10 scale.
_MAX_TURNOVER_PENALTY = 1.2
_MAX_SPREAD_PENALTY = 1.0
_WEAK_EDGE_NET_THRESHOLD = 6.0


def compute_net_edge(
    raw_score: float,
    *,
    turnover_burden: float = 0.25,
    spread_burden: float = 0.20,
    action: Optional[str] = None,
    extended: bool = False,
    partial_data: bool = False,
) -> Dict[str, Any]:
    """
    Estimate deployable score after simple cost drag.

    Rules (explicit, heuristic):
    - Clamp raw_score to [0, 10].
    - Clamp burdens to [0, 1].
    - turnover_penalty = turnover_burden * 1.2 (max ~1.2 pts)
    - spread_penalty = spread_burden * 1.0 (max ~1.0 pts)
    - If action is TRADE/BUY/PILOT, add +0.15 turnover (churn intent).
    - If extended (chase), add +0.20 spread burden cap bump (+0.15 spread penalty).
    - If partial_data, add +0.10 spread burden (+0.10 spread penalty).
    - net_deploy_score = max(0, raw - turnover_penalty - spread_penalty), rounded 1dp.
    - cost_drag = raw - net (rounded).
    - weak_edge_after_cost = net < 6.0
    """
    raw = max(0.0, min(10.0, float(raw_score)))
    tb = max(0.0, min(1.0, float(turnover_burden)))
    sb = max(0.0, min(1.0, float(spread_burden)))

    act = (action or "").upper()
    if act in ("TRADE", "BUY", "BUY_ON_DIP", "PILOT", "SCALE", "ADD"):
        tb = min(1.0, tb + 0.15)
    if extended:
        sb = min(1.0, sb + 0.20)
    if partial_data:
        sb = min(1.0, sb + 0.10)

    turnover_penalty = round(tb * _MAX_TURNOVER_PENALTY, 2)
    spread_penalty = round(sb * _MAX_SPREAD_PENALTY, 2)
    net = max(0.0, raw - turnover_penalty - spread_penalty)
    net = round(net, 1)
    drag = round(raw - net, 1)

    gross = round(raw, 1)
    return {
        "raw_score": gross,
        "gross_edge_score": gross,
        "net_deploy_score": net,
        "net_edge_score": net,
        "turnover_penalty": turnover_penalty,
        "spread_penalty": spread_penalty,
        "cost_drag": drag,
        "weak_edge_after_cost": net < _WEAK_EDGE_NET_THRESHOLD,
        "display": f"Raw {gross:.1f} · Net {net:.1f} after cost",
        "gross_net_display": f"Raw {gross:.1f} · Net {net:.1f} after cost",
        "model_note": "Heuristic estimate — not live TCA; use for ranking humility only.",
    }


def compute_gross_vs_net(
    raw_score: float,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Explicit gross vs net edge bundle for score_card / dossier surfaces."""
    edge = compute_net_edge(raw_score, **kwargs)
    gross = edge["gross_edge_score"]
    net = edge["net_edge_score"]
    return {
        **edge,
        "gross_vs_net": {
            "gross": gross,
            "net": net,
            "drag": edge["cost_drag"],
            "survives_cost": not edge["weak_edge_after_cost"],
        },
    }


def infer_burdens_from_row(row: Dict[str, Any]) -> Dict[str, float]:
    """Infer turnover/spread burdens from playbook or dossier context."""
    tb = 0.20
    sb = 0.15
    freshness = row.get("data_freshness_minutes")
    if freshness and int(freshness) > 480:
        sb = min(1.0, sb + 0.25)
    if row.get("partial") or row.get("module_errors"):
        sb = min(1.0, sb + 0.20)
    if row.get("rr_below_trade_threshold"):
        tb = min(1.0, tb + 0.15)
    stage = (row.get("stage") or "").upper()
    if stage in ("EXTENDED", "LATE", "BLOW_OFF"):
        sb = min(1.0, sb + 0.35)
        tb = min(1.0, tb + 0.10)
    return {"turnover_burden": tb, "spread_burden": sb}


def attach_net_edge_to_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Add net-edge fields to an opportunity row when raw score is known."""
    raw = row.get("raw_score")
    if raw is None:
        raw = row.get("score")
    if raw is None:
        return row
    burdens = infer_burdens_from_row(row)
    edge = compute_net_edge(
        float(raw),
        turnover_burden=burdens["turnover_burden"],
        spread_burden=burdens["spread_burden"],
        action=row.get("action"),
        extended=bool(row.get("extended") or row.get("timing_extended")),
        partial_data=bool(row.get("partial")),
    )
    row = {**row, **edge}
    row["net_edge_display"] = edge["display"]
    return row
