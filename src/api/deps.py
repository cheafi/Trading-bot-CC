"""
src/api/deps.py — FastAPI shared dependencies
==============================================
Central location for FastAPI Depends() callables.
Routers import from here instead of from main.py.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import time
from typing import Any

from fastapi import Cookie, Header, HTTPException

OPERATOR_SESSION_COOKIE = "cc_operator_session"
OPERATOR_SESSION_MAX_AGE_S = 12 * 3600

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


def _require_matching_api_key(
    x_api_key: str | None, *, allow_dev_bypass: bool
) -> bool:
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
        if allow_dev_bypass and _dev_unauth_api_allowed():
            return True
        raise HTTPException(
            status_code=401,
            detail=(
                "API key required. Set API_SECRET_KEY"
                + (
                    " or CC_DEV_ALLOW_UNAUTH_API=1 for non-sensitive local dev only."
                    if allow_dev_bypass
                    else " for this endpoint."
                )
            ),
        )

    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key; optional CC_DEV_ALLOW_UNAUTH_API for non-sensitive routes only."""
    return _require_matching_api_key(x_api_key, allow_dev_bypass=True)


def mint_operator_session_token(api_secret: str) -> str:
    """Signed HttpOnly session cookie value (no API key embedded)."""
    exp = int(time.time()) + OPERATOR_SESSION_MAX_AGE_S
    payload = f"v1.{exp}"
    sig = hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_operator_session_token(api_secret: str, token: str | None) -> bool:
    if not api_secret or not token:
        return False
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(
            api_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        exp = int(payload.split(".", 1)[1])
        return time.time() <= exp
    except (ValueError, TypeError, IndexError):
        return False


async def verify_sensitive_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
) -> bool:
    """Broker, ledger, and account mutations — never allow unauthenticated dev bypass."""
    try:
        settings = _load_settings()
        secret = settings.api_secret_key or ""
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Configuration unavailable; cannot authenticate.",
        ) from exc

    if secret and x_api_key and hmac.compare_digest(x_api_key, secret):
        return True
    if secret and verify_operator_session_token(secret, cc_operator_session):
        return True
    return _require_matching_api_key(x_api_key, allow_dev_bypass=False)


async def optional_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Optional key for read-only surfaces — invalid key yields None (no raise)."""
    try:
        settings = _load_settings()
    except Exception:
        return None
    if settings.api_secret_key and x_api_key != settings.api_secret_key:
        return None
    return x_api_key
