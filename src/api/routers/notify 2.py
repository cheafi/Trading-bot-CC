"""
Notify Router — Sprint 106
==========================
REST endpoints for querying the alert event log and test-firing a notification.

Endpoints:
  GET  /api/v7/notify/log         — last N alert events from alert_log.json
  POST /api/v7/notify/test        — fire a test notification to Discord
  GET  /api/v7/notify/status      — Discord webhook configured? last event ts?
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Query

from src.api.deps import optional_api_key, sanitize_for_json

router = APIRouter(prefix="/api/v7/notify", tags=["notify"])


@router.get("/log")
async def alert_log(limit: int = Query(default=20, ge=1, le=50)) -> Dict[str, Any]:
    """Return the last *limit* alert events persisted by AlertService."""
    try:
        from src.services.alert_service import get_alert_log  # noqa: PLC0415

        events = get_alert_log(limit=limit)
        return sanitize_for_json(
            {
                "count": len(events),
                "events": events,
            }
        )
    except Exception as exc:
        return {"count": 0, "events": [], "error": str(exc)}


@router.post("/test")
async def send_test_alert(
    message: str = Query(default="AlertService test ping from TradingAI Bot"),
    severity: str = Query(default="info"),
) -> Dict[str, Any]:
    """Fire a test Discord alert and log it.  Returns push success flag."""
    valid_severities = {"info", "warning", "critical", "ok"}
    if severity not in valid_severities:
        severity = "info"
    try:
        from src.services.alert_service import (
            _append_log,
            _make_event,
            _push_discord,
        )  # noqa: PLC0415

        event = _make_event(
            event_type="test",
            title="🧪 Test Alert",
            message=message,
            severity=severity,
        )
        _append_log(event)
        pushed = _push_discord("🧪 Test Alert", message, severity)
        return {
            "ok": True,
            "pushed_to_discord": pushed,
            "severity": severity,
            "message": message,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/status")
async def notify_status() -> Dict[str, Any]:
    """Check whether Discord webhook is configured and show last alert timestamp."""
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "") or os.getenv(
        "DISCORD_ALERT_WEBHOOK", ""
    )
    configured = bool(webhook)
    try:
        from src.services.alert_service import get_alert_log  # noqa: PLC0415

        log = get_alert_log(limit=1)
        last_ts = log[-1]["ts"] if log else None
        last_type = log[-1]["event_type"] if log else None
    except Exception:
        last_ts = None
        last_type = None

    return {
        "discord_configured": configured,
        "webhook_set": "yes" if configured else "no (set DISCORD_WEBHOOK_URL)",
        "last_alert_ts": last_ts,
        "last_alert_type": last_type,
    }
