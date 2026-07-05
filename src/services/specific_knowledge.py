"""
《纳瓦尔宝典》specific knowledge — competence fit vs borrowed conviction.
"""

from __future__ import annotations

from typing import Any, Dict, List

COMPETENCE_LABELS: Dict[str, str] = {
    "strong_fit": "inside circle — thesis + data support judgment",
    "partial_fit": "partial fit — monitor before sizing",
    "borrowed": "borrowed conviction — narrative without owned edge",
    "outside": "outside competence — research only",
}


def evaluate_competence_fit(row: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic competence from thesis, data confidence, calibration."""
    thesis = float(row.get("thesis_conf") or row.get("thesis_quality") or 0)
    data = float(row.get("data_conf") or (row.get("evidence_quality") or {}).get("data_conf") or 0)
    cal_n = int((row.get("evidence_quality") or {}).get("sample_count") or row.get("calibration_n") or 0)
    why_now = str(row.get("why_now") or "")
    narrative_heavy = len(why_now) > 120 and thesis < 0.55

    borrowed_risk = "low"
    if narrative_heavy or (thesis >= 0.6 and data < 0.45):
        borrowed_risk = "high"
    elif thesis < 0.5 or data < 0.5:
        borrowed_risk = "medium"

    if thesis >= 0.65 and data >= 0.6 and cal_n >= 20:
        fit = "strong_fit"
    elif thesis >= 0.5 and data >= 0.45:
        fit = "partial_fit"
    elif borrowed_risk == "high":
        fit = "borrowed"
    else:
        fit = "outside"

    labels: List[str] = [COMPETENCE_LABELS[fit]]
    if borrowed_risk == "high":
        labels.append("borrowed conviction risk — verify before acting")

    return {
        "competence_fit": fit,
        "competence_label": COMPETENCE_LABELS[fit],
        "borrowed_conviction_risk": borrowed_risk,
        "labels": labels,
    }


def tags_for_playbook_row(row: Dict[str, Any], **_kwargs: Any) -> Dict[str, Any]:
    c = evaluate_competence_fit(row)
    return {
        "competence_fit": c["competence_fit"],
        "competence_label": c["competence_label"],
        "borrowed_conviction_risk": c["borrowed_conviction_risk"],
    }
