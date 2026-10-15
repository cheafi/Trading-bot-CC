"""13F quarter-over-quarter sponsor set diffs (read-only SEC search proxy)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.services.research_safety import sanitize_research_payload


def _quarter_key(file_date: str) -> Optional[str]:
    raw = str(file_date or "").strip()[:10]
    if len(raw) < 7:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}Q{q}"


def qoq_sponsor_diffs(matched_sponsors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare known-manager sponsor sets between latest quarter and prior quarter.
    Uses filing_date on matched rows — not share-count deltas from XML holdings.
    """
    by_q: Dict[str, Set[str]] = defaultdict(set)
    meta: Dict[str, Dict[str, Any]] = {}
    for row in matched_sponsors or []:
        if not isinstance(row, dict):
            continue
        cik = str(row.get("cik") or row.get("name") or "")
        if not cik:
            continue
        qk = _quarter_key(str(row.get("filing_date") or ""))
        if not qk:
            continue
        by_q[qk].add(cik)
        meta[cik] = {
            "name": row.get("name"),
            "tier": row.get("tier"),
            "filing_date": row.get("filing_date"),
        }
    quarters = sorted(by_q.keys())
    if len(quarters) < 2:
        return sanitize_research_payload(
            {
                "ok": False,
                "reason": "insufficient_quarters",
                "quarters_seen": quarters,
                "note": "Need filings in two quarters for QoQ diff.",
                "authority": "research_only",
            }
        )
    current_q, prior_q = quarters[-1], quarters[-2]
    cur, prev = by_q[current_q], by_q[prior_q]
    added = sorted(cur - prev)
    removed = sorted(prev - cur)
    stable = sorted(cur & prev)

    def _rows(ciks: List[str]) -> List[Dict[str, Any]]:
        out = []
        for c in ciks:
            m = meta.get(c) or {}
            out.append({"cik": c, "name": m.get("name"), "tier": m.get("tier")})
        return out

    return sanitize_research_payload(
        {
            "ok": True,
            "current_quarter": current_q,
            "prior_quarter": prior_q,
            "added_managers": _rows(added),
            "removed_managers": _rows(removed),
            "stable_managers": _rows(stable),
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "stable": len(stable),
            },
            "note": "Manager appearance QoQ — not position size or shares held.",
            "authority": "research_only",
        }
    )
