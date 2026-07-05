"""
Portfolio / factor intelligence — overlap and concentration research.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.factor_exposure import evaluate_crowding

AUTHORITY_RESEARCH = "research_only"
AUTHORITY_ALLOCATOR = "allocator_support"


def _hidden_same_bet(
    positions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Detect tickers sharing sector/theme proxy."""
    by_sector: Dict[str, List[str]] = {}
    for p in positions:
        sec = str(p.get("sector") or "unknown").lower()
        sym = str(p.get("ticker") or p.get("symbol") or "").upper()
        if sym:
            by_sector.setdefault(sec, []).append(sym)
    alerts = []
    for sec, syms in by_sector.items():
        if len(syms) >= 3:
            alerts.append(
                {
                    "sector": sec,
                    "tickers": syms[:5],
                    "label": f"Hidden same-bet: {len(syms)} names in {sec}",
                }
            )
    return alerts[:3]


def build_portfolio_intel_context(
    *,
    positions: Optional[List[Dict[str, Any]]] = None,
    passive_baseline: Optional[Dict[str, Any]] = None,
    sleeve_summary: Optional[Dict[str, Any]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Book-level factor / overlap diagnostics."""
    pos = list(positions or [])
    sectors: Dict[str, float] = {}
    total = max(len(pos), 1)
    for p in pos:
        sec = str(p.get("sector") or "unknown")
        sectors[sec] = sectors.get(sec, 0) + 1
    sector_conc = max(sectors.values()) / total * 100 if sectors else 0
    overlap = evaluate_crowding(
        overlap_pct=sector_conc * 0.8,
        sector_concentration_pct=sector_conc,
    )

    passive = passive_baseline or {}
    complexity = passive.get("complexity_justified")
    passive_line = passive.get("advantage_note") or "Passive baseline comparator"

    sleeves = list((sleeve_summary or {}).get("cards") or [])
    cross_corr = "unknown" if len(sleeves) < 2 else "moderate — sleeve count " + str(len(sleeves))

    return {
        "authority": AUTHORITY_ALLOCATOR if sleeves else AUTHORITY_RESEARCH,
        "may_authorize_deploy": False,
        "degraded": degraded or not pos,
        "beta_tracker": {"label": "Book beta — research proxy when quotes sync"},
        "sector_concentration_pct": round(sector_conc, 1),
        "theme_concentration": overlap,
        "factor_overlap_map": {
            "crowding": overlap,
            "label": f"Factor crowding {overlap} — concentration research",
        },
        "cross_sleeve_correlation": cross_corr,
        "hidden_same_bet": _hidden_same_bet(pos),
        "passive_baseline_comparison": {
            "note": passive_line,
            "complexity_justified": complexity,
        },
        "active_vs_passive": {
            "label": (
                "Active complexity justified"
                if complexity is True
                else "Passive may be sufficient — research humility"
            ),
        },
        "strip_line": (
            f"Portfolio intel: sector conc {sector_conc:.0f}% · crowding {overlap}"
            + (" — MOCK/DEGRADED" if degraded or not pos else "")
            + " — not deploy authority"
        ),
    }
