"""Pre-decision readiness checklist — research_only, no deploy authority."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "decision_readiness.json"

CHECKLIST_FIELDS: List[Dict[str, str]] = [
    {"id": "why_now", "label": "Why now?", "label_bilingual": "Why now? · 為何現在"},
    {"id": "why_not_later", "label": "Why not later?", "label_bilingual": "Why not later? · 為何不等等"},
    {"id": "why_not_cash", "label": "Why not cash?", "label_bilingual": "Why not cash? · 為何不持現"},
    {"id": "why_not_another_stock", "label": "Why not another stock?", "label_bilingual": "Why not another stock? · 為何不是另一隻"},
    {"id": "what_changes_mind", "label": "What changes my mind?", "label_bilingual": "What changes my mind? · 什麼會改變看法"},
    {"id": "what_would_invalidate", "label": "What would invalidate?", "label_bilingual": "What would invalidate? · 什麼會令論點失效"},
    {"id": "opportunity_cost", "label": "Opportunity cost?", "label_bilingual": "Opportunity cost? · 機會成本"},
]

_FIELD_IDS = frozenset(f["id"] for f in CHECKLIST_FIELDS)


def _load_store() -> Dict[str, Any]:
    if not _DATA_PATH.is_file():
        return {"checklists": {}}
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("decision readiness store read failed: %s", exc)
        return {"checklists": {}}
    if not isinstance(data, dict):
        return {"checklists": {}}
    data.setdefault("checklists", {})
    return data


def _save_store(store: Dict[str, Any]) -> None:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DATA_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("decision readiness store write failed: %s", exc)
        raise


def default_answers() -> Dict[str, str]:
    return {field_id: "" for field_id in _FIELD_IDS}


def checklist_schema() -> Dict[str, Any]:
    return {
        "fields": CHECKLIST_FIELDS,
        "workflow": "Mission → Question → Belief → Counterargument → Deploy",
        "authority": "research_only",
    }


def load_checklist(ticker: str) -> Dict[str, Any]:
    """Return persisted checklist for ticker (empty template if none)."""
    key = str(ticker or "").strip().upper()
    store = _load_store()
    saved = store.get("checklists") or {}
    answers = dict(default_answers())
    if isinstance(saved.get(key), dict):
        for field_id in _FIELD_IDS:
            val = saved[key].get(field_id)
            if val is not None:
                answers[field_id] = str(val)
    complete = checklist_complete(answers)
    return {
        "ticker": key,
        "answers": answers,
        "complete": complete,
        "filled_count": sum(1 for v in answers.values() if str(v).strip()),
        "required_count": len(_FIELD_IDS),
        "authority": "research_only",
    }


def save_checklist(ticker: str, answers: Dict[str, Any]) -> Dict[str, Any]:
    """Persist checklist answers — display only; never grants deploy."""
    key = str(ticker or "").strip().upper()
    if not key:
        raise ValueError("ticker required")
    clean = {
        field_id: str((answers or {}).get(field_id) or "").strip()
        for field_id in _FIELD_IDS
    }
    store = _load_store()
    checklists: Dict[str, Any] = store.setdefault("checklists", {})
    checklists[key] = clean
    _save_store(store)
    result = load_checklist(key)
    _log_workflow_event(key, "checklist_saved", complete=result["complete"])
    return result


def checklist_complete(answers: Dict[str, Any]) -> bool:
    return all(str((answers or {}).get(field_id) or "").strip() for field_id in _FIELD_IDS)


def _log_workflow_event(ticker: str, event: str, **meta: Any) -> None:
    """Optional audit hook into decision journal."""
    try:
        from src.engines.decision_journal import DecisionJournal

        journal = DecisionJournal()
        journal.record(
            ticker=ticker,
            decision="WORKFLOW",
            notes=[f"workflow:{event}", *(f"{k}={v}" for k, v in meta.items())],
            factors={"workflow_event": event, **meta},
        )
    except Exception as exc:
        logger.debug("workflow journal hook skipped: %s", exc)
