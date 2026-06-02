"""
Core + satellite architecture — sleeve role tags and exposure bands for Portfolio.

Lightweight allocator view: core passive / active stock / tactical / cash reserve.
Honest when book is local-only or too small for band math.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical sleeve roles (core + satellite vocabulary)
SLEEVE_ROLES: Dict[str, Dict[str, str]] = {
    "core_passive": {
        "label": "Core passive",
        "meaning": "Index-like benchmark sleeve — SPY/QQQ/RSP proxies",
    },
    "active_stock": {
        "label": "Active stock",
        "meaning": "Council-validated single names with thesis",
    },
    "tactical": {
        "label": "Tactical",
        "meaning": "Short-horizon, event, or fund-sleeve deploy",
    },
    "cash_reserve": {
        "label": "Cash reserve",
        "meaning": "Dry powder — valid allocation, not forced deploy",
    },
}

# Policy exposure bands (target min–max % of book)
EXPOSURE_BANDS: Dict[str, Dict[str, float]] = {
    "core_passive": {"min_pct": 40.0, "max_pct": 70.0, "target_pct": 55.0},
    "active_stock": {"min_pct": 20.0, "max_pct": 50.0, "target_pct": 35.0},
    "tactical": {"min_pct": 0.0, "max_pct": 15.0, "target_pct": 5.0},
    "cash_reserve": {"min_pct": 5.0, "max_pct": 25.0, "target_pct": 10.0},
}

_PASSIVE_TICKERS = frozenset(
    {"SPY", "QQQ", "RSP", "IVV", "VOO", "VTI", "SCHB", "DIA", "IWM"}
)
_TACTICAL_HINTS = frozenset({"options", "tactical", "event", "sleeve", "deploy", "hedge"})


def classify_sleeve_role(position: Dict[str, Any]) -> str:
    """
    Infer sleeve role from position metadata.

    Explicit `sleeve_role` wins; otherwise heuristics from ticker / sleeve / strategy.
    """
    explicit = position.get("sleeve_role")
    if explicit and str(explicit).strip().lower() in SLEEVE_ROLES:
        return str(explicit).strip().lower()

    ticker = str(position.get("ticker") or "").upper()
    if ticker in ("CASH", "USD", "USDC"):
        return "cash_reserve"
    if ticker in _PASSIVE_TICKERS:
        return "core_passive"

    sleeve = str(position.get("sleeve") or "").lower()
    strategy = str(position.get("strategy_id") or position.get("strategy") or "").lower()
    combined = f"{sleeve} {strategy}"
    if any(h in combined for h in _TACTICAL_HINTS):
        return "tactical"
    if sleeve in ("true", "sleeve deploy", "sleeve_deploy", "fund sleeve"):
        return "tactical"
    if sleeve in ("false", "core book", "core", ""):
        return "active_stock"

    asset_class = str(position.get("asset_class") or "").lower()
    if asset_class in ("etf", "index", "passive"):
        return "core_passive"
    if asset_class == "cash":
        return "cash_reserve"

    return "active_stock"


def _total_value(positions: List[Dict[str, Any]]) -> float:
    return sum(float(p.get("market_value") or 0) for p in positions)


def _band_status(actual_pct: float, band: Dict[str, float]) -> str:
    if actual_pct < band["min_pct"]:
        return "under"
    if actual_pct > band["max_pct"]:
        return "over"
    return "in_band"


def build_core_satellite_summary(
    positions: List[Dict[str, Any]],
    *,
    equity: Optional[float] = None,
    cash_pct: float = 0.0,
    local_only: bool = False,
    broker_synced: bool = True,
) -> Dict[str, Any]:
    """
    Role-based allocation summary with exposure bands for Portfolio tab.
    """
    n = len(positions)
    total = equity if equity and equity > 0 else _total_value(positions)
    insufficient = n < 1 or (n == 1 and local_only) or (local_only and not broker_synced)

    role_weights: Dict[str, float] = {k: 0.0 for k in SLEEVE_ROLES}
    role_holdings: Dict[str, List[str]] = {k: [] for k in SLEEVE_ROLES}
    tagged: List[Dict[str, Any]] = []

    for p in positions:
        role = classify_sleeve_role(p)
        mv = float(p.get("market_value") or 0)
        wt = (mv / total * 100) if total > 0 else 0.0
        role_weights[role] = role_weights.get(role, 0.0) + wt
        ticker = str(p.get("ticker") or "—")
        role_holdings.setdefault(role, []).append(ticker)
        tagged.append(
            {
                "ticker": ticker,
                "sleeve_role": role,
                "sleeve_role_label": SLEEVE_ROLES[role]["label"],
                "weight_pct": round(wt, 2),
            }
        )

    if cash_pct > 0:
        role_weights["cash_reserve"] = role_weights.get("cash_reserve", 0.0) + cash_pct

    bands: List[Dict[str, Any]] = []
    for role_key, meta in SLEEVE_ROLES.items():
        band = EXPOSURE_BANDS[role_key]
        actual = round(role_weights.get(role_key, 0.0), 2)
        status = _band_status(actual, band) if not insufficient else "unknown"
        bands.append(
            {
                "role": role_key,
                "label": meta["label"],
                "meaning": meta["meaning"],
                "actual_pct": actual,
                "min_pct": band["min_pct"],
                "max_pct": band["max_pct"],
                "target_pct": band["target_pct"],
                "status": status,
                "holdings": role_holdings.get(role_key, [])[:6],
            }
        )

    out_of_band = [b for b in bands if b["status"] in ("over", "under") and b["actual_pct"] > 0]
    headline = "Core + satellite allocation"
    if insufficient:
        headline = "Insufficient book depth for band math"
        detail = (
            "One position or local-only book — role tags are illustrative. "
            "Confirm broker sync and ≥3 names before trusting exposure bands."
        )
    elif not out_of_band:
        detail = "All populated sleeves within policy bands — monitor drift at rebalance."
    else:
        parts = [f"{b['label']} {b['status']} band" for b in out_of_band[:2]]
        detail = " · ".join(parts) + " — rebalance before adding tactical risk."

    return {
        "headline": headline,
        "detail": detail,
        "insufficient_data": insufficient,
        "local_only": local_only,
        "position_count": n,
        "role_allocation": bands,
        "tagged_positions": tagged,
        "cash_pct": round(cash_pct, 2),
        "architecture_note": (
            "Core passive holds benchmark risk; active stock earns edge; "
            "tactical is sized small; cash reserve is valid."
        ),
        "model_note": (
            "Role tags inferred from ticker/sleeve metadata — set sleeve_role on "
            "positions to override heuristics."
        ),
        "index_fund_alignment": _index_fund_alignment_for_positions(positions),
    }


def _index_fund_alignment_for_positions(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Index-fund guide alignment for core passive holdings (proxy)."""
    try:
        from src.services.index_fund_judgment import index_fund_alignment_for_core_satellite

        return index_fund_alignment_for_core_satellite(positions)
    except Exception:
        return {
            "alignment_note": "Index-fund alignment unavailable",
            "proxy": True,
        }
