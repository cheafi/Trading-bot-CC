"""Shared CC performance helpers — cache fingerprints and HTTP cache headers."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Mapping, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, Response


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def today_cache_fingerprint(request: Request) -> str:
    """Cheap invalidation key when scanner/brief/broker inputs change."""
    parts: list[str] = []
    scan_cache = getattr(request.app.state, "scan_cache", None) or {}
    parts.append(f"scan:{scan_cache.get('ts', 0)}:{len(scan_cache.get('recs') or [])}")
    try:
        from src.api.routers.brief_regenerate import _latest_brief

        brief = _latest_brief() or {}
        parts.append(f"brief:{brief.get('date') or ''}:{brief.get('age_days', 0)}")
    except Exception:
        parts.append("brief:unknown")
    try:
        from src.services.ibkr_service import get_ibkr_service

        ibkr = get_ibkr_service().status()
        parts.append(
            "ibkr:"
            f"{int(bool(ibkr.get('connected')))}:"
            f"{int(bool(ibkr.get('session_usable')))}:"
            f"{ibkr.get('mode') or 'paper'}"
        )
    except Exception:
        parts.append("ibkr:unknown")
    try:
        from src.api.app_state import get_engine

        engine = get_engine(request.app)
        if engine:
            parts.append(
                f"eng:{int(bool(getattr(engine, '_running', False)))}:"
                f"{int(bool(getattr(engine, 'circuit_breaker_triggered', False)))}"
            )
        else:
            parts.append("eng:0:0")
    except Exception:
        parts.append("eng:unknown")
    return "|".join(parts)


def payload_etag(payload: Mapping[str, Any]) -> str:
  """Stable weak ETag from generated_at + trust.as_of when present."""
  trust = payload.get("trust") or {}
  seed = (
      str(payload.get("generated_at") or "")
      + ":"
      + str(trust.get("as_of") or "")
      + ":"
      + str(payload.get("date") or "")
  )
  return f'W/"{hashlib.md5(seed.encode()).hexdigest()[:16]}"'


def json_cache_response(
    payload: Dict[str, Any],
    request: Request,
    *,
    max_age: int = 30,
    stale_while_revalidate: int = 60,
) -> Response:
    """JSON response with private Cache-Control + ETag; honors If-None-Match."""
    etag = payload_etag(payload)
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": (
                    f"private, max-age={max_age}, "
                    f"stale-while-revalidate={stale_while_revalidate}"
                ),
            },
        )
    return JSONResponse(
        payload,
        headers={
            "ETag": etag,
            "Cache-Control": (
                f"private, max-age={max_age}, "
                f"stale-while-revalidate={stale_while_revalidate}"
            ),
        },
    )


def cc_header_cache_key(tab: Optional[str]) -> str:
    return (tab or "").strip().lower() or "_default"


def fingerprint_json(payload: Mapping[str, Any]) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        blob = str(payload)
    return hashlib.md5(blob.encode()).hexdigest()[:12]
