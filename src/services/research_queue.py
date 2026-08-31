"""Research queue — CIIO allocates research time like capital (not watchlist/scanner)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "research_queue.json"

DEFAULT_CATEGORY_BUDGETS: Dict[str, int] = {
    "Research": 60,
    "Portfolio": 30,
    "Belief": 20,
    "Counterargument": 15,
    "Review": 15,
}

_MAX_ITEMS = 12
_VALID_CATEGORIES = frozenset(DEFAULT_CATEGORY_BUDGETS.keys())


def _load_store() -> Dict[str, Any]:
    if not _DATA_PATH.is_file():
        return {"items": []}
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("research queue store read failed: %s", exc)
        return {"items": []}
    if not isinstance(data, dict):
        return {"items": []}
    if not isinstance(data.get("items"), list):
        data["items"] = []
    return data


def _save_store(store: Dict[str, Any]) -> None:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DATA_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("research queue store write failed: %s", exc)
        raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def list_queue() -> Dict[str, Any]:
    store = _load_store()
    items = [_normalize_item(it) for it in (store.get("items") or []) if isinstance(it, dict)]
    total_budget = sum(int(it.get("budget_minutes") or 0) for it in items)
    return {
        "items": items,
        "category_budgets": dict(DEFAULT_CATEGORY_BUDGETS),
        "total_budget_minutes": total_budget,
        "max_items": _MAX_ITEMS,
        "authority": "research_only",
        "headline": "Research Queue · 研究隊列 — CIIO time allocation (not watchlist)",
    }


def add_item(ticker: str, *, budget_minutes: int = 30, category: str = "Research") -> Dict[str, Any]:
    """Add ticker to queue with time budget."""
    key = str(ticker or "").strip().upper()
    if not key:
        raise ValueError("ticker required")
    cat = str(category or "Research").strip()
    if cat not in _VALID_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(sorted(_VALID_CATEGORIES))}")
    try:
        budget = int(budget_minutes)
    except (TypeError, ValueError) as exc:
        raise ValueError("budget_minutes must be an integer") from exc
    if budget < 5 or budget > 180:
        raise ValueError("budget_minutes must be between 5 and 180")

    store = _load_store()
    items: List[Dict[str, Any]] = [
        it for it in (store.get("items") or []) if isinstance(it, dict)
    ]
    items = [it for it in items if str(it.get("ticker") or "").upper() != key]
    items.insert(
        0,
        {
            "ticker": key,
            "budget_minutes": budget,
            "category": cat,
            "added_at": _now_iso(),
            "status": "queued",
        },
    )
    store["items"] = items[:_MAX_ITEMS]
    _save_store(store)
    _log_workflow_event(key, "research_queue_add", category=cat, budget_minutes=budget)
    return list_queue()


def remove_item(ticker: str) -> Dict[str, Any]:
    key = str(ticker or "").strip().upper()
    if not key:
        raise ValueError("ticker required")
    store = _load_store()
    before = len(store.get("items") or [])
    store["items"] = [
        it
        for it in (store.get("items") or [])
        if isinstance(it, dict) and str(it.get("ticker") or "").upper() != key
    ]
    if len(store["items"]) == before:
        raise ValueError(f"ticker not in queue: {key}")
    _save_store(store)
    _log_workflow_event(key, "research_queue_remove")
    return list_queue()


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    cat = str(raw.get("category") or "Research")
    if cat not in _VALID_CATEGORIES:
        cat = "Research"
    return {
        "ticker": str(raw.get("ticker") or "").upper(),
        "budget_minutes": int(raw.get("budget_minutes") or DEFAULT_CATEGORY_BUDGETS[cat]),
        "category": cat,
        "added_at": raw.get("added_at"),
        "status": str(raw.get("status") or "queued"),
        "authority": "research_only",
    }


def _log_workflow_event(ticker: str, event: str, **meta: Any) -> None:
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
