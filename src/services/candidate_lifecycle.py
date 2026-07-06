"""
Candidate lifecycle — primary bucket assignment and no-edge resolution.

Thin layer over playbook_truth for tests and legacy callers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.cc_display_constants import CC_TOP_MONITOR_COUNT
from src.services.playbook_truth import (
    assign_primary_bucket,
    bucket_rows,
    enforce_single_primary_bucket as _enforce_single_primary_bucket,
    is_no_edge_mode,
)

BUCKET_DEPLOY = "Deploy"
BUCKET_PILOT = "Pilot"
BUCKET_WATCH = "Watch"
BUCKET_NEAR_MISS = "Near-miss"
BUCKET_REJECTED = "Rejected"
BUCKET_ARCHIVED = "Archived"


def bucket_candidate(
    row: Dict[str, Any],
    *,
    deploy_authority: bool = False,
    near_miss: bool = False,
    regime_state: str = "WAIT",
) -> str:
    if row.get("archived"):
        return BUCKET_ARCHIVED
    return assign_primary_bucket(
        row,
        deploy_authority=deploy_authority,
        near_miss=near_miss,
        regime_state=regime_state,
    )


def enforce_single_primary_bucket(
    buckets: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """One ticker — one primary bucket (delegates to playbook_truth)."""
    return _enforce_single_primary_bucket(buckets)


def enforce_bucket_exclusivity(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    near_miss_tickers: Optional[set[str]] = None,
    regime_state: str = "WAIT",
) -> Dict[str, List[Dict[str, Any]]]:
    return bucket_rows(
        rows,
        deploy_authority=deploy_authority,
        near_miss_tickers=near_miss_tickers,
        regime_state=regime_state,
    )


def filter_rejected_from_top_slots(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    limit: int = CC_TOP_MONITOR_COUNT,
) -> List[Dict[str, Any]]:
    buckets = bucket_rows(rows, deploy_authority=deploy_authority)
    out: List[Dict[str, Any]] = []
    for bucket in (BUCKET_DEPLOY, BUCKET_PILOT, BUCKET_WATCH, BUCKET_NEAR_MISS):
        for row in buckets.get(bucket) or []:
            out.append(row)
            if len(out) >= limit:
                return out
    return out


def resolve_no_edge_state(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
) -> Dict[str, Any]:
    buckets = bucket_rows(rows, deploy_authority=deploy_authority)
    counts = {k: len(buckets.get(k) or []) for k in buckets}
    no_edge = is_no_edge_mode(counts)
    return {
        "no_edge": no_edge,
        "counts": counts,
        "best_action": "do nothing — preserve capital" if no_edge else "review Playbook buckets",
    }
