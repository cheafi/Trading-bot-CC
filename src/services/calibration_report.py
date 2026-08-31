"""Calibration quarterly report — confidence vs outcome (CCX-045)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.forward_outcomes import load_forward_outcomes
from src.services.decision_journal import load_recent


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bucket_confidence(p: Optional[float]) -> str:
    if p is None:
        return "unknown"
    if p >= 0.7:
        return "high"
    if p >= 0.45:
        return "medium"
    return "low"


def build_calibration_report(*, limit: int = 200) -> Dict[str, Any]:
    """
    Quarterly-style calibration from forward outcomes + decision journal.
    Research_only — does not change deploy authority.
    """
    outcomes = load_forward_outcomes(limit=limit)
    journal = load_recent(limit=limit)

    marks: List[Dict[str, Any]] = []
    for o in outcomes:
        mark_r = o.get("mark_r")
        if mark_r is None:
            continue
        marks.append(
            {
                "decision_id": o.get("decision_id"),
                "ticker": o.get("ticker"),
                "horizon": o.get("horizon"),
                "mark_r": float(mark_r),
                "win": float(mark_r) > 0,
            }
        )

    wins = sum(1 for m in marks if m.get("win"))
    total = len(marks)
    win_rate = round(wins / total, 3) if total else None

    journal_with_prob = [
        j for j in journal if j.get("expected_probability") is not None
    ]
    buckets: Dict[str, Dict[str, int]] = {}
    for j in journal_with_prob:
        bucket = _bucket_confidence(j.get("expected_probability"))
        buckets.setdefault(bucket, {"count": 0, "with_outcome": 0})
        buckets[bucket]["count"] += 1
        did = j.get("decision_id")
        if did and any(m.get("decision_id") == did for m in marks):
            buckets[bucket]["with_outcome"] += 1

    return {
        "as_of": _utcnow_iso(),
        "authority": "research_only",
        "sample": {
            "forward_marks": total,
            "journal_entries": len(journal),
            "win_rate": win_rate,
        },
        "confidence_buckets": buckets,
        "recent_marks": marks[-10:],
        "headline": (
            f"Calibration: {total} marks, win rate {win_rate:.0%}"
            if win_rate is not None and total
            else "Insufficient forward marks for calibration — continue logging decisions."
        ),
        "recommendation": (
            "Review high-confidence losses in Belief Review ritual."
            if total >= 5 and win_rate is not None and win_rate < 0.45
            else "Continue forward outcome marks at T+20."
        ),
    }
