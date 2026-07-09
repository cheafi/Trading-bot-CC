"""
Opportunity Portfolio Builder — diversified research/watch/near-miss book.

Caps: research 20, watch 10, near-miss 5, with sector/theme concentration limits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

RESEARCH_CAP = 20
WATCH_CAP = 10
NEAR_MISS_CAP = 5
SECTOR_CAP = 4
THEME_CAP = 3


def _score_row(entry: Dict[str, Any]) -> float:
    ev = entry.get("evidence") or {}
    cal = entry.get("calibration") or {}
    composite = float(ev.get("composite_score") or 0)
    sample_penalty = 0.05 if cal.get("learning_mode") else 0.0
    cost_drag = float(cal.get("cost_drag_r") or 0)
    return composite - sample_penalty - min(0.3, cost_drag * 0.1)


def _sector_key(entry: Dict[str, Any]) -> str:
    cand = entry.get("candidate") or {}
    return str(cand.get("sector") or cand.get("theme") or "unknown").lower()


def _theme_key(entry: Dict[str, Any]) -> str:
    cand = entry.get("candidate") or {}
    return str(cand.get("theme") or cand.get("sector") or "unknown").lower()


def _pick_diversified(
    rows: List[Dict[str, Any]],
    *,
    limit: int,
    sector_cap: int = SECTOR_CAP,
    theme_cap: int = THEME_CAP,
) -> List[Dict[str, Any]]:
    ranked = sorted(rows, key=_score_row, reverse=True)
    picked: List[Dict[str, Any]] = []
    sector_counts: Dict[str, int] = {}
    theme_counts: Dict[str, int] = {}
    for entry in ranked:
        if len(picked) >= limit:
            break
        sk = _sector_key(entry)
        tk = _theme_key(entry)
        if sector_counts.get(sk, 0) >= sector_cap:
            continue
        if theme_counts.get(tk, 0) >= theme_cap:
            continue
        picked.append(entry)
        sector_counts[sk] = sector_counts.get(sk, 0) + 1
        theme_counts[tk] = theme_counts.get(tk, 0) + 1
    return picked


def build_opportunity_portfolio(
    scored_rows: List[Dict[str, Any]],
    *,
    truth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ = truth
    by_stage: Dict[str, List[Dict[str, Any]]] = {}
    for entry in scored_rows or []:
        stage = str((entry.get("candidate") or {}).get("stage") or "evidence_candidate")
        by_stage.setdefault(stage, []).append(entry)

    research = _pick_diversified(
        (by_stage.get("research_hit") or [])
        + (by_stage.get("evidence_candidate") or []),
        limit=RESEARCH_CAP,
    )
    watch = _pick_diversified(by_stage.get("watch_candidate") or [], limit=WATCH_CAP)
    near_miss = _pick_diversified(by_stage.get("near_miss") or [], limit=NEAR_MISS_CAP)
    playbook = _pick_diversified(by_stage.get("playbook_review") or [], limit=10)

    def _summarize(book: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for e in book:
            cand = e.get("candidate") or {}
            ev = e.get("evidence") or {}
            cal = e.get("calibration") or {}
            scr = e.get("screens") or {}
            out.append(
                {
                    "ticker": cand.get("ticker"),
                    "stage": cand.get("stage"),
                    "evidence_grade": ev.get("grade"),
                    "calibration_state": cal.get("state"),
                    "pattern_status": scr.get("pattern_status"),
                    "sector": cand.get("sector"),
                    "theme": cand.get("theme"),
                }
            )
        return out

    return {
        "research_book": _summarize(research),
        "watch_book": _summarize(watch),
        "near_miss_book": _summarize(near_miss),
        "playbook_book": _summarize(playbook),
        "caps": {
            "research": RESEARCH_CAP,
            "watch": WATCH_CAP,
            "near_miss": NEAR_MISS_CAP,
            "sector": SECTOR_CAP,
            "theme": THEME_CAP,
        },
        "counts": {
            "research": len(research),
            "watch": len(watch),
            "near_miss": len(near_miss),
            "playbook": len(playbook),
        },
        "diversification_note": "Sector/theme caps applied — not deploy allocation",
        "evidence_only": True,
        "may_authorize_deploy": False,
        "authority_effect": "none",
    }
