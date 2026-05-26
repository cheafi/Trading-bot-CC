"""Operator console — system verdict, blockers, next actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _section_state(
    *,
    active: bool,
    sample: int = 0,
    min_sample: int = 5,
    loaded: bool = False,
    stale: bool = False,
) -> Dict[str, Any]:
    if not active:
        return {"state": "inactive", "label": "Inactive", "detail": "Engine not running"}
    if not loaded:
        return {
            "state": "not_loaded",
            "label": "Not loaded",
            "detail": "Click refresh or start engine",
        }
    if stale:
        return {"state": "stale", "label": "Stale", "detail": "Data older than threshold"}
    if sample < min_sample:
        return {
            "state": "insufficient_sample",
            "label": "Insufficient sample",
            "detail": f"Need {min_sample}+ observations (have {sample})",
        }
    return {"state": "active", "label": "Active", "detail": "Evidence available"}


def build_ops_operator_console(
    *,
    ops_status: Optional[Dict[str, Any]] = None,
    cc_header: Optional[Dict[str, Any]] = None,
    today: Optional[Dict[str, Any]] = None,
    self_learn: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Single operator verdict from engine + header + today cache."""
    ops_status = ops_status or {}
    cc_header = cc_header or {}
    today = today or {}
    eng = {**(cc_header.get("engine") or {}), **(ops_status.get("engine") or {})}
    components = {
        **(ops_status.get("components") or {}),
        **(cc_header.get("components") or {}),
    }

    running = bool(eng.get("running"))
    dry_run = bool(eng.get("dry_run", True))
    breaker = bool(eng.get("circuit_breaker"))
    cycles = int(eng.get("cycle_count") or 0)
    signals_today = int(eng.get("signals_today") or 0)
    cached_recs = int(eng.get("cached_recommendations") or 0)
    last_cycle = eng.get("last_cycle")
    ibkr = cc_header.get("ibkr") or {}

    blockers: List[str] = []
    if not running:
        blockers.append("Trading engine is stopped")
    if breaker:
        blockers.append(
            f"Circuit breaker: {eng.get('circuit_breaker_reason') or 'tripped'}"
        )
    if cycles == 0 and running:
        blockers.append("No successful engine cycles yet")
    if cached_recs == 0:
        blockers.append("No cached recommendations")
    if signals_today == 0 and running:
        blockers.append("Zero signals generated today")
    freshness = cc_header.get("freshness") or {}
    if freshness.get("worst_tier") not in (None, "FRESH"):
        blockers.append(f"Market data tier: {freshness.get('worst_tier')}")
    if not ibkr.get("connected") and not components.get("broker"):
        blockers.append("Broker not connected (paper handoff unavailable)")

    if breaker:
        verdict = "LIVE_BLOCKED"
        verdict_detail = "Circuit breaker active — do not deploy"
    elif not running:
        verdict = "NOT_RUNNABLE"
        verdict_detail = "Engine stopped — infrastructure may be up but loop is off"
    elif dry_run:
        verdict = "PAPER_ONLY"
        verdict_detail = "Paper/dry-run only — not live capital"
    else:
        verdict = "RUNNABLE"
        verdict_detail = "Engine running in live mode — verify gates before deploy"

    next_actions: List[Dict[str, str]] = []
    if not running:
        next_actions.append(
            {"step": "1", "action": "Start trading engine", "why": "Loop is stopped"}
        )
    if running and cycles == 0:
        next_actions.append(
            {"step": "2", "action": "Run first engine cycle", "why": "Validate pipeline"}
        )
    if not ibkr.get("gateway_reachable"):
        next_actions.append(
            {
                "step": "3",
                "action": "Start IB Gateway / verify host",
                "why": "Gateway unreachable",
            }
        )
    if cached_recs == 0:
        next_actions.append(
            {
                "step": "4",
                "action": "Refresh recommendation cache",
                "why": "No cached recs for Today tab",
            }
        )
    if signals_today == 0 and running:
        next_actions.append(
            {
                "step": "5",
                "action": "Inspect filter funnel / regime gate",
                "why": "Engine ran but produced no signals",
            }
        )
    if not next_actions:
        next_actions.append(
            {
                "step": "✓",
                "action": "Monitor positions & alerts",
                "why": "Core loop appears healthy",
            }
        )

    why_no_signals: List[Dict[str, Any]] = []
    diagnosis = today.get("no_setup_diagnosis") or {}
    breakdown = diagnosis.get("breakdown") or {}
    if breakdown:
        for k, v in sorted(breakdown.items(), key=lambda x: -x[1]):
            why_no_signals.append({"gate": k, "count": v})
    elif not running:
        why_no_signals.append({"gate": "engine_stopped", "count": 1})
    elif today.get("tradeability") == "NO_TRADE":
        why_no_signals.append({"gate": "regime_no_trade", "count": 1})
    else:
        why_no_signals.append(
            {"gate": "scanner_selective", "note": "No breakdown in today cache"}
        )

    closed_trades = 0
    if self_learn and self_learn.get("engine_state"):
        closed_trades = int(self_learn.get("closed_trades_available") or 0)

    sections = {
        "self_learning": _section_state(
            active=running,
            sample=closed_trades,
            min_sample=20,
            loaded=bool(self_learn),
        ),
        "thompson_sizing": _section_state(
            active=running, sample=closed_trades, min_sample=30, loaded=False
        ),
        "feature_ic": _section_state(
            active=running, sample=closed_trades, min_sample=50, loaded=False
        ),
        "pipeline_stats": _section_state(active=running, loaded=cycles > 0),
        "execution_metrics": _section_state(
            active=running,
            sample=int(eng.get("trades_today") or 0),
            min_sample=1,
            loaded=bool(eng.get("trades_today")),
        ),
    }

    component_evidence = []
    for name, ok in sorted(components.items()):
        component_evidence.append(
            {
                "name": name,
                "ok": bool(ok),
                "label": "OK" if ok else "FAIL",
                "evidence": (
                    "Probe passed"
                    if ok
                    else "Failed probe — not evidence of runtime health alone"
                ),
            }
        )

    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "system_verdict": verdict,
        "verdict_detail": verdict_detail,
        "runnable": verdict == "RUNNABLE",
        "blockers": blockers,
        "next_actions": next_actions,
        "last_events": {
            "last_cycle": last_cycle,
            "last_brief": (cc_header.get("brief_status") or {}).get("latest", {}).get(
                "as_of"
            ),
            "ibkr_heartbeat": ibkr.get("last_heartbeat"),
            "market_data_tier": freshness.get("worst_tier"),
        },
        "engine": {
            "running": running,
            "dry_run": dry_run,
            "cycle_count": cycles,
            "signals_today": signals_today,
            "trades_today": int(eng.get("trades_today") or 0),
            "cached_recommendations": cached_recs,
            "circuit_breaker": breaker,
        },
        "why_no_signals": why_no_signals,
        "section_states": sections,
        "component_evidence": component_evidence,
        "ibkr": {
            "connected": bool(ibkr.get("connected")),
            "gateway": bool(ibkr.get("gateway_reachable")),
            "mode": ibkr.get("mode") or "paper",
            "account_sync": ibkr.get("account"),
        },
        "providers": cc_header.get("providers") or ops_status.get("providers"),
        "uptime": ops_status.get("uptime"),
        "latency": ops_status.get("latency"),
    }
