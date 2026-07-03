"""
Operator surface blocks — NOW / WHY / ALLOWED / BLOCKED / VALID CANDIDATES / NEXT.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.authority_engine import (
    allowed_line,
    blocked_line,
    next_action,
    primary_operator_state,
    valid_candidates_line,
    why_lines,
)


def build_research_surface_block(
    truth: Optional[Dict[str, Any]] = None,
    *,
    surface: str = "discovery",
    extra_blocker: str = "",
    extra_next: str = "",
) -> Dict[str, Any]:
    """NOW / BLOCKER / NEXT for research-only surfaces (Flow pattern)."""
    t = dict(truth or {})
    posture = primary_operator_state(t)
    blocker = str(extra_blocker or t.get("primary_blocker") or "deploy authority blocked").strip()
    if not t.get("deploy_authority") and "deploy" not in blocker.lower():
        blocker = f"{blocker} · no deploy authority"
    surface_next = {
        "discovery": "promote names to Playbook — scan evidence only",
        "flow": "confirm in Playbook / Dossier — flow is supporting only",
        "funds": "review sleeve research — not live allocation",
        "strategy": "calibrate when closed-trade evidence exists",
        "agent": "use Dashboard + Playbook for deploy gates",
        "shadow": "shadow challengers — no capital impact until promoted",
    }
    surf = str(surface or "research").lower()
    nxt = extra_next or surface_next.get(surf, "monitor only")
    if not extra_next and t.get("deploy_authority"):
        nxt = next_action(t)
    return {
        "surface": str(surface or "research").lower(),
        "now": posture.get("primary") or "MONITOR ONLY",
        "blocker": blocker,
        "next": nxt,
        "details_collapsed": True,
        "research_only": not bool(t.get("deploy_authority")),
    }


def build_operator_block(
    truth: Optional[Dict[str, Any]] = None,
    page: str = "dashboard",
) -> Dict[str, Any]:
    """Canonical operator block for dashboard / playbook / agent surfaces."""
    t = dict(truth or {})
    posture = primary_operator_state(t)
    why_parts = why_lines(t)
    why = " + ".join(why_parts) if why_parts else str(t.get("primary_blocker") or "upgrade conditions not met")
    block = {
        "page": str(page or "dashboard").lower(),
        "now": posture.get("now") or posture.get("primary") or "MONITOR ONLY",
        "primary": posture.get("primary") or "MONITOR ONLY",
        "secondary": posture.get("secondary") or "",
        "why": why,
        "allowed": allowed_line(t),
        "blocked": blocked_line(t),
        "valid_candidates": valid_candidates_line(t),
        "next": next_action(t),
        "truth_strip": t.get("truth_strip") or t.get("typed_freshness_display") or "",
        "regime_state": str(t.get("regime_state") or "WAIT").upper(),
        "deploy_authority": bool(t.get("deploy_authority")),
        "repair_priority": list(t.get("repair_priority") or [])[:5],
    }
    if page == "agent":
        block["agent_blocker_compact"] = True
        block["why"] = str(t.get("primary_blocker") or why_parts[0] if why_parts else why)
    return block
