"""Portfolio risk cockpit — concentration, correlation, factor crowding."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.engines.correlation_risk import CorrelationRiskEngine, get_sector


def _build_risk_reduction_actions(
    positions: List[Dict[str, Any]],
    concentration_offenders: List[Dict[str, Any]],
    heat: Dict[str, Any],
    *,
    sector_breaches: List[Dict[str, Any]],
    at_cap: bool,
) -> List[Dict[str, str]]:
    """Top risk-reduction actions with PM language — critical tier first."""
    actions: List[Dict[str, str]] = []
    if heat.get("stop_breached_count"):
        for bp in heat.get("stop_breached_positions") or []:
            ticker = bp.get("ticker") or "—"
            open_r = bp.get("open_r")
            r_note = f" ({open_r:+.2f}R open)" if open_r is not None else ""
            actions.append(
                {
                    "urgency": "now",
                    "tier": "critical",
                    "action": "EXIT NOW",
                    "message": f"{ticker} stop breached{r_note} — exit risk unmanaged",
                    "ticker": ticker,
                }
            )
    for c in concentration_offenders[:2]:
        tier = "critical" if float(c.get("weight_pct") or 0) >= 50 else "secondary"
        actions.append(
            {
                "urgency": "now" if tier == "critical" else "today",
                "tier": tier,
                "action": "TRIM NOW",
                "message": f"Reduce {c['ticker']} — {c['reason']}",
                "ticker": c["ticker"],
            }
        )
    for sb in sector_breaches[:1]:
        actions.append(
            {
                "urgency": "today",
                "action": "REDUCE CONCENTRATION",
                "message": f"Trim {sb['sector']} sleeve — sector {sb['weight_pct']:.1f}% overweight",
                "ticker": None,
            }
        )
    if heat.get("without_stop"):
        actions.append(
            {
                "urgency": "now",
                "action": "SET STOPS",
                "message": heat.get(
                    "heat_quality_label",
                    "Define stop anchors — heat unmeasurable without stops",
                ),
                "ticker": None,
            }
        )
    elif heat.get("heat_available") and float(heat.get("heat_pct") or 0) > 6:
        actions.append(
            {
                "urgency": "now",
                "action": "DE-RISK",
                "message": f"Total heat {heat.get('heat_pct', 0):.1f}% > 6% — trim weakest names",
                "ticker": None,
            }
        )
    if at_cap:
        actions.append(
            {
                "urgency": "today",
                "action": "AT CAP",
                "message": "10/10 positions — trim before adding new risk",
                "ticker": None,
            }
        )
    if not actions and positions:
        actions.append(
            {
                "urgency": "monitor",
                "action": "MONITOR",
                "message": "No critical risk breaches — maintain stops and drift checks",
                "ticker": None,
            }
        )
    return actions[:3]


def build_portfolio_risk_cockpit(
    positions: List[Dict[str, Any]],
    *,
    max_sector_pct: float = 40.0,
    heat: Optional[Dict[str, Any]] = None,
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

    # Per-position risk contributors sorted by weight × negative pnl
    risk_contributors: List[Dict[str, Any]] = []
    concentration_offenders: List[Dict[str, Any]] = []
    earnings_near = 0
    for p in positions:
        mv = float(p.get("market_value") or 0)
        w = (mv / total) * 100 if total else 0.0
        pnl = float(p.get("pnl_pct") or 0)
        ticker = p.get("ticker") or "—"
        risk_score = round(w * max(0.0, -pnl), 3)
        risk_contributors.append(
            {
                "ticker": ticker,
                "weight_pct": round(w, 2),
                "pnl_pct": pnl,
                "risk_score": risk_score,
                "reason": "Weight × unrealized drag" if pnl < 0 else "Weight exposure",
            }
        )
        if w > 12:
            concentration_offenders.append(
                {
                    "ticker": ticker,
                    "weight_pct": round(w, 2),
                    "reason": f"Single-name {w:.1f}% > 12% guide",
                }
            )
        if int(p.get("days_to_earnings") or 999) <= 5:
            earnings_near += 1

    risk_contributors.sort(key=lambda x: -x["risk_score"])
    concentration_offenders.sort(key=lambda x: -x["weight_pct"])

    top_risk = risk_contributors[0] if risk_contributors else None

    alerts: List[Dict[str, str]] = []
    for w in summary.get("warnings") or []:
        alerts.append(
            {"severity": "warning", "category": "concentration", "message": w}
        )
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
    heat = heat or {}
    if heat.get("stop_breached_count"):
        alerts.insert(
            0,
            {
                "severity": "critical",
                "category": "stop_breach",
                "message": heat.get(
                    "heat_quality_label", "Stop breached — exit risk unmanaged"
                ),
            },
        )
    elif heat.get("without_stop"):
        alerts.append(
            {
                "severity": "warning",
                "category": "stop_coverage",
                "message": heat.get("heat_quality_label", "Stop missing on positions"),
            }
        )

    matrix_labels = list({get_sector(h["ticker"]) for h in holdings if h["ticker"]})
    matrix: Dict[str, Dict[str, float]] = {}
    for a in matrix_labels:
        matrix[a] = {}
        for b in matrix_labels:
            matrix[a][b] = 1.0 if a == b else 0.35

    # Correlated clusters — sector groups with >2 names
    sector_counts: Dict[str, int] = {}
    for p in positions:
        sec = get_sector(p.get("ticker") or "")
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
    correlated_clusters = [
        {"sector": sec, "count": cnt, "note": f"{cnt} names in {sec}"}
        for sec, cnt in sector_counts.items()
        if cnt >= 2
    ]

    tech_weight = sector_pct.get("Technology", 0)
    beta_concentration = (
        round(
            sum(
                (float(p.get("market_value") or 0) / total)
                * float(p.get("beta") or 1.0)
                for p in positions
            ),
            2,
        )
        if positions
        else 0.0
    )

    hhi = summary.get("hhi") or 0
    concentration_status = (
        "critical"
        if hhi > 2500 or (summary.get("top_weight_pct") or 0) > 15
        else "elevated"
        if hhi > 1800
        else "normal"
    )
    if (
        heat.get("stop_breached_count")
        or concentration_status == "critical"
        or heat.get("without_stop")
        or (heat.get("heat_available") and float(heat.get("heat_pct") or 0) > 6)
    ):
        severity = "Action needed"
    elif concentration_status == "elevated" or sector_pct.get("Technology", 0) > 40:
        severity = "Watch"
    else:
        severity = "OK"

    if hhi > 2500:
        hhi_plain = "Highly concentrated — top names dominate risk"
    elif hhi > 1800:
        hhi_plain = "Moderately concentrated — monitor drift"
    else:
        hhi_plain = "Well diversified — no single-name dominance"

    top_risk_ranked: List[Dict[str, Any]] = []
    for r in risk_contributors[:3]:
        w = float(r.get("weight_pct") or 0)
        sec = get_sector(r.get("ticker") or "")
        if w > 12:
            action = f"Trim {r['ticker']} toward 12% cap"
        elif sec == "Technology" and sector_pct.get("Technology", 0) > 40:
            action = (
                f"Trim tech sleeve 15–20% (now {sector_pct.get('Technology', 0):.0f}%)"
            )
        elif r.get("pnl_pct", 0) < -5:
            action = f"Review thesis — unrealized drag {r['pnl_pct']:.1f}%"
        else:
            action = "Monitor — within heuristic bands"
        top_risk_ranked.append({**r, "recommended_action": action})

    for sb in [
        {"sector": sec, "weight_pct": wt}
        for sec, wt in sector_pct.items()
        if wt > max_sector_pct
    ]:
        if len(top_risk_ranked) >= 3:
            break
        top_risk_ranked.append(
            {
                "ticker": sb["sector"],
                "weight_pct": sb["weight_pct"],
                "reason": f"Sector {sb['weight_pct']:.1f}% > {max_sector_pct:.0f}% cap",
                "recommended_action": f"Trim {sb['sector']} exposure 15–20%",
            }
        )

    return {
        "grade": summary.get("grade", "—"),
        "hhi": hhi,
        "hhi_plain_english": hhi_plain,
        "severity": severity,
        "top_ticker": summary.get("top_ticker"),
        "top_weight_pct": summary.get("top_weight_pct"),
        "concentration_status": concentration_status,
        "position_cap": 10,
        "at_position_cap": len(positions) >= 10,
        "sector_cap_pct": max_sector_pct,
        "sector_breaches": [
            {
                "sector": sec,
                "weight_pct": wt,
                "message": f"{sec} {wt:.1f}% > {max_sector_pct:.0f}% cap",
            }
            for sec, wt in sector_pct.items()
            if wt > max_sector_pct
        ],
        "crowding_risk": (
            "elevated"
            if len(summary.get("crowding_flags") or []) > 0 or tech_weight > 40
            else "normal"
        ),
        "stop_coverage_pct": heat.get("stop_coverage_pct", 0),
        "stop_missing_count": heat.get("without_stop", 0),
        "sector_exposure_pct": sector_pct,
        "correlated_pairs": summary.get("correlated_pairs") or [],
        "correlated_clusters": correlated_clusters,
        "correlation_pair_count": summary.get("correlation_pairs", 0),
        "diversification_score": max(0, min(100, 100 - int(hhi / 30))),
        "factor_crowding_note": (
            "High tech weight — hidden beta to QQQ"
            if tech_weight > 40
            else "Sector mix within normal heuristic bands"
        ),
        "beta_concentration": beta_concentration,
        "earnings_concentration": earnings_near,
        "top_risk_contributor": top_risk,
        "top_risk_contributors": top_risk_ranked[:3],
        "concentration_offenders": concentration_offenders[:3],
        "risk_source_breakdown": {
            "concentration": concentration_status,
            "correlation": "elevated" if summary.get("crowding_flags") else "normal",
            "stop_coverage": (
                "partial"
                if heat.get("without_stop") and heat.get("with_stop")
                else "missing"
                if heat.get("without_stop")
                else "full"
            ),
            "earnings": "near" if earnings_near else "clear",
        },
        "alerts": alerts,
        "risk_reduction_actions": _build_risk_reduction_actions(
            positions,
            concentration_offenders,
            heat,
            sector_breaches=[
                {"sector": sec, "weight_pct": wt}
                for sec, wt in sector_pct.items()
                if wt > max_sector_pct
            ],
            at_cap=len(positions) >= 10,
        ),
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
