"""Persistent store for Vibe Agent intents, rules, alerts, journal — fixed paths only."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STORE = Path("data") / "artifacts" / "vibe_agent.json"
_LOG = Path("data") / "artifacts" / "vibe_agent_audit.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _empty() -> Dict[str, Any]:
    return {
        "intents": [],
        "rules": [],
        "alerts": [],
        "journal": [],
        "updated_at": _now(),
    }


def _load() -> Dict[str, Any]:
    if not _STORE.exists():
        return _empty()
    try:
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in ("intents", "rules", "alerts", "journal"):
                if not isinstance(data.get(key), list):
                    data[key] = []
            return data
    except Exception as exc:
        logger.warning("vibe_agent store load failed: %s", exc)
    return _empty()


def _save(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_agent_decision(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append-only audit log."""
    row = {"id": str(uuid.uuid4())[:12], "timestamp": _now(), **entry}
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    data = _load()
    data.setdefault("journal", []).append(
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "type": entry.get("type") or "audit",
            "linkedIntentId": entry.get("intent_id"),
            "linkedRuleId": entry.get("rule_id"),
            "linkedAlertId": entry.get("alert_id"),
            "userAction": entry.get("user_action"),
            "detail": entry.get("detail") or "",
        }
    )
    if len(data["journal"]) > 500:
        data["journal"] = data["journal"][-500:]
    _save(data)
    return row


def list_intents(*, status: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _load().get("intents") or []
    if status:
        rows = [r for r in rows if str(r.get("status") or "") == status]
    return rows


def save_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**intent, "id": intent.get("id") or str(uuid.uuid4())[:12]}
    data.setdefault("intents", []).append(entry)
    _save(data)
    return entry


def list_rules(*, status: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _load().get("rules") or []
    if status:
        rows = [r for r in rows if str(r.get("status") or "active") == status]
    return rows


def save_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**rule, "id": rule.get("id") or str(uuid.uuid4())[:12], "created_at": _now()}
    data.setdefault("rules", []).append(entry)
    _save(data)
    return entry


def update_rule(rule_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load()
    for i, row in enumerate(data.get("rules") or []):
        if str(row.get("id")) == rule_id:
            data["rules"][i] = {**row, **patch, "updated_at": _now()}
            _save(data)
            return data["rules"][i]
    return None


def list_alerts(*, limit: int = 50) -> List[Dict[str, Any]]:
    rows = sorted(
        _load().get("alerts") or [],
        key=lambda r: str(r.get("triggeredAt") or ""),
        reverse=True,
    )
    return rows[:limit]


def save_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    entry = {**alert, "id": alert.get("id") or str(uuid.uuid4())[:12]}
    data.setdefault("alerts", []).append(entry)
    if len(data["alerts"]) > 300:
        data["alerts"] = data["alerts"][-300:]
    _save(data)
    return entry


def update_alert(alert_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load()
    for i, row in enumerate(data.get("alerts") or []):
        if str(row.get("id")) == alert_id:
            data["alerts"][i] = {**row, **patch, "updated_at": _now()}
            _save(data)
            return data["alerts"][i]
    return None


def list_journal(*, limit: int = 100) -> List[Dict[str, Any]]:
    rows = sorted(
        _load().get("journal") or [],
        key=lambda r: str(r.get("timestamp") or ""),
        reverse=True,
    )
    return rows[:limit]


def store_snapshot() -> Dict[str, Any]:
    data = _load()
    return {
        "intent_count": len(data.get("intents") or []),
        "rule_count": len(data.get("rules") or []),
        "alert_count": len(data.get("alerts") or []),
        "journal_count": len(data.get("journal") or []),
        "updated_at": data.get("updated_at"),
    }
