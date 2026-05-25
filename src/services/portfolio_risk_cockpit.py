"""Portfolio risk cockpit — concentration, correlation, factor crowding."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.engines.correlation_risk import CorrelationRiskEngine, get_sector


def build_portfolio_risk_cockpit(
    positions: List[Dict[str, Any]],
    *,
    max_sector_pct: float = 35.0,
) -> Dict[str, Any]:
    """Risk cockpit payload for portfolio tab."""
    holdings = [
        {
            "ticker": p.get("ticker", ""),
            "market_value": float(p.get("market_value") or 0),
        }
        for p in positions
        if p.get("ticker")
    ]
    engine = CorrelationRiskEngine()
    summary = engine.summary(holdings) if holdings else {}

    total = sum(h["market_value"] for h in holdings) or 1.0
    sector_pct = {
        k: round(v * 100, 1) for k, v in (summary.get("sector_weights") or {}).items()
    }
    top_risk = None
    if holdings:
        worst = min(
            positions,
            key=lambda p: float(p.get("pnl_pct") or 0),
            default=None,
        )
        if worst:
            top_risk = {
                "ticker": worst.get("ticker"),
                "reason": "Largest unrealized drag",
                "pnl_pct": worst.get("pnl_pct"),
            }

    alerts: List[Dict[str, str]] = []
    for w in summary.get("warnings") or []:
        alerts.append({"severity": "warning", "category": "concentration", "message": w})
    for c in summary.get("crowding_flags") or []:
        alerts.append({"severity": "warning", "category": "correlation", "message": c})
    if (summary.get("top_weight_pct") or 0) > max_sector_pct:
        alerts.append(
            {
                "severity": "critical",
                "category": "concentration",
                "message": f"Top name {summary.get('top_weight_pct')}% exceeds {max_sector_pct}% guide",
            }
        )

    matrix_labels = list({get_sector(h["ticker"]) for h in holdings if h["ticker"]})
    matrix: Dict[str, Dict[str, float]] = {}
    for a in matrix_labels:
        matrix[a] = {}
        for b in matrix_labels:
            matrix[a][b] = 1.0 if a == b else (0.65 if a == b else 0.35)

    return {
        "grade": summary.get("grade", "—"),
        "hhi": summary.get("hhi", 0),
        "top_ticker": summary.get("top_ticker"),
        "top_weight_pct": summary.get("top_weight_pct"),
        "sector_exposure_pct": sector_pct,
        "correlated_pairs": summary.get("correlated_pairs") or [],
        "correlation_pair_count": summary.get("correlation_pairs", 0),
        "diversification_score": max(0, min(100, 100 - int((summary.get("hhi") or 0) / 30))),
        "factor_crowding_note": (
            "High tech weight — hidden beta to QQQ"
            if sector_pct.get("Technology", 0) > 40
            else "Sector mix within normal heuristic bands"
        ),
        "top_risk_contributor": top_risk,
        "alerts": alerts,
        "sector_correlation_matrix": {
            "labels": matrix_labels,
            "matrix": matrix,
        },
        "evidence": {
            "basis": "heuristic_sector_map",
            "live_correlation": False,
            "label": "Sector heuristic — wire live returns for true matrix",
        },
    }
