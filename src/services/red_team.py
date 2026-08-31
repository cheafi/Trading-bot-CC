"""Red Team Engine stub — structured pre-deploy challenge (research_only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def build_red_team_challenge(*, ticker: str = "") -> Dict[str, Any]:
    sym = str(ticker or "").upper().strip() or "GENERIC"
    return {
        "status": "stub",
        "authority": "research_only",
        "ticker": sym,
        "headline": f"Red Team · 紅隊質詢 — {sym} (research only)",
        "four_questions": {
            "know": "Historical failure modes for this setup class; regime facts.",
            "believe": "Thesis under challenge — steel-man the opposing case.",
            "doubt": "What would invalidate? What would change our mind?",
            "act": "Complete red team before deploy; never blocks human authority.",
        },
        "challenges": {
            "why_this_fails": "Stub — enumerate top 3 failure paths.",
            "strongest_opposing_case": "Stub — best argument against deploy.",
            "alternative_explanation": "Stub — non-thesis explanation of price action.",
            "would_invalidate": "Stub — measurable kill triggers.",
            "would_change_mind": "Stub — evidence that upgrades or downgrades belief.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
