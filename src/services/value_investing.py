"""
《巴芒演义》value-investing mode — margin of safety over narrative.

Business quality + valuation + patience; not scanner momentum theater.
"""

from __future__ import annotations

from typing import Any, Dict, List

BAMANG_LABELS: Dict[str, str] = {
    "moat_unclear": "moat unclear — story ≠ franchise",
    "price_above_value": "price above estimated value band",
    "margin_of_safety_ok": "margin of safety within band",
    "owner_earnings_weak": "owner earnings quality weak",
    "circle_of_competence": "outside circle of competence — research only",
    "patience_valid": "patience is the position — no forced trade",
    "quality_priced_in": "quality name, edge likely priced in",
}

PARTS: List[Dict[str, str]] = [
    {"part": "1", "title": "Origins", "focus": "Graham discipline — price vs value"},
    {"part": "2", "title": "Buffett evolution", "focus": "Quality at fair price"},
    {"part": "3", "title": "Munger mental models", "focus": "Checklists, inversion"},
    {"part": "4", "title": "Moat & franchise", "focus": "Durability of returns"},
    {"part": "5", "title": "Capital allocation", "focus": "Mgmt reinvestment skill"},
    {
        "part": "6",
        "title": "Accounting reality",
        "focus": "Owner earnings, not EPS theater",
    },
    {
        "part": "7",
        "title": "Market psychology",
        "focus": "Fear/greed — wait for mispricing",
    },
    {"part": "8", "title": "Concentration", "focus": "Few high-conviction names"},
    {"part": "9", "title": "Patience & cash", "focus": "No action is action"},
    {"part": "10", "title": "Institutional practice", "focus": "Process > prediction"},
]


def evaluate_value_posture(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Heuristic value posture from existing row fields — not a full DCF engine."""
    score = float(row.get("score") or row.get("validated_score") or 0)
    thesis = float(row.get("thesis_conf") or row.get("thesis_quality") or 0)
    pe = row.get("pe") or row.get("valuation_pe")
    extended = bool((row.get("structure") or {}).get("is_extended"))
    tb = (tradeability or "").upper()

    labels: List[str] = []
    margin_ok = thesis >= 0.65 and score >= 7.0 and not extended
    if margin_ok:
        labels.append(BAMANG_LABELS["margin_of_safety_ok"])
    elif extended:
        labels.append(BAMANG_LABELS["price_above_value"])
    if thesis < 0.5:
        labels.append(BAMANG_LABELS["moat_unclear"])
    if pe and float(pe) > 45:
        labels.append(BAMANG_LABELS["quality_priced_in"])
    if tb in ("WAIT", "NO_TRADE"):
        labels.append(BAMANG_LABELS["patience_valid"])

    action_hint = "WATCH"
    if margin_ok and tb in ("TRADE", "SELECTIVE", "STRONG_TRADE"):
        action_hint = "PILOT"
    elif not margin_ok:
        action_hint = "RESEARCH"

    return {
        "mode": "bamang_value",
        "parts_framework": PARTS,
        "labels": labels,
        "margin_of_safety_ok": margin_ok,
        "action_hint": action_hint,
        "headline": labels[0] if labels else BAMANG_LABELS["circle_of_competence"],
        "authority": "research_only",
        "model_note": "Heuristic from thesis/score/extension — not audited fundamentals",
    }


def tags_for_playbook_row(
    row: Dict[str, Any], *, tradeability: str = ""
) -> Dict[str, Any]:
    v = evaluate_value_posture(row, tradeability=tradeability)
    return {
        "value_tag": v["headline"],
        "value_action_hint": v["action_hint"],
        "bamang_labels": v["labels"],
    }
