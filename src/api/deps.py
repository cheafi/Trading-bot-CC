"""
src/api/deps.py — FastAPI shared dependencies
==============================================
Central location for FastAPI Depends() callables.
Routers import from here instead of from main.py.
"""

from __future__ import annotations

import hmac
import math
import re
from typing import Any

from fastapi import Header, HTTPException

_TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")

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


def validate_ticker(ticker: str) -> str:
    """Sanitize and validate a ticker symbol."""
    cleaned = ticker.strip().upper()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Ticker symbol is required.")
    if not _TICKER_RE.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid ticker '{ticker}'. "
                "Allowed: letters, digits, '.', '-', '^'. Max 10 chars."
            ),
        )
    return cleaned


# ── Auth dependencies ─────────────────────────────────────────────────────────


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key from X-API-Key header.

    Security hardening: in production, a missing API_SECRET_KEY means ALL
    authenticated endpoints are locked. In development we allow open access.
    """
    try:
        from src.core.config import settings  # noqa: PLC0415
    except Exception as e:
        # Fail closed: an unreadable config must not grant access to every
        # authenticated endpoint.
        raise HTTPException(
            status_code=503,
            detail="Auth configuration unavailable.",
        ) from e

    if not settings.api_secret_key:
        if getattr(settings, "environment", "development") == "production":
            raise HTTPException(
                status_code=503,
                detail="API key not configured. Set API_SECRET_KEY.",
            )
        return True  # dev/staging: open access

    # compare_digest, not ==: a plain comparison leaks the key byte-by-byte
    # through response timing.
    if not x_api_key or not hmac.compare_digest(
        str(x_api_key), str(settings.api_secret_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


async def optional_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Optional API key verification — returns None on mismatch (no raise)."""
    try:
        from src.core.config import settings  # noqa: PLC0415
    except Exception:
        return None  # fail closed — treat as unauthenticated
    if settings.api_secret_key and (
        not x_api_key
        or not hmac.compare_digest(str(x_api_key), str(settings.api_secret_key))
    ):
        return None
    return x_api_key
