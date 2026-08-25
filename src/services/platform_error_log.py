"""Session-scoped platform error log — ring buffer for operator diagnostics."""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Literal, Optional

from src.core.version import APP_VERSION

Severity = Literal["critical", "warning", "info"]

_MAX_ENTRIES = 200
_DEDUPE_TTL_SEC = 120.0

_buffer: Deque[Dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_lock = threading.Lock()
_recent_keys: Dict[str, float] = {}
_changelog_cache: Optional[Dict[str, Any]] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prune_dedupe(now: float) -> None:
    stale = [k for k, ts in _recent_keys.items() if now - ts > _DEDUPE_TTL_SEC]
    for key in stale:
        _recent_keys.pop(key, None)


def clear_error_log_for_tests() -> None:
    """Reset buffer — test helper only."""
    with _lock:
        _buffer.clear()
        _recent_keys.clear()


def log_platform_error(
    *,
    severity: Severity,
    component: str,
    message: str,
    detail: str,
    suggested_action: str = "",
    dedupe_key: Optional[str] = None,
    stack_trace: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    root_cause: Optional[str] = None,
    lesson: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Append one error entry. Returns the entry or None if deduplicated."""
    now = time.time()
    if dedupe_key:
        with _lock:
            _prune_dedupe(now)
            last = _recent_keys.get(dedupe_key)
            if last is not None and now - last < _DEDUPE_TTL_SEC:
                return None
            _recent_keys[dedupe_key] = now

    entry: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "timestamp": _now_iso(),
        "severity": severity,
        "component": component,
        "message": message,
        "detail": detail,
        "suggested_action": suggested_action
        or "Review Ops console and retry when upstream services recover.",
        "meta": meta or {},
    }
    if root_cause:
        entry["root_cause"] = root_cause
    if lesson:
        entry["lesson"] = lesson
    elif root_cause and not lesson:
        entry["lesson"] = (
            "Encode this failure in the decision machine — pain plus reflection."
        )
    if stack_trace:
        entry["stack_trace"] = stack_trace

    with _lock:
        _buffer.appendleft(entry)
    return entry


def log_api_failure(
    *,
    path: str,
    status_code: int,
    detail: str,
    component: str = "api",
    severity: Optional[Severity] = None,
) -> None:
    """Record an HTTP API failure with operator-friendly copy."""
    sev: Severity = severity or ("critical" if status_code >= 500 else "warning")
    short_path = path.split("?", 1)[0]
    msg = f"API {status_code} on {short_path}"
    plain = (
        f"The {short_path} endpoint returned HTTP {status_code}. "
        f"Server detail: {detail or 'no detail'}. "
        "Downstream boards may show stale, cached, or degraded output until this recovers."
    )
    action = (
        "Wait 30–60s and refresh. If persistent, open Ops → Error Log and check engine/broker state."
        if status_code >= 500
        else "Verify request parameters; this is usually a client or validation issue."
    )
    log_platform_error(
        severity=sev,
        component=component,
        message=msg,
        detail=plain,
        suggested_action=action,
        dedupe_key=f"api:{short_path}:{status_code}",
    )


def log_engine_stopped(*, cycle_count: int = 0, cached_recs: int = 0) -> None:
    """Log when signal engine is off — boards may be stale."""
    log_platform_error(
        severity="warning",
        component="engine",
        message="Signal engine not running this session",
        detail=(
            "The auto-trading / signal engine is stopped. Dashboard, Playbook, and Ranked views "
            "may still display cached, fallback, or precomputed recommendations — that is not proof "
            f"of a fresh scan (cycles={cycle_count}, cached_recs={cached_recs})."
        ),
        suggested_action=(
            "Start the engine or confirm scheduler jobs, then refresh Ops. "
            "Use Error Log for API/broker failures that may block startup."
        ),
        dedupe_key="engine:stopped",
        meta={"cycle_count": cycle_count, "cached_recs": cached_recs},
    )


def log_broker_event(
    *,
    event: str,
    detail: str,
    severity: Severity = "warning",
    suggested_action: str = "",
) -> None:
    """Record IBKR / broker connectivity events."""
    log_platform_error(
        severity=severity,
        component="broker",
        message=event,
        detail=detail,
        suggested_action=suggested_action
        or "Confirm IB Gateway/TWS is running, API port matches mode (paper/live), and client ID is free.",
        dedupe_key=f"broker:{event}",
    )


def log_dossier_timeout(*, ticker: str, reason: str = "") -> None:
    """Record stock-intel / dossier aggregation failures."""
    log_platform_error(
        severity="critical",
        component="dossier",
        message=f"Dossier load failed for {ticker}",
        detail=(
            f"Stock intel aggregation for {ticker} did not complete in time or a provider failed. "
            f"{reason or 'Upstream market data or enrichment modules may be cold or unavailable.'} "
            "The Dossier tab may show partial data or an error state."
        ),
        suggested_action=(
            "Retry with lite mode first; wait for cache warm-up. "
            "Check Error Log for repeated 503s from the same ticker."
        ),
        dedupe_key=f"dossier:{ticker}",
        meta={"ticker": ticker},
    )


def get_error_log(
    *,
    severity: Optional[str] = None,
    limit: int = 50,
    include_stack: bool = False,
) -> Dict[str, Any]:
    """Return recent entries, optionally filtered by severity."""
    sev = (severity or "all").lower()
    with _lock:
        rows = list(_buffer)

    if sev in ("critical", "warning", "info"):
        rows = [r for r in rows if r.get("severity") == sev]

    rows = rows[: max(1, min(limit, _MAX_ENTRIES))]

    if not include_stack:
        rows = [{k: v for k, v in r.items() if k != "stack_trace"} for r in rows]

    return {
        "count": len(rows),
        "total_buffered": len(_buffer),
        "severity_filter": sev,
        "include_stack": include_stack,
        "entries": rows,
    }


def _changelog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "changelog.json"


def _fallback_changelog() -> Dict[str, Any]:
    return {
        "version": APP_VERSION,
        "updated": _now_iso()[:10],
        "source": "fallback",
        "entries": [
            {
                "date": _now_iso()[:10],
                "title": "CC platform",
                "summary": (
                    "Changelog file unavailable — showing built-in fallback. "
                    "Edit data/changelog.json in the repo to maintain release notes."
                ),
                "surfaces": ["Ops"],
            }
        ],
    }


def load_changelog() -> Dict[str, Any]:
    """Load static changelog JSON from repo; merge canonical version."""
    global _changelog_cache
    if _changelog_cache is not None:
        return dict(_changelog_cache)

    path = _changelog_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("changelog root must be object")
        entries = raw.get("entries")
        if not isinstance(entries, list):
            entries = []
        payload = {
            "version": raw.get("version") or APP_VERSION,
            "updated": raw.get("updated") or _now_iso()[:10],
            "product": raw.get("product") or "CC — Clarity Console",
            "source": "data/changelog.json",
            "entries": entries,
        }
        _changelog_cache = payload
        return dict(payload)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        fallback = _fallback_changelog()
        _changelog_cache = fallback
        return dict(fallback)


def capture_exception(
    *,
    component: str,
    message: str,
    exc: BaseException,
    severity: Severity = "critical",
    suggested_action: str = "",
    dedupe_key: Optional[str] = None,
) -> None:
    """Log an exception with optional stack trace."""
    log_platform_error(
        severity=severity,
        component=component,
        message=message,
        detail=str(exc) or exc.__class__.__name__,
        suggested_action=suggested_action,
        dedupe_key=dedupe_key or f"{component}:{exc.__class__.__name__}",
        stack_trace=traceback.format_exc(),
    )
