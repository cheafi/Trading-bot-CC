"""
IBKR-style execution algo recommendations — recommendation strings only.

Never routes orders or grants deploy authority.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.signal_provenance import (
    SIGNAL_EXECUTION_ALGO,
    build_provenance_envelope,
)

SIGNAL_EXECUTION_ALGO = SIGNAL_EXECUTION_ALGO  # re-export for tests

ALGO_ADAPTIVE = "adaptive"
ALGO_VWAP = "vwap"
ALGO_TWAP = "twap"
ALGO_PATIENT = "patient_limit"
ALGO_URGENT = "urgent_limit"

ALGO_LABELS: Dict[str, str] = {
    ALGO_ADAPTIVE: "Adaptive IBKR algo — balance urgency vs impact (recommendation only)",
    ALGO_VWAP: "VWAP — liquid names, full-day participation (recommendation only)",
    ALGO_TWAP: "TWAP — steady clip, elevated vol (recommendation only)",
    ALGO_PATIENT: "Patient limit — wide spread / low urgency (recommendation only)",
    ALGO_URGENT: "Urgent limit — only when board + execution path green (recommendation only)",
}


def recommend_execution_algo(
    *,
    urgency: str = "normal",
    spread_bps: float = 8.0,
    avg_daily_volume: float = 1_000_000,
    vix: Optional[float] = None,
    liquidity_fit: str = "ok",
) -> str:
    urg = (urgency or "normal").lower()
    if liquidity_fit == "thin" or spread_bps > 18:
        return ALGO_PATIENT
    if urg == "high" and spread_bps <= 12 and (vix or 18) < 26:
        return ALGO_URGENT
    if avg_daily_volume >= 5_000_000 and spread_bps <= 10:
        return ALGO_VWAP
    if (vix or 18) >= 24:
        return ALGO_TWAP
    return ALGO_ADAPTIVE


def build_execution_algo_context(
    *,
    ticker: str = "",
    urgency: str = "normal",
    spread_bps: float = 8.0,
    avg_daily_volume: float = 1_000_000,
    vix: Optional[float] = None,
    liquidity_fit: str = "ok",
    degraded: bool = True,
) -> Dict[str, Any]:
    algo = recommend_execution_algo(
        urgency=urgency,
        spread_bps=spread_bps,
        avg_daily_volume=avg_daily_volume,
        vix=vix,
        liquidity_fit=liquidity_fit,
    )
    body = {
        "ticker": (ticker or "").upper().strip(),
        "recommended_algo": algo,
        "recommendation": ALGO_LABELS.get(algo, algo),
        "urgency": urgency,
        "spread_bps": spread_bps,
        "liquidity_fit": liquidity_fit,
        "routes_orders": False,
        "authorizes_execution": False,
        "monitor_only": True,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_EXECUTION_ALGO,
        source="mock-execution-algo-stub",
        degraded=degraded,
        data_mode="research_only",
        extra=body,
    )
