"""
Event / news / insider / smart-money intelligence — downgrade and context only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.event_noise_filter import build_event_risk_context
from src.services.insider_tracker import build_insider_context
from src.services.institutional_13f import build_institutional_context

AUTHORITY_RESEARCH = "research_only"
AUTHORITY_CONFIRMATION = "confirmation_only"


def build_event_intel_bundle(
    ticker: str = "SPY",
    *,
    event_risks: Optional[List[str]] = None,
    headlines: Optional[List[Dict[str, Any]]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Aggregate event intelligence for Dossier / Playbook support."""
    sym = ticker.upper().strip() or "SPY"
    event_ctx = build_event_risk_context(ticker=sym, degraded=degraded)
    insider = build_insider_context(ticker=sym)
    inst = build_institutional_context(ticker=sym)

    severity = "low"
    risks = list(event_risks or [])
    sym_hits = [r for r in risks if sym in r.upper()]
    if sym_hits:
        severity = "elevated"

    downgrade_path: List[str] = []
    if severity == "elevated":
        downgrade_path.append("Event proximity — downgrade urgency on board support")
    if (event_ctx.get("downgrade_only") or event_ctx.get("provenance", {}).get("downgrade_only")):
        downgrade_path.append("News filter — downgrade-only framing")

    return {
        "authority": AUTHORITY_CONFIRMATION,
        "may_authorize_deploy": False,
        "downgrade_only": True,
        "degraded": degraded,
        "ticker": sym,
        "event_risk_severity": {
            "level": severity,
            "hits": sym_hits[:2],
            "label": f"Event severity {severity} — never upgrades WAIT alone",
        },
        "event_noise_filter": event_ctx,
        "insider_cluster": {
            **(insider if isinstance(insider, dict) else {}),
            "lag_disclosure": "Form 4 lag days–weeks — research only",
        },
        "institutional_13f": {
            **(inst if isinstance(inst, dict) else {}),
            "lag_disclosure": "13F quarterly lag — research only",
        },
        "smart_money_alignment": {
            "score": None,
            "label": "Smart-money alignment — lagged research context only",
        },
        "narrative_contradiction": {
            "label": "Use AI contradiction layer on dossier — confirm-only",
        },
        "headline_shock_triage": {
            "label": "Shock vs structural damage — triage in dossier, not deploy",
        },
        "downgrade_path": downgrade_path,
        "strip_line": (
            f"Event intel {sym}: severity {severity} — downgrade/context only"
        ),
    }
