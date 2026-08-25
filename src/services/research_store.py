"""Unified research persistence — drafts, runs, shadow, memory, reports."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STORE = Path("data") / "artifacts" / "research_pipeline.json"
_LOG = Path("data") / "artifacts" / "research_audit.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _empty() -> Dict[str, Any]:
    return {
        "strategy_drafts": [],
        "backtest_runs": [],
        "shadow_runs": [],
        "memory": [],
        "reports": [],
        "updated_at": _now(),
    }


def _load() -> Dict[str, Any]:
    if not _STORE.exists():
        return _empty()
    try:
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in ("strategy_drafts", "backtest_runs", "shadow_runs", "memory", "reports"):
                if not isinstance(data.get(key), list):
                    data[key] = []
            return data
    except Exception as exc:
        logger.warning("research store load failed: %s", exc)
    return _empty()


def _save(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_research_event(entry: Dict[str, Any]) -> Dict[str, Any]:
    row = {"id": str(uuid.uuid4())[:12], "timestamp": _now(), **entry}
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def save_strategy_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**draft, "id": draft.get("id") or str(uuid.uuid4())[:12], "createdAt": _now()}
    data.setdefault("strategy_drafts", []).append(entry)
    _save(data)
    log_research_event({"type": "strategy_draft", "draft_id": entry["id"]})
    return entry


def list_strategy_drafts(*, limit: int = 50) -> List[Dict[str, Any]]:
    rows = sorted(_load().get("strategy_drafts") or [], key=lambda r: r.get("createdAt", ""), reverse=True)
    return rows[:limit]


def get_strategy_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    for row in _load().get("strategy_drafts") or []:
        if str(row.get("id")) == draft_id:
            return row
    return None


def save_backtest_run(run: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**run, "id": run.get("id") or str(uuid.uuid4())[:12], "createdAt": _now()}
    data.setdefault("backtest_runs", []).append(entry)
    if len(data["backtest_runs"]) > 200:
        data["backtest_runs"] = data["backtest_runs"][-200:]
    _save(data)
    log_research_event({"type": "backtest_run", "run_id": entry["id"]})
    return entry


def list_backtest_runs(*, limit: int = 50) -> List[Dict[str, Any]]:
    rows = sorted(_load().get("backtest_runs") or [], key=lambda r: r.get("createdAt", ""), reverse=True)
    return rows[:limit]


def save_shadow_run(run: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**run, "id": run.get("id") or str(uuid.uuid4())[:12], "createdAt": _now()}
    data.setdefault("shadow_runs", []).append(entry)
    if len(data["shadow_runs"]) > 100:
        data["shadow_runs"] = data["shadow_runs"][-100:]
    _save(data)
    log_research_event({"type": "shadow_run", "run_id": entry["id"]})
    return entry


def list_shadow_runs(*, limit: int = 30) -> List[Dict[str, Any]]:
    rows = sorted(_load().get("shadow_runs") or [], key=lambda r: r.get("createdAt", ""), reverse=True)
    return rows[:limit]


def save_memory_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**item, "id": item.get("id") or str(uuid.uuid4())[:12], "timestamp": _now()}
    data.setdefault("memory", []).append(entry)
    if len(data["memory"]) > 500:
        data["memory"] = data["memory"][-500:]
    _save(data)
    return entry


def list_memory(*, limit: int = 100, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _load().get("memory") or []
    if item_type:
        rows = [r for r in rows if str(r.get("type") or "") == item_type]
    rows = sorted(rows, key=lambda r: r.get("timestamp", ""), reverse=True)
    return rows[:limit]


def save_report(report: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**report, "id": report.get("id") or str(uuid.uuid4())[:12], "createdAt": _now()}
    data.setdefault("reports", []).append(entry)
    if len(data["reports"]) > 200:
        data["reports"] = data["reports"][-200:]
    _save(data)
    log_research_event({"type": "report", "report_id": entry["id"]})
    return entry


def list_reports(*, limit: int = 50) -> List[Dict[str, Any]]:
    rows = sorted(_load().get("reports") or [], key=lambda r: r.get("createdAt", ""), reverse=True)
    return rows[:limit]


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    for row in _load().get("reports") or []:
        if str(row.get("id")) == report_id:
            return row
    return None
