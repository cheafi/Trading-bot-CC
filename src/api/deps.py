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
import secrets
import time
from typing import Any
from urllib.parse import urlparse

from fastapi import Cookie, Header, HTTPException, Request

OPERATOR_SESSION_COOKIE = "cc_operator_session"
OPERATOR_SESSION_MAX_AGE_S = 12 * 3600
PORTFOLIO_SESSION_SCOPE = "portfolio"

_TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")

# In-process revocation (single-operator); not durable across restarts.
_REVOKED_PORTFOLIO_SESSION_IDS: set[str] = set()

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


def _api_secret_or_raise() -> str:
    try:
        settings = _load_settings()
        secret = (settings.api_secret_key or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Configuration unavailable; cannot authenticate.",
        ) from exc
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set API_SECRET_KEY.",
        )
    return secret


def _header_api_key_valid(secret: str, x_api_key: str | None) -> bool:
    return bool(x_api_key and hmac.compare_digest(x_api_key, secret))


def cookie_secure_flag() -> bool:
    return os.environ.get("CC_COOKIE_SECURE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def mint_operator_session_token(api_secret: str) -> tuple[str, str]:
    """Portfolio-scoped signed cookie (scope embedded; no API key in token)."""
    exp = int(time.time()) + OPERATOR_SESSION_MAX_AGE_S
    session_id = secrets.token_hex(16)
    payload = f"v1.{PORTFOLIO_SESSION_SCOPE}.{exp}.{session_id}"
    sig = hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}", session_id


def parse_portfolio_session_token(token: str | None) -> tuple[str, int, str] | None:
    if not token:
        return None
    try:
        body, sig = token.rsplit(".", 1)
        parts = body.split(".")
        if len(parts) != 4 or parts[0] != "v1" or parts[1] != PORTFOLIO_SESSION_SCOPE:
            return None
        exp = int(parts[2])
        session_id = parts[3]
        return body, exp, session_id
    except (ValueError, TypeError, IndexError):
        return None


def verify_portfolio_session_token(api_secret: str, token: str | None) -> bool:
    if not api_secret or not token:
        return False
    parsed = parse_portfolio_session_token(token)
    if not parsed:
        return False
    body, exp, session_id = parsed
    if session_id in _REVOKED_PORTFOLIO_SESSION_IDS:
        return False
    expected = hmac.new(
        api_secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    try:
        _, sig = token.rsplit(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(sig, expected):
        return False
    return time.time() <= exp


def revoke_portfolio_session_token(token: str | None) -> bool:
    """Server-side revoke for portfolio session id (logout)."""
    parsed = parse_portfolio_session_token(token)
    if not parsed:
        return False
    _REVOKED_PORTFOLIO_SESSION_IDS.add(parsed[2])
    return True


def verify_operator_session_token(api_secret: str, token: str | None) -> bool:
    """Backward-compatible alias — portfolio scope only."""
    return verify_portfolio_session_token(api_secret, token)


def _same_origin_for_cookie_mutation(request: Request) -> bool:
    """Fail-closed Origin/Referer check for cookie-authenticated writes."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if not host:
        return False
    origin = request.headers.get("origin")
    if origin:
        try:
            return urlparse(origin).hostname == host
        except Exception:
            return False
    referer = request.headers.get("referer")
    if referer:
        try:
            return urlparse(referer).hostname == host
        except Exception:
            return False
    return False


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key; optional CC_DEV_ALLOW_UNAUTH_API for non-sensitive routes only."""
    return _require_matching_api_key(x_api_key, allow_dev_bypass=True)


async def verify_sensitive_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> bool:
    """Privileged execution/admin — header API key only; never portfolio session cookie."""
    secret = _api_secret_or_raise()
    if _header_api_key_valid(secret, x_api_key):
        return True
    return _require_matching_api_key(x_api_key, allow_dev_bypass=False)


async def verify_portfolio_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
) -> bool:
    """Dashboard portfolio read — API key header or portfolio-scoped session cookie."""
    secret = _api_secret_or_raise()
    if _header_api_key_valid(secret, x_api_key):
        return True
    if verify_portfolio_session_token(secret, cc_operator_session):
        return True
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def verify_portfolio_write(
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key"),
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
) -> bool:
    """Portfolio mutations via cookie require same-origin evidence (CSRF mitigation)."""
    secret = _api_secret_or_raise()
    if _header_api_key_valid(secret, x_api_key):
        return True
    if not verify_portfolio_session_token(secret, cc_operator_session):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if request.method.upper() in ("GET", "HEAD", "OPTIONS"):
        return True
    if not _same_origin_for_cookie_mutation(request):
        raise HTTPException(
            status_code=403,
            detail="Cross-origin cookie mutation blocked; use X-API-Key for privileged clients.",
        )
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
