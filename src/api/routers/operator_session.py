"""Same-origin portfolio session — avoids embedding API_SECRET_KEY in HTML."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.api.deps import (
    OPERATOR_SESSION_COOKIE,
    OPERATOR_SESSION_MAX_AGE_S,
    cookie_secure_flag,
    mint_operator_session_token,
    revoke_portfolio_session_token,
    verify_portfolio_session_token,
)

router = APIRouter(tags=["operator"])


class OperatorSessionRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512)


def _load_secret() -> str:
    from src.api.deps import _load_settings

    settings = _load_settings()
    secret = (settings.api_secret_key or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set API_SECRET_KEY.",
        )
    return secret


@router.post("/api/operator/session")
async def establish_operator_session(
    body: OperatorSessionRequest,
    request: Request,
    response: Response,
):
    """Validate operator API key and set portfolio-scoped HttpOnly session cookie."""
    secret = _load_secret()
    if not hmac.compare_digest(body.api_key.strip(), secret):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    token, _session_id = mint_operator_session_token(secret)
    response.set_cookie(
        key=OPERATOR_SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure_flag() or request.url.scheme == "https",
        max_age=OPERATOR_SESSION_MAX_AGE_S,
        path="/",
    )
    return {
        "ok": True,
        "authenticated": True,
        "scope": "portfolio",
        "expires_in_seconds": OPERATOR_SESSION_MAX_AGE_S,
    }


@router.delete("/api/operator/session")
async def clear_operator_session(
    response: Response,
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
):
    revoke_portfolio_session_token(cc_operator_session)
    response.delete_cookie(key=OPERATOR_SESSION_COOKIE, path="/")
    return {"ok": True, "authenticated": False, "revoked": True}


@router.get("/api/operator/session/status")
async def operator_session_status(
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
):
    """Non-sensitive session probe for dashboard bootstrap."""
    try:
        secret = _load_secret()
    except HTTPException:
        return {"authenticated": False, "reason": "api_key_not_configured"}
    return {
        "authenticated": verify_portfolio_session_token(secret, cc_operator_session),
        "scope": "portfolio",
    }
