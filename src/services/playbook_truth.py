"""
Playbook truth — mutually exclusive buckets, qualification copy, no-edge mode.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_AVOID = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE", "BLOCKED"})
_TRADE = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"})
_PILOT = frozenset({"PILOT"})
_WATCH = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER"})

_BUCKET_ORDER = ("Deploy", "Pilot", "Watch", "Near-miss", "Rejected")

_TAG_BUCKETS = frozenset({"fastest_improving", "sector_leader", "best_rr"})


def assign_primary_bucket(
    row: Dict[str, Any],
    *,
    deploy_authority: bool = False,
    near_miss: bool = False,
) -> str:
    """One primary bucket per candidate — Deploy|Pilot|Watch|Near-miss|Rejected."""
    act = str(row.get("effective_action") or row.get("action") or "WATCH").upper()
    if act in _AVOID:
        return "Rejected"
    if deploy_authority and bool(row.get("execution_ready")) and act in _TRADE:
        return "Deploy"
    if act in _PILOT:
        return "Pilot"
    if near_miss or bool(row.get("near_miss")) or bool(row.get("whats_missing")):
        return "Near-miss"
    if act in _WATCH or act in _TRADE:
        return "Watch"
    try:
        score = float(row.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    if score >= 6.0:
        return "Near-miss"
    return "Rejected"


def bucket_rows(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    near_miss_tickers: Optional[set[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Partition rows into mutually exclusive primary buckets."""
    nm = {str(t).upper() for t in (near_miss_tickers or set())}
    out: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _BUCKET_ORDER}
    for row in rows or []:
        ticker = str(row.get("ticker") or "").upper()
        bucket = assign_primary_bucket(
            row,
            deploy_authority=deploy_authority,
            near_miss=ticker in nm,
        )
        tagged = {**row, "primary_bucket": bucket}
        out[bucket].append(tagged)
    return out


def bucket_counts(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    near_miss_tickers: Optional[set[str]] = None,
) -> Dict[str, int]:
    buckets = bucket_rows(
        rows,
        deploy_authority=deploy_authority,
        near_miss_tickers=near_miss_tickers,
    )
    return {k: len(buckets.get(k) or []) for k in _BUCKET_ORDER}


def is_no_edge_mode(counts: Dict[str, int]) -> bool:
    """True when only rejected names remain — hide upgrade/monitor panels."""
    deploy = int(counts.get("Deploy") or 0)
    pilot = int(counts.get("Pilot") or 0)
    watch = int(counts.get("Watch") or 0)
    near = int(counts.get("Near-miss") or 0)
    rejected = int(counts.get("Rejected") or 0)
    actionable = deploy + pilot + watch + near
    return actionable == 0 and rejected > 0


def no_edge_copy(counts: Dict[str, int]) -> str:
    """Canonical no-edge hero line."""
    return (
        "NO EDGE TODAY · "
        f"{int(counts.get('Deploy') or 0)} Deploy · "
        f"{int(counts.get('Pilot') or 0)} Pilot · "
        f"{int(counts.get('Watch') or 0)} Watch · "
        f"{int(counts.get('Near-miss') or 0)} Near-miss · "
        "Rejected hidden · Best action: do nothing"
    )


def format_playbook_qualification_line(
    *,
    setup_qualified: int = 0,
    trade_qualified: int = 0,
    execution_qualified: int = 0,
    deploy_qualified: int = 0,
    deploy_authority: bool = False,
    regime_state: str = "WAIT",
) -> str:
    """Playbook strip — never 'Deploy gate open' when authority blocked."""
    parts: List[str] = []
    if setup_qualified:
        parts.append(f"{setup_qualified} setup-qualified")
    if trade_qualified and regime_state not in ("NO_TRADE",):
        parts.append(f"{trade_qualified} trade-qualified")
    if execution_qualified and execution_qualified != deploy_qualified:
        parts.append(f"{execution_qualified} execution-qualified")
    parts.append(f"{deploy_qualified} deploy-qualified")
    return " · ".join(parts)


def playbook_qualification_for_truth(
    qualification_levels: Optional[Dict[str, Any]],
    *,
    deploy_authority: bool,
    regime_state: str,
) -> str:
    lv = qualification_levels or {}
    return format_playbook_qualification_line(
        setup_qualified=int(lv.get("setup_qualified") or 0),
        trade_qualified=int(lv.get("trade_qualified") or 0),
        execution_qualified=int(lv.get("execution_qualified") or 0),
        deploy_qualified=int(lv.get("deploy_qualified") or 0),
        deploy_authority=deploy_authority,
        regime_state=regime_state,
    )
