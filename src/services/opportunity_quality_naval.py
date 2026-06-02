"""
《纳瓦尔宝典》opportunity quality — durability, asymmetry, bandwidth worthiness.

Distinct from generic opportunity scanners — Naval lens on what deserves focus.
"""

from __future__ import annotations

from typing import Any, Dict

QUALITY_LABELS: Dict[str, str] = {
    "durable": "durable setup — thesis + structure align",
    "fragile": "fragile — timing-dependent, size down",
    "asymmetric": "asymmetric payoff — R:R earns study",
    "symmetric": "symmetric — edge must come from process",
    "bandwidth_yes": "worth mental bandwidth today",
    "bandwidth_no": "not worth bandwidth — defer",
}


def evaluate_opportunity_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    thesis = float(row.get("thesis_conf") or 0)
    timing = float(row.get("timing_conf") or 0)
    rr = float(row.get("risk_reward") or 0)
    struct = row.get("structure") or {}
    extended = bool(struct.get("is_extended"))

    durability = "durable" if thesis >= 0.6 and not extended else "fragile"
    asymmetry = "asymmetric" if rr >= 2.5 else "symmetric"
    bandwidth = (
        "bandwidth_yes"
        if thesis >= 0.55 and (rr >= 2.0 or timing >= 0.55)
        else "bandwidth_no"
    )

    return {
        "durability": durability,
        "durability_label": QUALITY_LABELS[durability],
        "asymmetry": asymmetry,
        "asymmetry_label": QUALITY_LABELS[asymmetry],
        "mental_bandwidth_worthy": bandwidth == "bandwidth_yes",
        "bandwidth_label": QUALITY_LABELS[bandwidth],
    }


def tags_for_playbook_row(row: Dict[str, Any], **_kwargs: Any) -> Dict[str, Any]:
    q = evaluate_opportunity_quality(row)
    return {
        "mental_bandwidth_worthy": q["mental_bandwidth_worthy"],
        "naval_durability": q["durability"],
        "naval_asymmetry": q["asymmetry"],
        "naval_bandwidth_label": q["bandwidth_label"],
    }
