"""
Execution analytics — latency, slippage, fill quality (TCA-style labels).

Ops / research surface — does not authorize trades or override board WAIT.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_EXECUTION_ANALYTICS,
    build_provenance_envelope,
)

STATUS_EXCELLENT = "excellent"
STATUS_ACCEPTABLE = "acceptable"
STATUS_DEGRADED = "degraded"
STATUS_UNKNOWN = "unknown"

SAMPLE_STATE_LIVE = "live_sample"
SAMPLE_STATE_STUB = "stub_sample"
SAMPLE_STATE_INSUFFICIENT = "insufficient_sample"

STATUS_LABELS: Dict[str, str] = {
    STATUS_EXCELLENT: "Fill quality excellent — ops context",
    STATUS_ACCEPTABLE: "Acceptable slippage — monitor size",
    STATUS_DEGRADED: "Execution degraded — reduce urgency",
    STATUS_UNKNOWN: "Insufficient fill sample",
}

SAMPLE_STATE_LABELS: Dict[str, str] = {
    SAMPLE_STATE_LIVE: "Live fill sample — ops context",
    SAMPLE_STATE_STUB: "Stub sample — MOCK/DEGRADED",
    SAMPLE_STATE_INSUFFICIENT: "Insufficient sample — monitor only",
}


def resolve_sample_state(
    *,
    orders_sampled: int,
    ibkr_connected: bool,
    degraded: bool,
) -> str:
    if orders_sampled < 5 or degraded:
        return SAMPLE_STATE_INSUFFICIENT
    if ibkr_connected and orders_sampled >= 5:
        return SAMPLE_STATE_LIVE
    return SAMPLE_STATE_STUB


def _latency_bucket(ms: float) -> str:
    if ms < 50:
        return "low"
    if ms < 200:
        return "medium"
    return "high"


def evaluate_fill_quality(
    *,
    slippage_bps: float,
    fill_rate_pct: float,
    partial_fill_pct: float = 0.0,
) -> str:
    if fill_rate_pct < 85 or slippage_bps > 25:
        return STATUS_DEGRADED
    if slippage_bps > 12 or partial_fill_pct > 15:
        return STATUS_ACCEPTABLE
    if fill_rate_pct >= 95 and slippage_bps <= 8:
        return STATUS_EXCELLENT
    return STATUS_ACCEPTABLE


def build_execution_analytics(
    *,
    orders_sampled: int = 24,
    median_latency_ms: float = 85.0,
    p95_latency_ms: float = 210.0,
    median_slippage_bps: float = 6.5,
    fill_rate_pct: float = 92.0,
    partial_fill_pct: float = 4.0,
    ibkr_connected: bool = False,
    degraded: bool = False,
) -> Dict[str, Any]:
    status = evaluate_fill_quality(
        slippage_bps=median_slippage_bps,
        fill_rate_pct=fill_rate_pct,
        partial_fill_pct=partial_fill_pct,
    )
    if orders_sampled < 5 or degraded:
        status = STATUS_UNKNOWN

    sample_state = resolve_sample_state(
        orders_sampled=orders_sampled,
        ibkr_connected=ibkr_connected,
        degraded=degraded or orders_sampled < 5,
    )

    body = {
        "orders_sampled": orders_sampled,
        "sample_state": sample_state,
        "sample_state_label": SAMPLE_STATE_LABELS.get(sample_state, ""),
        "structure": {
            "latency_bucket": _latency_bucket(median_latency_ms),
            "slippage_band": "within band" if median_slippage_bps <= 12 else "elevated",
            "fill_quality_status": status,
        },
        "latency": {
            "median_ms": median_latency_ms,
            "p95_ms": p95_latency_ms,
            "bucket": _latency_bucket(median_latency_ms),
        },
        "slippage": {
            "median_bps": median_slippage_bps,
            "label": "within band" if median_slippage_bps <= 12 else "elevated",
        },
        "fill_quality": {
            "fill_rate_pct": fill_rate_pct,
            "partial_fill_pct": partial_fill_pct,
            "status": status,
            "status_label": STATUS_LABELS.get(status, ""),
        },
        "ibkr_connected": ibkr_connected,
        "authorizes_execution": False,
        "backtest_not_live_edge": True,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_EXECUTION_ANALYTICS,
        source="mock-execution-analytics-stub",
        degraded=degraded or not ibkr_connected,
        data_mode="ops_probe" if ibkr_connected else "research_only",
        extra=body,
    )


def build_empty_execution_analytics_state() -> Dict[str, Any]:
    """Structure + empty sample — honest degraded when no fills."""
    return build_execution_analytics(
        orders_sampled=0,
        median_latency_ms=0.0,
        p95_latency_ms=0.0,
        median_slippage_bps=0.0,
        fill_rate_pct=0.0,
        partial_fill_pct=0.0,
        ibkr_connected=False,
        degraded=True,
    )


def build_recent_fills_summary(fills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate user-supplied fill rows for router payloads."""
    if not fills:
        return build_execution_analytics(degraded=True)
    slips = [float(f.get("slippage_bps") or 0) for f in fills]
    rates = [100.0 if f.get("filled") else 0.0 for f in fills]
    return build_execution_analytics(
        orders_sampled=len(fills),
        median_slippage_bps=sum(slips) / len(slips) if slips else 0,
        fill_rate_pct=sum(rates) / len(rates) if rates else 0,
        ibkr_connected=True,
        degraded=False,
    )
