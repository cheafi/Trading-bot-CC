"""Decision Health stub — calibration inputs (research_only, non-blocking)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def build_decision_health_summary() -> Dict[str, Any]:
    return {
        "status": "stub",
        "authority": "research_only",
        "headline": "Decision Health · 決策健康 — calibration inputs (non-blocking)",
        "four_questions": {
            "know": "Self-reported state: rushed, emotional, distracted, sleep.",
            "believe": "Decisions today and disagreement level vs baseline.",
            "doubt": "Uncertainty score — honest doubt improves calibration.",
            "act": "Inputs only; never blocks deploy_open or human authority.",
        },
        "inputs": {
            "rushed": None,
            "emotional": None,
            "distracted": None,
            "sleep_hours": None,
            "decisions_today": None,
            "uncertainty": None,
            "disagreement": None,
        },
        "note": "Stub — CCX-160 Phase 2 will persist rolling calibration.",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
