"""Decision Committee stub — virtual members challenge deploy (research_only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.deployment_manifest import audit_deploy_open_provenance

_COMMITTEE_ROLES = (
    "Risk Officer",
    "PM",
    "Macro",
    "Execution",
    "Behavior",
    "Knowledge",
    "Capital Allocation",
)


def build_committee_review(
    *,
    ticker: str = "",
    deploy_open: bool = False,
    llm_vote: bool = False,
) -> Dict[str, Any]:
    sym = str(ticker or "").upper().strip() or "GENERIC"
    members: List[Dict[str, Any]] = []
    for role in _COMMITTEE_ROLES:
        members.append(
            {
                "role": role,
                "stance": "stub",
                "challenge": f"{role}: stub challenge for {sym}.",
                "authority": "research_only",
                "broker_eligible": False,
                "llm_vote_affects_broker": False,
            }
        )
    provenance = audit_deploy_open_provenance(
        deploy_open=deploy_open,
        source="decision_committee",
        llm_vote=llm_vote,
    )
    return {
        "status": "stub",
        "authority": "research_only",
        "ticker": sym,
        "headline": f"Decision Committee · 決策委員會 — {sym} (research only)",
        "ciio_brief": "Stub — CIIO explains thesis; committee debates.",
        "four_questions": {
            "know": "Facts presented by CIIO with provenance.",
            "believe": "Thesis and conviction under committee scrutiny.",
            "doubt": "Dissenting views and missing evidence.",
            "act": "Human PM decides; committee never authorizes deploy.",
        },
        "members": members,
        "deploy_open_provenance": provenance,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
