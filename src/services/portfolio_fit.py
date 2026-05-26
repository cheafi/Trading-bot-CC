"""Portfolio-fit score — is this stock right for the current book?"""

from __future__ import annotations

from typing import Any, Dict, List

from src.engines.correlation_risk import get_sector


def build_portfolio_fit(
    ticker: str,
    positions: List[Dict[str, Any]],
    *,
    sector: str | None = None,
) -> Dict[str, Any]:
    """Heuristic portfolio-fit for single-stock 360."""
    sym = ticker.upper()
    holdings = [
        (p.get("ticker") or "").upper()
        for p in positions
        if p.get("ticker")
    ]
    total = sum(float(p.get("market_value") or 0) for p in positions) or 1.0
    same_sector = 0.0
    overlap: List[str] = []
    for p in positions:
        t = (p.get("ticker") or "").upper()
        if t == sym:
            overlap.append(t)
        if sector and get_sector(t) == sector:
            same_sector += float(p.get("market_value") or 0) / total

    score = 70
    notes: List[str] = []
    if sym in holdings:
        score -= 25
        notes.append("Already in book — sizing add only")
    if same_sector > 0.35:
        score -= 20
        notes.append(f"Sector cluster ~{same_sector * 100:.0f}% — diversification weak")
    if len(holdings) >= 8 and sym not in holdings:
        score += 5
        notes.append("Adds name count — modest diversifier")
    if not holdings:
        score = 55
        notes.append("Empty book — fit neutral until policy set")

    score = max(0, min(100, score))
    return {
        "score": score,
        "fit_label": (
            "strong_fit"
            if score >= 75
            else "neutral"
            if score >= 50
            else "poor_fit"
        ),
        "overlap_tickers": overlap,
        "sector_weight_pct": round(same_sector * 100, 1),
        "diversification_benefit": score >= 60,
        "concentration_impact": "high" if same_sector > 0.25 else "low",
        "beta_impact_note": "Wire position betas for book-level beta delta",
        "recommended_sizing_context": (
            "Starter size — 0.5–1R"
            if score >= 70
            else "Reduce size or wait for trim elsewhere"
            if score < 50
            else "Standard sleeve sizing"
        ),
        "notes": notes,
        "evidence": {"basis": "heuristic", "label": "Sector map + holdings overlap"},
    }
