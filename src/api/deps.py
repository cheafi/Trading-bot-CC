"""
src/api/deps.py — FastAPI shared dependencies
==============================================
Central location for FastAPI Depends() callables.
Routers import from here instead of from main.py.
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import Header, HTTPException

# ── JSON sanitizer ────────────────────────────────────────────────────────────


def sanitize_for_json(obj: Any) -> Any:
    """Recursively replace NaN / Inf floats with None for JSON compliance."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    return obj


# Keep underscore alias for backward-compat callers
_sanitize_for_json = sanitize_for_json


# ── Auth dependencies ─────────────────────────────────────────────────────────


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key from X-API-Key header.

    Security hardening: in production, a missing API_SECRET_KEY means ALL
    authenticated endpoints are locked. In development we allow open access.
    """
    try:
        from src.core.config import settings  # noqa: PLC0415
    except Exception:
        return True

    if not settings.api_secret_key:
        if getattr(settings, "environment", "development") == "production":
            raise HTTPException(
                status_code=503,
                detail="API key not configured. Set API_SECRET_KEY.",
            )
        return True  # dev/staging: open access

    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


async def optional_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Optional API key verification — returns None on mismatch (no raise)."""
    try:
        from src.core.config import settings  # noqa: PLC0415
    except Exception:
        return x_api_key
    if settings.api_secret_key and x_api_key != settings.api_secret_key:
        return None
    return x_api_key
