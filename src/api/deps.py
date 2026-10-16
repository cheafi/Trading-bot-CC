"""
src/api/deps.py — FastAPI shared dependencies
==============================================
Central location for FastAPI Depends() callables.
Routers import from here instead of from main.py.
"""

from __future__ import annotations

import math
import os
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


def _dev_unauth_api_allowed() -> bool:
    """Explicit local-only bypass — never default for mutating broker/ledger APIs."""
    return os.environ.get("CC_DEV_ALLOW_UNAUTH_API", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _load_settings():
    from src.core.config import settings  # noqa: PLC0415

    return settings


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key from X-API-Key header (fail-closed)."""
    try:
        settings = _load_settings()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Configuration unavailable; cannot authenticate.",
        ) from exc

    if not settings.api_secret_key:
        if getattr(settings, "environment", "development") == "production":
            raise HTTPException(
                status_code=503,
                detail="API key not configured. Set API_SECRET_KEY.",
            )
        if _dev_unauth_api_allowed():
            return True
        raise HTTPException(
            status_code=401,
            detail=(
                "API key required. Set API_SECRET_KEY or "
                "CC_DEV_ALLOW_UNAUTH_API=1 for restricted local dev only."
            ),
        )

    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


async def optional_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Optional key for read-only surfaces — invalid key yields None (no raise)."""
    try:
        settings = _load_settings()
    except Exception:
        return None
    if settings.api_secret_key and x_api_key != settings.api_secret_key:
        return None
    return x_api_key
