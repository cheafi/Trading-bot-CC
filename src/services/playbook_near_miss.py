"""Playbook near-miss / monitor queue — honest labels, no deploy authority."""

from __future__ import annotations

from typing import Any, Dict, List

PLAYBOOK_NEAR_MISS_LIMIT = 16
DISCOVERY_NEAR_MISS_STRIP_LIMIT = 12

_WATCH_ACTIONS = frozenset(
    {"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"}
)
_DEPLOY_ACTIONS = frozenset(
    {"TRADE", "PILOT", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"}
)
_AVOID_ACTIONS = frozenset(
    {"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "AVOID_NOW"}
)

_DEFAULT_MISSING = (
    "stronger timing, confirmed volume follow-through, "
    "monitor-pipeline support, and execution-ready status"
)
_DEFAULT_HORIZON = "next 1–3 sessions if conditions improve"


def build_playbook_near_miss_rows(
    opps: List[Dict[str, Any]],
    *,
    limit: int = PLAYBOOK_NEAR_MISS_LIMIT,
) -> List[Dict[str, Any]]:
    """
    Build monitor / near-miss rows from ranked opportunities.

    Includes WATCH names and high-scoring AVOID rows that are near deploy gates.
    Never marks rows execution-ready or deploy-qualified.
    """
    deploy_tickers = {
        str(o.get("ticker") or "").upper() for o in opps if o.get("execution_ready")
    }
    candidates: List[Dict[str, Any]] = []
    for row in opps or []:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or ticker in deploy_tickers:
            continue
        act = str(row.get("action") or "").upper()
        if act in _DEPLOY_ACTIONS or row.get("execution_ready"):
            continue

        score = float(row.get("score") or row.get("final_conf") or 0)
        timing = float(row.get("timing_conf") or 0)
        thesis = float(row.get("thesis_conf") or 0)
        net = float(row.get("net_edge_score") or score)

        is_watch = act in _WATCH_ACTIONS
        is_near_avoid = act in _AVOID_ACTIONS and (
            (score >= 4.3 or net >= 3.8) and (timing >= 0.48 or thesis >= 0.38)
        )
        if not is_watch and not is_near_avoid:
            continue
        min_watch_score = (
            5.2 if str(row.get("asset_class") or "") in ("etf", "index") else 5.3
        )
        if is_watch and score < min_watch_score:
            continue

        nm = dict(row)
        nm["action"] = "WATCH"
        nm["execution_ready"] = False
        nm.setdefault("monitor_state", "near_miss")
        nm.setdefault("surface_authority", "monitor_only")
        if is_near_avoid:
            nm["near_miss_label"] = "near_miss"
            nm.setdefault(
                "whats_missing",
                "Blocked by deploy gates — monitor for upgrade (not deploy-ready)",
            )
        else:
            nm["near_miss_label"] = "watch"
        if not nm.get("whats_missing") and not nm.get("gaps"):
            nm["whats_missing"] = _DEFAULT_MISSING
        if not nm.get("timing_bucket"):
            nm["timing_bucket"] = _DEFAULT_HORIZON
        candidates.append(nm)

    def _sort_key(r: Dict[str, Any]) -> tuple:
        gaps = len(r.get("gaps") or [])
        timing = float(r.get("timing_conf") or 0)
        net = float(r.get("net_edge_score") or r.get("score") or 0)
        return (gaps, -timing, -net)

    candidates.sort(key=_sort_key)
    return candidates[:limit]


def build_discovery_near_miss_strip(
    merged_top_names: List[Dict[str, Any]],
    *,
    limit: int = DISCOVERY_NEAR_MISS_STRIP_LIMIT,
) -> List[Dict[str, Any]]:
    """Discovery-tab monitor strip from merged scanner names (research only)."""
    strip: List[Dict[str, Any]] = []
    for row in merged_top_names or []:
        act = str(row.get("action") or "").upper()
        if act == "TRADE" or row.get("is_warning"):
            continue
        if act == "AVOID" and float(row.get("max_score") or 0) < 6.0:
            continue
        item = {
            **row,
            "monitor_label": "near_miss"
            if row.get("status") == "speculative"
            else "watch",
            "research_only": True,
            "surface_authority": "monitor_only",
        }
        strip.append(item)
        if len(strip) >= limit:
            break
    return strip
