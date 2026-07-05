"""
Execution console — extended TCA / ops analytics.

Never fakes broker readiness or authorizes trades.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.execution_analytics import (
    build_execution_analytics_from_ibkr,
    build_empty_execution_analytics_state,
)

AUTHORITY_OPS = "ops_only"


def _fill_by_ticker(fills: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_sym: Dict[str, List[Dict[str, Any]]] = {}
    for f in fills or []:
        sym = str(f.get("symbol") or "").upper()
        if not sym:
            continue
        by_sym.setdefault(sym, []).append(f)
    out: Dict[str, Dict[str, Any]] = {}
    for sym, rows in by_sym.items():
        slips = [float(r.get("slippage_bps") or 8.0) for r in rows]
        out[sym] = {
            "count": len(rows),
            "median_slippage_bps": round(sum(slips) / len(slips), 1),
            "label": f"{sym}: n={len(rows)} fills — ops context",
        }
    return out


def build_execution_console(
    fills: Optional[List[Dict[str, Any]]] = None,
    *,
    ibkr_connected: bool = False,
    execution_readiness: Optional[Dict[str, Any]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Extended execution layer for IBKR / Ops / post-trade review."""
    fill_rows = list(fills or [])
    if ibkr_connected and fill_rows and not degraded:
        core = build_execution_analytics_from_ibkr(fill_rows, ibkr_connected=True)
    elif ibkr_connected and not degraded:
        core = build_empty_execution_analytics_state()
    else:
        core = build_empty_execution_analytics_state()

    readiness = execution_readiness or {}
    broker_drift = "stable"
    if readiness.get("blocked"):
        broker_drift = "blocked"
    elif not ibkr_connected:
        broker_drift = "disconnected"
    elif readiness.get("degraded"):
        broker_drift = "degraded"

    partial_rate = (core.get("fill_quality") or {}).get("partial_fill_pct") or 0
    latency_med = (core.get("latency") or {}).get("median_ms") or 0

    return {
        "authority": AUTHORITY_OPS,
        "may_authorize_deploy": False,
        "authorizes_execution": False,
        "degraded": degraded or core.get("degraded", True),
        "core_analytics": core,
        "extended": {
            "signal_to_order_latency_ms": latency_med,
            "order_to_fill_latency_ms": latency_med,
            "implementation_shortfall_bps": (core.get("slippage") or {}).get("median_bps"),
            "partial_fill_rate_pct": partial_rate,
            "cancel_replace_frequency": "unknown — session log not wired",
            "algo_selection": "manual_default — recommendation only",
            "fill_by_ticker": _fill_by_ticker(fill_rows),
            "broker_readiness_drift": broker_drift,
            "handoff_status": (
                "ready" if readiness.get("ready") else "blocked_or_degraded"
            ),
            "bracket_template_quality": "confirm on dossier — not auto-routed",
        },
        "strip_line": _console_strip(core, broker_drift),
    }


def _console_strip(core: Dict[str, Any], broker_drift: str) -> str:
    sample = core.get("sample_state") or "insufficient_sample"
    n = core.get("orders_sampled") or 0
    if broker_drift == "disconnected":
        return "Execution console: IBKR disconnected — not broker-ready"
    if sample == "live_sample":
        return f"Execution console: live n={n} · broker {broker_drift} — ops only"
    if sample == "stub_sample":
        return "Execution console: MOCK/DEGRADED stub — ops context only"
    return f"Execution console: insufficient sample (n={n}) — monitor only"
