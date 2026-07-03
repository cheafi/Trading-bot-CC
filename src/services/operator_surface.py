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
