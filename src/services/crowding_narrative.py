"""
Crowding / narrative heat — bubble skepticism heuristic stub.

First-class discount for extension, sector cluster, and consensus-rich setups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def compute_crowding_score(
    *,
    rsi: Optional[float] = None,
    extended: bool = False,
    sector_overlap_pct: float = 0.0,
    narrative_bullet_count: int = 0,
    confluence_score: int = 0,
    leader_status: Optional[str] = None,
    vol_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Heuristic crowding / narrative heat (low / medium / high).

    Not a precision bubble detector — explicit flags for operator discount.
    """
    flags: List[str] = []
    points = 0

    if rsi is not None and rsi >= 72:
        flags.append("rsi_extended")
        points += 2
    elif rsi is not None and rsi >= 65:
        flags.append("rsi_elevated")
        points += 1

    if extended:
        flags.append("price_extended")
        points += 2

    if sector_overlap_pct > 30:
        flags.append("sector_cluster_in_book")
        points += 2
    elif sector_overlap_pct > 15:
        flags.append("sector_overlap")
        points += 1

    if narrative_bullet_count >= 4 and confluence_score < 65:
        flags.append("narrative_rich_evidence_light")
        points += 2

    if (leader_status or "").upper() == "LEADER" and extended:
        flags.append("crowded_leader_extension")
        points += 1

    if vol_ratio is not None and vol_ratio > 2.0 and extended:
        flags.append("blow_off_volume")
        points += 1

    if points >= 4:
        level = "high"
    elif points >= 2:
        level = "medium"
    else:
        level = "low"

    summary = (
        "Crowding elevated — " + ", ".join(flags)
        if flags
        else "No strong crowding flags from available proxies."
    )

    return {
        "level": level,
        "score": points,
        "flags": flags,
        "summary": summary,
        "discount_guidance": (
            "Apply extra skepticism — consensus and extension may be priced in."
            if level == "high"
            else (
                "Monitor narrative heat — partial discount warranted."
                if level == "medium"
                else "Standard process — crowding not dominant."
            )
        ),
        "model_note": "Heuristic stub — not a quant crowding model.",
    }


def crowding_from_playbook_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Infer crowding from ranked playbook row fields."""
    struct = row.get("structure") or {}
    earn = row.get("earnings") or {}
    extended = bool(
        struct.get("is_extended")
        or row.get("extended")
        or row.get("timing_extended")
    )
    rsi = struct.get("rsi") or row.get("rsi")
    vol = row.get("vol_ratio")
    if vol is None and isinstance(row.get("fundamentals"), dict):
        vol = row["fundamentals"].get("vol_ratio")
    pg = row.get("portfolio_gate") or {}
    overlap = float(pg.get("sector_overlap_pct") or row.get("sector_overlap_pct") or 0)

    result = compute_crowding_score(
        rsi=float(rsi) if rsi is not None else None,
        extended=extended,
        sector_overlap_pct=overlap,
        narrative_bullet_count=len(row.get("why_now") or []) if isinstance(row.get("why_now"), list) else 0,
        confluence_score=int(row.get("trigger_quality") or 0),
        leader_status=row.get("leader"),
        vol_ratio=float(vol) if vol is not None else None,
    )
    return result


def attach_crowding_to_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Add crowding_narrative fields to opportunity row."""
    crowding = crowding_from_playbook_row(row)
    row = {**row, "crowding_narrative": crowding}
    if crowding["level"] == "high":
        row["passive_replacement_risk"] = "high"
    elif crowding["level"] == "medium":
        row["passive_replacement_risk"] = "medium"
    else:
        row["passive_replacement_risk"] = "low"
    return row
