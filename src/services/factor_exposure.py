"""
Factor exposure — beta, sector, overlap, crowding labels (research).

Informs concentration risk; never grants deploy or sizing authority alone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_FACTOR_EXPOSURE,
    build_provenance_envelope,
)

CROWDING_LOW = "low"
CROWDING_MODERATE = "moderate"
CROWDING_HIGH = "high"

CROWDING_LABELS: Dict[str, str] = {
    CROWDING_LOW: "Factor crowding low — diversification OK in research",
    CROWDING_MODERATE: "Moderate overlap — watch concentration",
    CROWDING_HIGH: "High crowding — narrative / factor pile-on risk",
}


def evaluate_crowding(
    *,
    overlap_pct: float,
    sector_concentration_pct: float,
) -> str:
    if overlap_pct >= 55 or sector_concentration_pct >= 45:
        return CROWDING_HIGH
    if overlap_pct >= 30 or sector_concentration_pct >= 28:
        return CROWDING_MODERATE
    return CROWDING_LOW


def build_factor_exposure(
    ticker: str,
    *,
    market_beta: float = 1.05,
    sector: str = "Technology",
    sector_weight_pct: float = 22.0,
    book_overlap_pct: float = 18.0,
    positions: Optional[List[Dict[str, Any]]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    sym = ticker.upper().strip()
    positions = positions or []
    overlap = book_overlap_pct
    if positions:
        same_sector = sum(
            1 for p in positions if (p.get("sector") or "").lower() == sector.lower()
        )
        overlap = max(overlap, same_sector / max(len(positions), 1) * 100)

    crowding = evaluate_crowding(
        overlap_pct=overlap,
        sector_concentration_pct=sector_weight_pct,
    )
    body = {
        "ticker": sym,
        "beta": round(market_beta, 2),
        "sector": sector,
        "sector_weight_pct": sector_weight_pct,
        "book_overlap_pct": round(overlap, 1),
        "crowding": crowding,
        "crowding_label": CROWDING_LABELS[crowding],
        "overlap_warning": overlap >= 40,
        "may_authorize_deploy": False,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_FACTOR_EXPOSURE,
        source="mock-factor-stub",
        degraded=degraded or True,
        extra=body,
    )
