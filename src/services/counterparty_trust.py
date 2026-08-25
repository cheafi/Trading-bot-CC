"""
《乱世华尔街》counterparty / execution trust — broker plumbing before hero trades.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

TRUST_LABELS: Dict[str, str] = {
    "trusted": "Execution path trusted — still subject to regime gate",
    "monitor_only": "Connected for monitoring — not full deploy trust",
    "degraded": "Broker degraded — confirm fills and brackets manually",
    "untrusted": "Counterparty path untrusted — no new risk",
}


def evaluate_counterparty_trust(
    *,
    ibkr_health: Optional[Dict[str, Any]] = None,
    ibkr_connected: bool = False,
    bracket_ready: bool = False,
    circuit_breaker: bool = False,
) -> Dict[str, Any]:
    """Map IBKR health snapshot to execution-trust posture."""
    health = ibkr_health or {}
    if circuit_breaker:
        return {
            "trust_level": "untrusted",
            "headline": TRUST_LABELS["untrusted"],
            "labels": [TRUST_LABELS["untrusted"], "Circuit breaker active"],
            "deploy_trusted": False,
            "monitoring_only": True,
        }

    session_ok = health.get("session_operational") or ibkr_connected
    handoff = health.get("handoff_status") or ""
    exec_status = health.get("execution_status") or ""
    degraded = bool(health.get("degraded_reasons"))

    if not session_ok:
        return {
            "trust_level": "untrusted",
            "headline": TRUST_LABELS["untrusted"],
            "labels": [TRUST_LABELS["untrusted"]],
            "deploy_trusted": False,
            "monitoring_only": True,
        }

    if handoff == "ready" and exec_status == "ready" and bracket_ready and not degraded:
        return {
            "trust_level": "trusted",
            "headline": TRUST_LABELS["trusted"],
            "labels": [TRUST_LABELS["trusted"]],
            "deploy_trusted": True,
            "monitoring_only": False,
        }

    if handoff == "monitoring_only" or health.get("monitoring_only"):
        return {
            "trust_level": "monitor_only",
            "headline": TRUST_LABELS["monitor_only"],
            "labels": [TRUST_LABELS["monitor_only"]],
            "deploy_trusted": False,
            "monitoring_only": True,
        }

    if degraded or exec_status != "ready":
        return {
            "trust_level": "degraded",
            "headline": TRUST_LABELS["degraded"],
            "labels": [TRUST_LABELS["degraded"], *(health.get("degraded_reasons") or [])[:2]],
            "deploy_trusted": False,
            "monitoring_only": True,
        }

    return {
        "trust_level": "monitor_only",
        "headline": TRUST_LABELS["monitor_only"],
        "labels": [TRUST_LABELS["monitor_only"]],
        "deploy_trusted": False,
        "monitoring_only": True,
    }
