"""Editable research skills — reusable workflows (memory-backed, no deploy)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path("data") / "artifacts" / "research_skills.json"

_BUILTIN = [
    {
        "id": "vibe-session-default",
        "name": "Vibe research session",
        "task": "ask_question",
        "steps": ["parse_intent", "cross_market", "teams", "composite_backtest", "memory"],
        "editable": False,
    },
    {
        "id": "shadow-review-default",
        "name": "Shadow trade review",
        "task": "review_trades",
        "steps": ["parse_journal", "shadow_analyze", "export_audit"],
        "editable": False,
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _load() -> Dict[str, Any]:
    if not _STORE.exists():
        return {"skills": list(_BUILTIN), "updated_at": _now()}
    try:
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("skills"), list):
            data["skills"] = list(_BUILTIN)
        return data
    except Exception:
        return {"skills": list(_BUILTIN), "updated_at": _now()}


def _save(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_skills() -> List[Dict[str, Any]]:
    return list(_load().get("skills") or [])


def get_skill(skill_id: str) -> Optional[Dict[str, Any]]:
    for row in list_skills():
        if str(row.get("id")) == skill_id:
            return row
    return None


def upsert_skill(
    *,
    skill_id: Optional[str],
    name: str,
    task: str,
    steps: List[str],
    prompt_template: Optional[str] = None,
) -> Dict[str, Any]:
    data = _load()
    sid = skill_id or str(uuid.uuid4())[:12]
    entry = {
        "id": sid,
        "name": name[:200],
        "task": task[:64],
        "steps": [str(s)[:80] for s in steps[:20]],
        "prompt_template": (prompt_template or "")[:4000],
        "editable": True,
        "updatedAt": _now(),
    }
    skills = data.setdefault("skills", [])
    replaced = False
    for i, row in enumerate(skills):
        if str(row.get("id")) == sid and row.get("editable", True):
            skills[i] = {**row, **entry}
            replaced = True
            break
        if str(row.get("id")) == sid and not row.get("editable", True):
            raise ValueError("builtin_skill_readonly")
    if not replaced:
        skills.append(entry)
    _save(data)
    return entry
