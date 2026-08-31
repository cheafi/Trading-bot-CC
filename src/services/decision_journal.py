"""IDOS Decision Journal — pre-outcome decision records (research_only).

Flow: Decision → Outcome → Learning (never Outcome → Explanation).
Append-only JSONL at data/decision_journal.jsonl.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "decision_journal.jsonl"

_REQUIRED_FIELDS = frozenset(
    {
        "decision",
        "thesis",
        "alternatives_considered",
        "rejected_alternative",
        "expected_probability",
        "expected_downside",
        "expected_upside",
        "why_now",
        "what_changes_mind",
    }
)

_EDITABLE_ON_CREATE = _REQUIRED_FIELDS | frozenset(
    {"ticker", "decision_id", "notes", "source"}
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _review_dates(from_day: Optional[date] = None) -> Dict[str, str]:
    base = from_day or datetime.now(timezone.utc).date()
    return {
        "30d": (base + timedelta(days=30)).isoformat(),
        "90d": (base + timedelta(days=90)).isoformat(),
        "180d": (base + timedelta(days=180)).isoformat(),
    }


def _load_all() -> List[Dict[str, Any]]:
    if not _DATA_PATH.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in _DATA_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError as exc:
        logger.debug("decision journal read failed: %s", exc)
    return rows


def _append(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DATA_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("decision journal write failed: %s", exc)
        raise
    return entry


def _normalize_decision(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    if not value:
        raise ValueError("decision is required")
    return value


def _entry_by_decision_id(decision_id: str) -> Optional[Dict[str, Any]]:
    key = str(decision_id or "").strip()
    if not key:
        return None
    for row in reversed(_load_all()):
        if str(row.get("decision_id") or "").strip() == key:
            return row
    return None


def build_entry(payload: Dict[str, Any], *, stub: bool = False) -> Dict[str, Any]:
    """Validate and normalize a journal entry before persist."""
    clean = {k: v for k, v in (payload or {}).items() if v is not None}
    missing = [f for f in _REQUIRED_FIELDS if not clean.get(f) and clean.get(f) != 0]
    if missing and not stub:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")

    now = _utc_now_iso()
    today = now[:10]
    decision = _normalize_decision(clean.get("decision"))

    alts = clean.get("alternatives_considered")
    if alts is None:
        alts = []
    if isinstance(alts, str):
        alts = [alts]
    if not isinstance(alts, list):
        alts = [str(alts)]

    return {
        "entry_id": clean.get("entry_id") or f"DJ-{uuid.uuid4().hex[:8].upper()}",
        "decision": decision,
        "date": str(clean.get("date") or today),
        "recorded_at": now,
        "ticker": str(clean.get("ticker") or "").upper() or None,
        "decision_id": str(clean.get("decision_id") or "").strip() or None,
        "thesis": str(clean.get("thesis") or ""),
        "alternatives_considered": [str(a) for a in alts if str(a).strip()],
        "rejected_alternative": str(clean.get("rejected_alternative") or ""),
        "expected_probability": clean.get("expected_probability"),
        "expected_downside": str(clean.get("expected_downside") or ""),
        "expected_upside": str(clean.get("expected_upside") or ""),
        "why_now": str(clean.get("why_now") or ""),
        "what_changes_mind": str(clean.get("what_changes_mind") or ""),
        "review_dates": clean.get("review_dates") or _review_dates(),
        "outcome": clean.get("outcome"),
        "learning": clean.get("learning"),
        "authority": "research_only",
        "may_authorize_deploy": False,
        "source": str(clean.get("source") or ("stub" if stub else "manual")),
        "stub": bool(stub),
        "four_questions": clean.get("four_questions")
        or {
            "know": str(clean.get("thesis") or "")[:240],
            "believe": str(clean.get("why_now") or "")[:240],
            "doubt": str(clean.get("what_changes_mind") or "")[:240],
            "act": decision,
        },
    }


def append_entry(payload: Dict[str, Any], *, stub: bool = False) -> Dict[str, Any]:
    entry = build_entry(payload, stub=stub)
    return _append(entry)


def load_recent(limit: int = 20) -> List[Dict[str, Any]]:
    rows = _load_all()
    return list(reversed(rows[-limit:]))


def maybe_stub_from_decision_id(
    *,
    decision_id: str,
    ticker: str = "",
    decision: str = "PENDING_JOURNAL",
    source: str = "belief_review_hook",
) -> Optional[Dict[str, Any]]:
    """Create minimal stub when decision_id exists but no journal row yet."""
    key = str(decision_id or "").strip()
    if not key or _entry_by_decision_id(key):
        return None
    return append_entry(
        {
            "decision": decision,
            "decision_id": key,
            "ticker": ticker,
            "thesis": "Stub — complete thesis before deploy or explicit wait.",
            "alternatives_considered": ["cash", "monitor_only"],
            "rejected_alternative": "Incomplete — journal stub only.",
            "expected_probability": None,
            "expected_downside": "TBD",
            "expected_upside": "TBD",
            "why_now": "Auto-stub from decision_id link; replace before capital action.",
            "what_changes_mind": "Complete Decision Journal entry.",
            "source": source,
        },
        stub=True,
    )


def record_deploy_intent_stub(
    *,
    ticker: str,
    decision_id: Optional[str] = None,
    thesis: str = "",
) -> Optional[Dict[str, Any]]:
    """Hook: deploy intent with decision_id → stub journal row if missing."""
    key = str(decision_id or "").strip()
    if not key:
        return None
    if _entry_by_decision_id(key):
        return None
    return maybe_stub_from_decision_id(
        decision_id=key,
        ticker=ticker,
        decision="DEPLOY_INTENT",
        source="deploy_intent_hook",
    )


def summary(limit: int = 20) -> Dict[str, Any]:
    rows = _load_all()
    recent = list(reversed(rows[-limit:]))
    stubs = sum(1 for row in recent if row.get("stub"))
    return {
        "status": "phase1" if recent else "empty",
        "authority": "research_only",
        "headline": "Decision Journal · 決策日誌 — pre-outcome records (research only)",
        "total_loaded": len(rows),
        "recent_count": len(recent),
        "stub_count_recent": stubs,
        "entries": recent,
        "schema_fields": sorted(_REQUIRED_FIELDS | {"date", "review_dates", "outcome", "learning"}),
        "generated_at": _utc_now_iso(),
    }


def deploy_intent_journal_status(
    *,
    decision_id: str = "",
    ticker: str = "",
) -> Dict[str, Any]:
    """
    Phase 2 — deploy-intent path journal checklist (display only, non-blocking).

    Returns missing required fields when entry is absent or still a stub.
    Human deploy only; never grants deploy authority.
    """
    key = str(decision_id or "").strip()
    sym = str(ticker or "").upper().strip()
    entry = _entry_by_decision_id(key) if key else None
    missing: List[str] = []
    if not entry:
        missing = sorted(_REQUIRED_FIELDS)
        status = "missing"
    elif entry.get("stub"):
        missing = [
            f
            for f in _REQUIRED_FIELDS
            if not str(entry.get(f) or "").strip() and entry.get(f) != 0
        ]
        status = "stub"
    else:
        status = "complete"

    readiness_hint = (
        f"/api/v7/decision-readiness/checklist?ticker={sym}" if sym else None
    )
    return {
        "status": status,
        "authority": "research_only",
        "may_authorize_deploy": False,
        "decision_id": key or None,
        "ticker": sym or entry.get("ticker") if entry else sym or None,
        "entry_id": entry.get("entry_id") if entry else None,
        "stub": bool(entry.get("stub")) if entry else False,
        "complete": status == "complete",
        "missing_fields": missing,
        "required_fields": sorted(_REQUIRED_FIELDS),
        "journal_post_path": "/api/v7/decision-journal/entry",
        "readiness_path": readiness_hint,
        "headline": (
            "Journal complete — human deploy confirm still required"
            if status == "complete"
            else "Journal incomplete — complete pre-outcome record before deploy intent"
        ),
        "checklist_note": (
            "Link pre-decision checklist + journal POST — research_only; no auto-deploy."
        ),
        "generated_at": _utc_now_iso(),
    }
