"""Outside View Engine stub — base rates by decision class (research_only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def build_outside_view_base_rate(*, setup_type: str = "") -> Dict[str, Any]:
    kind = str(setup_type or "").strip().lower() or "generic_breakout"
    return {
        "status": "stub",
        "authority": "research_only",
        "setup_type": kind,
        "headline": f"Outside View · 外部視角 — {kind} base rates (research only)",
        "four_questions": {
            "know": f"Historical hit rate for setup class '{kind}' (not this ticker).",
            "believe": "Inside-view thesis must beat class base rate to earn capital.",
            "doubt": "Sample size, regime conditioning, and selection bias unknowns.",
            "act": "Adjust conviction vs class prior; no auto-deploy.",
        },
        "base_rate": {
            "class": kind,
            "historical_success_rate": None,
            "sample_n": 0,
            "regime_adjusted": None,
            "confidence": "low",
            "note": "Stub — wire calibration DB in CCX-158 Phase 2.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
