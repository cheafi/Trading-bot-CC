"""
Machine-of-machines registry — Principles series operating layer.

Eight decision machines with health + constraint per machine.
Used by Ops health panel; does not replace honest board gates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

MachineId = Literal[
    "data_integrity",
    "regime",
    "playbook",
    "dossier",
    "portfolio",
    "execution",
    "review",
    "learning",
]

HealthState = Literal["healthy", "degraded", "blocked", "inactive"]

MACHINE_CATALOG: Dict[str, Dict[str, str]] = {
    "data_integrity": {
        "label": "Data Integrity",
        "role": "Facts vs stale vs estimated — radical transparency",
        "constraint": "No action on unknown or stale facts",
    },
    "regime": {
        "label": "Regime",
        "role": "Macro gate — tradeability and crisis posture",
        "constraint": "WAIT / NO_TRADE binds all downstream machines",
    },
    "playbook": {
        "label": "Playbook",
        "role": "Ranked opportunities with principle tags",
        "constraint": "Rank ≠ permission — evidence grade required",
    },
    "dossier": {
        "label": "Dossier",
        "role": "Single-name memo — known facts and unknowns",
        "constraint": "Research-only when process grade C or D",
    },
    "portfolio": {
        "label": "Portfolio",
        "role": "Fit, sizing, and concentration",
        "constraint": "Portfolio machine cannot override regime gate",
    },
    "execution": {
        "label": "Execution",
        "role": "Broker handoff and order path",
        "constraint": "No live deploy without tested execution path",
    },
    "review": {
        "label": "Review",
        "role": "Post-decision audit — process vs outcome",
        "constraint": "Judge process quality independent of P&L",
    },
    "learning": {
        "label": "Learning",
        "role": "Pain log, root cause, encoded lessons",
        "constraint": "Every failure must produce a machine update",
    },
}


def _health_from_signals(
    *,
    active: bool,
    degraded: bool = False,
    blocked: bool = False,
) -> HealthState:
    if not active:
        return "inactive"
    if blocked:
        return "blocked"
    if degraded:
        return "degraded"
    return "healthy"


def evaluate_machine_health(
    machine_id: MachineId,
    *,
    ops_status: Optional[Dict[str, Any]] = None,
    today: Optional[Dict[str, Any]] = None,
    cc_header: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    error_log_count: int = 0,
) -> Dict[str, Any]:
    """Single machine health + constraint."""
    ops_status = ops_status or {}
    today = today or {}
    cc_header = cc_header or {}
    execution_readiness = execution_readiness or {}
    meta = MACHINE_CATALOG.get(machine_id, {})

    eng = {**(cc_header.get("engine") or {}), **(ops_status.get("engine") or {})}
    running = bool(eng.get("running"))
    cycles = int(eng.get("cycle_count") or 0)
    cached = int(eng.get("cached_recommendations") or 0)
    tb = str(
        (today.get("decision_model") or {}).get("honest_tradeability")
        or (today.get("market_regime") or {}).get("tradeability")
        or "WAIT"
    )
    trust = today.get("trust") or {}
    stale = bool(trust.get("stale"))
    posture = today.get("principles_posture") or {}

    health: HealthState = "inactive"
    detail = meta.get("constraint", "")

    if machine_id == "data_integrity":
        freshness = (cc_header.get("freshness") or {}).get("worst_tier")
        health = _health_from_signals(
            active=True,
            degraded=stale or freshness not in (None, "FRESH"),
            blocked=posture.get("fact_integrity") == "degraded",
        )
        detail = f"Freshness tier: {freshness or 'unknown'}; stale={stale}"
    elif machine_id == "regime":
        health = _health_from_signals(
            active=True,
            blocked=tb in ("WAIT", "NO_TRADE"),
            degraded=not (today.get("market_regime") or {}).get("should_trade", True),
        )
        detail = f"Tradeability: {tb}"
    elif machine_id == "playbook":
        health = _health_from_signals(
            active=running and cached > 0,
            degraded=cycles == 0 or stale,
            blocked=posture.get("action_blocked_by_principle", False),
        )
        detail = f"Cached recs: {cached}; blocked setups: {posture.get('blocked_setup_count', 0)}"
    elif machine_id == "dossier":
        health = _health_from_signals(active=True, degraded=error_log_count > 3)
        detail = "Stock-intel loads independently of engine cycle"
    elif machine_id == "portfolio":
        health = _health_from_signals(
            active=True,
            blocked=tb in ("WAIT", "NO_TRADE"),
        )
        detail = "Portfolio fit available; regime gate binds sizing"
    elif machine_id == "execution":
        ibkr = execution_readiness or cc_header.get("ibkr") or {}
        connected = bool(ibkr.get("connected") or ibkr.get("session_usable"))
        handoff = bool(execution_readiness.get("trade_handoff_ready"))
        health = _health_from_signals(
            active=connected,
            degraded=connected and not handoff,
            blocked=not running,
        )
        detail = f"Broker connected={connected}; handoff={handoff}"
    elif machine_id == "review":
        health = _health_from_signals(active=cycles > 0, degraded=not running)
        detail = "Review machine active after closed trades or decisions"
    elif machine_id == "learning":
        health = _health_from_signals(
            active=True,
            degraded=error_log_count > 0,
            blocked=False,
        )
        detail = f"Session error log entries: {error_log_count}"

    return {
        "id": machine_id,
        "label": meta.get("label", machine_id),
        "role": meta.get("role", ""),
        "constraint": meta.get("constraint", ""),
        "health": health,
        "health_label": health.replace("_", " "),
        "detail": detail,
    }


def build_machines_health_panel(
    *,
    ops_status: Optional[Dict[str, Any]] = None,
    today: Optional[Dict[str, Any]] = None,
    cc_header: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    error_log_count: int = 0,
) -> Dict[str, Any]:
    """Ops machines health panel — all eight machines."""
    machines: List[Dict[str, Any]] = []
    blocked_n = 0
    degraded_n = 0
    for mid in MACHINE_CATALOG:
        m = evaluate_machine_health(
            mid,  # type: ignore[arg-type]
            ops_status=ops_status,
            today=today,
            cc_header=cc_header,
            execution_readiness=execution_readiness,
            error_log_count=error_log_count,
        )
        machines.append(m)
        if m["health"] == "blocked":
            blocked_n += 1
        elif m["health"] == "degraded":
            degraded_n += 1

    if blocked_n >= 2:
        overall = "blocked"
        headline = f"{blocked_n} machines blocked — respect constraints before deploy"
    elif degraded_n >= 3:
        overall = "degraded"
        headline = f"{degraded_n} machines degraded — verify facts and process"
    elif all(m["health"] in ("healthy", "inactive") for m in machines):
        overall = "healthy"
        headline = "Decision machines aligned — monitor constraints"
    else:
        overall = "degraded"
        headline = "Mixed machine health — check Ops panel"

    return {
        "mode": "principles_series",
        "overall": overall,
        "headline": headline,
        "machine_count": len(machines),
        "blocked_count": blocked_n,
        "degraded_count": degraded_n,
        "machines": machines,
    }
