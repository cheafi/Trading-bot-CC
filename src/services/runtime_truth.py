from __future__ import annotations

from typing import Any, Dict, Optional


def engine_runtime_snapshot(engine: Any) -> Dict[str, Any]:
    """Canonical runtime snapshot shared across Today / Header / Ops."""
    if not engine:
        return {
            "running": False,
            "dry_run": True,
            "cycle_count": 0,
            "cached_recommendations": 0,
            "signals_today": 0,
            "trades_today": 0,
            "circuit_breaker": False,
            "circuit_breaker_reason": "",
        }

    cb = getattr(engine, "circuit_breaker", None)
    return {
        "running": bool(getattr(engine, "_running", False)),
        "dry_run": bool(getattr(engine, "dry_run", True)),
        "cycle_count": int(getattr(engine, "_cycle_count", 0)),
        "cached_recommendations": len(getattr(engine, "_cached_recommendations", [])),
        "signals_today": len(getattr(engine, "_signals_today", [])),
        "trades_today": len(getattr(engine, "_trades_today", [])),
        "circuit_breaker": bool(getattr(cb, "triggered", False)) if cb else False,
        "circuit_breaker_reason": str(getattr(cb, "trigger_reason", "") or ""),
    }


def merge_execution_runtime_truth(
    execution_readiness: Optional[Dict[str, Any]] = None,
    *,
    engine: Any = None,
) -> Dict[str, Any]:
    """
    Merge router-local execution_readiness with canonical engine runtime truth.

    Router payloads may already know broker/gateway state; runtime fields must come
    from one canonical engine snapshot so all surfaces inherit the same engine/breaker truth.
    """
    merged: Dict[str, Any] = dict(execution_readiness or {})
    runtime = engine_runtime_snapshot(engine)
    merged["engine_running"] = bool(
        merged.get("engine_running") if merged.get("engine_running") is not None else runtime["running"]
    )
    merged["circuit_breaker"] = bool(
        merged.get("circuit_breaker")
        if merged.get("circuit_breaker") is not None
        else runtime["circuit_breaker"]
    )
    if runtime.get("circuit_breaker_reason") and not merged.get("circuit_breaker_reason"):
        merged["circuit_breaker_reason"] = runtime["circuit_breaker_reason"]
    return merged
