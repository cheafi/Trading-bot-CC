"""Persistent user monitors — fixed path only (no user input in file paths)."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STORE = Path("data") / "monitors.json"
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_ALLOWED_CLASSES = frozenset(
    {"stock", "portfolio", "market", "smart_money", "thesis"}
)
_ALLOWED_RULE_TYPES = frozenset(
    {
        "thesis_drift",
        "insider_cluster",
        "options_flow",
        "weight_drift",
        "stop_breach",
        "correlation_spike",
        "regime_mismatch",
        "catalyst_countdown",
        "earnings_proximity",
        "benchmark_lag",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _sanitize_ticker(ticker: str) -> Optional[str]:
    t = (ticker or "").strip().upper()
    if not t or not _TICKER_RE.match(t):
        return None
    return t


def _load() -> Dict[str, Any]:
    if not _STORE.exists():
        return {"monitors": [], "updated_at": _now()}
    try:
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("monitors"), list):
            return data
    except Exception as exc:
        logger.warning("monitors load failed: %s", exc)
    return {"monitors": [], "updated_at": _now()}


def _save(data: Dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_monitors(*, active_only: bool = False) -> Dict[str, Any]:
    data = _load()
    rows = data.get("monitors") or []
    if active_only:
        rows = [m for m in rows if m.get("enabled", True)]
    return {"monitors": rows, "count": len(rows), "as_of": _now()}


def create_monitor(body: Dict[str, Any]) -> Dict[str, Any]:
    rule_class = (body.get("class") or "stock").lower()
    if rule_class not in _ALLOWED_CLASSES:
        rule_class = "stock"
    rule_type = (body.get("rule_type") or "thesis_drift").lower()
    if rule_type not in _ALLOWED_RULE_TYPES:
        rule_type = "thesis_drift"
    ticker = _sanitize_ticker(body.get("ticker") or "")
    entry = {
        "id": str(uuid.uuid4())[:12],
        "class": rule_class,
        "rule_type": rule_type,
        "ticker": ticker,
        "label": (body.get("label") or rule_type)[:80],
        "severity": (body.get("severity") or "medium")[:16],
        "enabled": bool(body.get("enabled", True)),
        "created_at": _now(),
        "params": body.get("params") if isinstance(body.get("params"), dict) else {},
    }
    data = _load()
    data.setdefault("monitors", []).append(entry)
    _save(data)
    return entry


def update_monitor(monitor_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load()
    for i, m in enumerate(data.get("monitors") or []):
        if m.get("id") != monitor_id:
            continue
        if "enabled" in body:
            m["enabled"] = bool(body["enabled"])
        if "label" in body:
            m["label"] = str(body["label"])[:80]
        if "severity" in body:
            m["severity"] = str(body["severity"])[:16]
        if "ticker" in body:
            t = _sanitize_ticker(body["ticker"])
            if t:
                m["ticker"] = t
        data["monitors"][i] = m
        _save(data)
        return m
    return None


def delete_monitor(monitor_id: str) -> bool:
    data = _load()
    before = len(data.get("monitors") or [])
    data["monitors"] = [m for m in data.get("monitors") or [] if m.get("id") != monitor_id]
    if len(data["monitors"]) < before:
        _save(data)
        return True
    return False


def evaluate_monitors(
    *,
    today: Optional[Dict[str, Any]] = None,
    positions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Lightweight evaluator — surfaces active rules as alert stubs."""
    alerts: List[Dict[str, Any]] = []
    data = _load()
    regime = (today or {}).get("market_regime") or {}
    for m in data.get("monitors") or []:
        if not m.get("enabled"):
            continue
        rt = m.get("rule_type")
        if rt == "regime_mismatch" and regime.get("tradeability") == "NO_TRADE":
            alerts.append(_alert_from_rule(m, "Regime NO_TRADE — review risk", "high"))
        elif rt == "earnings_proximity" and m.get("ticker"):
            alerts.append(
                _alert_from_rule(
                    m,
                    f"Earnings watch on {m['ticker']} — confirm calendar",
                    "medium",
                )
            )
        elif rt == "weight_drift" and positions:
            alerts.append(
                _alert_from_rule(m, "Portfolio drift — check allocation monitor", "medium")
            )
    return alerts[:20]


def _alert_from_rule(rule: Dict[str, Any], message: str, severity: str) -> Dict[str, Any]:
    return {
        "id": rule.get("id"),
        "what_changed": message,
        "why_it_matters": rule.get("label") or rule.get("rule_type"),
        "severity": severity,
        "confidence": "medium",
        "evidence_quality": "rule_based",
        "recommended_action": "Review on Portfolio / Dossier",
        "next_review": "daily",
        "rule": rule,
    }
